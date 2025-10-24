import asyncio
import time
import logging
import aiohttp
from datetime import timedelta
import async_timeout
# UpdateFailed lives in helpers.update_coordinator in current HA. Fall back
# gracefully if imported location differs on older cores.
try:
    from homeassistant.helpers.update_coordinator import (
        DataUpdateCoordinator,
        UpdateFailed,
    )
except Exception:  # pragma: no cover - compatibility shim
    from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

    class UpdateFailed(Exception):
        pass

_LOGGER = logging.getLogger(__name__)


class ThermalCameraDataCoordinator(DataUpdateCoordinator):
    """
    Hybrid coordinator: behaves like the original poller when talking to a JSON
    endpoint, and can optionally open a persistent binary stream (length-
    prefixed frames) when `use_stream=True` or path == 'bin'.

    Backwards compatible constructor signature is preserved so existing code
    that constructs this class with (hass, session, url, path, data_field,
    lowest_field, highest_field, average_field) continues to work. Additional
    optional kwargs: width, height, update_interval_ms, use_stream,
    stream_push_ms (throttle push frequency when streaming; default 100ms).
    """

    def __init__(
        self,
        hass,
        session,
        url,
        path,
        data_field,
        lowest_field,
        highest_field,
        average_field,
        *,
        width: int = 32,
        height: int = 24,
        update_interval_ms: int = 500,
        use_stream: bool = None,
    stream_push_ms: int = 1000,
    ):
        super().__init__(
            hass,
            _LOGGER,
            name="Thermal Camera Data Coordinator",
            update_interval=timedelta(milliseconds=update_interval_ms),
        )

        self.session = session
        self.url = url.rstrip("/")
        self.path = path.lstrip("/")
        self.data_field = data_field
        self.lowest_field = lowest_field
        self.highest_field = highest_field
        self.average_field = average_field
        self.width = width
        self.height = height
        self.stream_push_ms = max(1, int(stream_push_ms))

        # Decide whether to use stream: explicit flag overrides, otherwise use
        # stream when path == 'bin'.
        if use_stream is None:
            self.use_stream = (self.path == "bin")
        else:
            self.use_stream = bool(use_stream)

        self._last_data = {
            "frame_data": [],
            "min_value": 0.0,
            "max_value": 0.0,
            "avg_value": 0.0,
        }

        # background stream reader (only created in stream mode)
        self._reader_task = None
        if self.use_stream:
            self._reader_task = asyncio.create_task(self._stream_reader_loop())

    async def _async_update_data(self):
        """
        Polling path (JSON) — kept for backward compatibility.
        If streaming mode is active this method simply returns the last known
        data.
        """
        if not self.use_stream:
            try:
                _LOGGER.debug("Polling JSON endpoint %s/%s", self.url, self.path)
                async with async_timeout.timeout(1.5):
                    async with self.session.get(f"{self.url}/{self.path}", headers={"Connection": "close"}) as resp:
                        if resp.status != 200:
                            _LOGGER.warning("Failed to fetch JSON: %s", resp.status)
                            return self._last_data
                        data = await resp.json()
                        frame_data = data.get(self.data_field, []) if self.data_field else data
                        # If the response lacked frame data, keep the last known frame to
                        # avoid spamming downstream components with empty frames.
                        if not frame_data:
                            _LOGGER.debug(
                                "JSON response missing/empty frame data; keeping last known frame"
                            )
                            frame_data = self._last_data.get("frame_data", [])

                        min_v = data.get(self.lowest_field, 0.0) if self.lowest_field else 0.0
                        max_v = data.get(self.highest_field, 0.0) if self.highest_field else 0.0
                        avg_v = data.get(self.average_field, 0.0) if self.average_field else 0.0
                        self._last_data = {
                            "frame_data": frame_data,
                            "min_value": min_v,
                            "max_value": max_v,
                            "avg_value": avg_v,
                        }
                        # set updated data and notify listeners
                        try:
                            self.async_set_updated_data(self._last_data)
                        except Exception:
                            # older integrations may rely on different behavior; ignore
                            pass
                        return self._last_data
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                _LOGGER.warning("Network error polling JSON: %s", e)
                return self._last_data
            except Exception as e:
                _LOGGER.exception("Unexpected error polling JSON: %s", e)
                return self._last_data
        else:
            # In streaming mode, just return the last-known data (which may be
            # empty initially) so HA setup doesn't fail. The background reader
            # will call async_set_updated_data() as soon as a valid frame
            # arrives.
            return self._last_data

    async def _stream_reader_loop(self):
        """
        Persistent stream reader for length-prefixed binary frames. Reconnects
        with exponential backoff on error.
        """
        connect_url = f"{self.url}/{self.path}"
        backoff = 1.0
        while True:
            try:
                _LOGGER.debug("Connecting to binary stream at %s", connect_url)
                timeout = aiohttp.ClientTimeout(total=None)
                headers = {"Connection": "keep-alive"}
                async with self.session.get(connect_url, timeout=timeout, headers=headers) as resp:
                    if resp.status != 200:
                        _LOGGER.warning("Stream endpoint returned %s, retrying", resp.status)
                        await asyncio.sleep(backoff)
                        backoff = min(backoff * 2, 10.0)
                        continue

                    _LOGGER.debug("Connected to stream, reading frames")
                    backoff = 1.0
                    last_push_ts = 0.0  # monotonic seconds
                    pending_payload: bytes | None = None

                    while True:
                        header = await resp.content.readexactly(4)
                        if not header:
                            _LOGGER.debug("Stream closed by server")
                            break
                        length = int.from_bytes(header, byteorder="big", signed=False)
                        if length <= 0:
                            _LOGGER.warning("Invalid frame length %s, closing stream", length)
                            break
                        payload = await resp.content.readexactly(length)

                        # Coalesce frames: avoid parsing for frames we won't push
                        now_ts = time.monotonic()
                        if (now_ts - last_push_ts) * 1000.0 < self.stream_push_ms:
                            # keep only the latest payload
                            pending_payload = payload
                            continue

                        # Use the latest payload (current or pending) for parsing
                        if pending_payload is not None:
                            payload_to_parse = pending_payload
                            pending_payload = None
                        else:
                            payload_to_parse = payload

                        values = self._parse_payload(payload_to_parse)

                        # If the parsed payload is an empty list, skip updating the
                        # last-known frame. Empty frames are noisy for consumers;
                        # prefer keeping the previous frame until valid data arrives.
                        if isinstance(values, list) and not values:
                            _LOGGER.debug("Received empty frame from stream; keeping last known frame")
                            continue

                        # compute stats if numeric
                        min_v = max_v = avg_v = None
                        if isinstance(values, list) and values:
                            try:
                                numeric = [float(x) for x in values]
                                min_v = min(numeric)
                                max_v = max(numeric)
                                avg_v = sum(numeric) / len(numeric)
                            except Exception:
                                numeric = None

                        # Keep a flat 1D list to reduce object churn; consumers can reshape if needed
                        frame_data = values

                        self._last_data = {
                            "frame_data": frame_data,
                            "min_value": (min_v if min_v is not None else self._last_data.get("min_value", 0.0)),
                            "max_value": (max_v if max_v is not None else self._last_data.get("max_value", 0.0)),
                            "avg_value": (avg_v if avg_v is not None else self._last_data.get("avg_value", 0.0)),
                        }

                        # Throttle updates to Home Assistant to reduce load
                        if (now_ts - last_push_ts) * 1000.0 >= self.stream_push_ms:
                            last_push_ts = now_ts
                            try:
                                self.async_set_updated_data(self._last_data)
                            except Exception as e:
                                _LOGGER.exception("Failed to set updated data: %s", e)
                            # Yield to event loop to avoid starving HA
                            await asyncio.sleep(0)

            except asyncio.CancelledError:
                _LOGGER.debug("Stream reader cancelled")
                break
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                _LOGGER.warning("Stream connection error: %s — reconnecting in %.1fs", exc, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 10.0)
                continue
            except Exception as exc:
                _LOGGER.exception("Unexpected stream reader error: %s — reconnecting in %.1fs", exc, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 10.0)
                continue

    def _parse_payload(self, payload: bytes):
        # try JSON
        try:
            text = payload.decode("utf-8")
            data = __import__("json").loads(text)
            if isinstance(data, list):
                return data
        except Exception:
            pass

        # float32 big-endian
        if len(payload) % 4 == 0:
            try:
                import struct

                cnt = len(payload) // 4
                fmt = ">" + ("f" * cnt)
                return list(struct.unpack(fmt, payload))
            except Exception:
                pass

        # uint16 big-endian
        if len(payload) % 2 == 0:
            try:
                import struct

                cnt = len(payload) // 2
                fmt = ">" + ("H" * cnt)
                raw_vals = list(struct.unpack(fmt, payload))
                # convert raw uint16 -> Celsius using device formula: (v/128.0)-64.0
                vals = [((v / 128.0) - 64.0) for v in raw_vals]
                return vals
            except Exception:
                pass

        return payload

    async def async_will_remove(self):
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
