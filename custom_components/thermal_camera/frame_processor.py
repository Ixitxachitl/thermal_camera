import numpy as np
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

def process_frame(frame_data, min_value, max_value, avg_value, rows, cols, resample_method, font, desired_height):
    """Convert frame data to an image with overlays."""
    # Vectorized color mapping to avoid loops
    normalized_data = np.clip((frame_data - min_value) / (max_value - min_value), 0, 1)
    rgb_array = np.zeros((rows, cols, 3), dtype=np.uint8)
    
    # Map normalized data to RGB values using vectorized ranges
    rgb_array[..., 0] = np.where(normalized_data >= 0.5, np.minimum(255, 510 * (normalized_data - 0.5)), 0)
    rgb_array[..., 1] = np.where(
        (normalized_data >= 0.25) & (normalized_data < 0.75),
        np.minimum(255, 510 * (0.75 - abs(normalized_data - 0.5))),
        0,
    )
    rgb_array[..., 2] = np.where(normalized_data < 0.5, np.minimum(255, 510 * (0.5 - normalized_data)), 0)

    # Create a PIL image from the RGB array
    img = Image.fromarray(rgb_array, "RGB")

    # Scale the image
    scale_factor = 20
    img = img.resize((cols * scale_factor, rows * scale_factor), resample=resample_method)

    # Draw overlay elements (e.g., reticle, scale bar)
    draw_overlay(img, frame_data, min_value, max_value, avg_value, scale_factor, font)

    # Resize to desired height if needed
    if img.height != desired_height:
        aspect_ratio = img.width / img.height
        img = img.resize((int(desired_height * aspect_ratio), desired_height), resample=resample_method)

    return image_to_jpeg_bytes(img)

def map_to_color(value, min_value, max_value):
    """Map thermal value to a color gradient."""
    normalized = max(0.0, min(1.0, (value - min_value) / (max_value - min_value)))
    if normalized < 0.25:  # Black to Blue
        return (0, 0, int(255 * (normalized / 0.25)))
    elif normalized < 0.5:  # Blue to Green
        blue = int(255 * (1 - (normalized - 0.25) / 0.25))
        green = int(255 * ((normalized - 0.25) / 0.25))
        return (0, green, blue)
    elif normalized < 0.75:  # Green to Yellow
        return (int(255 * ((normalized - 0.5) / 0.25)), 255, 0)
    elif normalized < 0.9:  # Yellow to Red
        return (255, int(255 * (1 - (normalized - 0.75) / 0.15)), 0)
    else:  # Red to White
        return (255, int(255 * ((normalized - 0.9) / 0.1)), int(255 * ((normalized - 0.9) / 0.1)))

def image_to_jpeg_bytes(img):
    """Convert PIL image to JPEG bytes."""
    with BytesIO() as output:
        img.save(output, format="JPEG")
        return output.getvalue()

def draw_overlay(img, frame_data, min_value, max_value, avg_value, scale_factor, font):
    """Draw reticle, scale bar, and temperature text on the image."""
    draw = ImageDraw.Draw(img)

    # Locate the hottest pixel for the reticle
    max_index = np.argmax(frame_data)
    max_row, max_col = divmod(max_index, frame_data.shape[1])
    center_x = (max_col + 0.5) * scale_factor
    center_y = (max_row + 0.5) * scale_factor
    reticle_radius = 9

    # Draw crosshairs and reticle on the hottest pixel
    draw.line(
        [(center_x, center_y - reticle_radius), (center_x, center_y + reticle_radius)],
        fill="red",
        width=1
    )
    draw.line(
        [(center_x - reticle_radius, center_y), (center_x + reticle_radius, center_y)],
        fill="red",
        width=1
    )
    draw.ellipse(
        [(center_x - reticle_radius + 2, center_y - reticle_radius + 2),
         (center_x + reticle_radius - 2, center_y + reticle_radius - 2)],
        outline="red",
        width=1
    )

    # Draw the scale bar with shadows
    bar_width = 10
    bar_height = img.height - 20
    bar_x = img.width - bar_width - 10
    bar_y = 10
    draw_scale_bar_with_shadow(img, bar_x, bar_y, bar_width, bar_height, min_value, max_value, avg_value, font)

    # Draw the highest temperature text
    text = f"{frame_data[max_row, max_col]:.1f}°"
    if max_row >= (img.height // scale_factor) - 3:
        # If the reticle is in the bottom three rows, move the text above the reticle
        text_y = max(center_y - 50, 0)
    else:
        # Otherwise, place the text below the reticle
        text_y = min(center_y + reticle_radius, img.height)
    text_x = min(max(center_x, 0), img.width - 120)

    # Draw the temperature text with shadow
    draw_text_with_shadow(img, text_x, text_y, text, font)

def draw_text_with_shadow(img, text_x, text_y, text, font):
    """Draw text with both a black border and a semi-transparent shadow."""
    shadow_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))  # Transparent RGBA layer
    shadow_draw = ImageDraw.Draw(shadow_layer)

    # Define shadow properties
    shadow_offset = 5  # Offset for the shadow
    shadow_color = (0, 0, 0, 100)  # Semi-transparent black

    # Draw the semi-transparent shadow
    shadow_draw.text(
        (text_x + shadow_offset, text_y + shadow_offset),
        text,
        font=font,
        fill=shadow_color
    )

    # Add the shadow layer to the main image
    img_rgba = img.convert("RGBA")
    combined = Image.alpha_composite(img_rgba, shadow_layer)

    # Convert back to RGB (to remove the alpha channel)
    img_rgb = combined.convert("RGB")
    img.paste(img_rgb)

    # Reinitialize ImageDraw for drawing on the combined image
    draw = ImageDraw.Draw(img)

    # Draw the black border
    border_offset = 2  # Border thickness
    for dx in range(-border_offset, border_offset + 1):
        for dy in range(-border_offset, border_offset + 1):
            if dx != 0 or dy != 0:
                draw.text((text_x + dx, text_y + dy), text, fill="black", font=font)

    # Draw the main text (white) in the center
    draw.text((text_x, text_y), text, fill="white", font=font)

def draw_scale_bar_with_shadow(img, bar_x, bar_y, bar_width, bar_height, min_value, max_value, avg_value, font):
    """Draw the scale bar with a shadow and gradient."""
    shadow_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))  # Transparent RGBA layer
    shadow_draw = ImageDraw.Draw(shadow_layer)

    shadow_offset = 5  # Offset for the shadow
    shadow_color = (0, 0, 0, 100)  # Semi-transparent black

    # Draw the shadow for the scale bar
    shadow_draw.rectangle(
        [bar_x + shadow_offset, bar_y + shadow_offset, bar_x + bar_width + shadow_offset, bar_y + bar_height + shadow_offset],
        fill=shadow_color
    )

    # Add the shadow layer to the main image
    img_rgba = img.convert("RGBA")
    combined = Image.alpha_composite(img_rgba, shadow_layer)

    # Convert back to RGB (to remove the alpha channel)
    img_rgb = combined.convert("RGB")
    img.paste(img_rgb)

    draw = ImageDraw.Draw(img)

    # Draw gradient on scale bar (from bottom to top, black to white)
    for i in range(bar_height):
        color_value = min_value + (max_value - min_value) * ((bar_height - i - 1) / bar_height)
        color = map_to_color(color_value, min_value, max_value)
        draw.line([(bar_x, bar_y + i), (bar_x + bar_width, bar_y + i)], fill=color)

    # Draw min, max, and average values to the left of the scale bar
    label_x = bar_x - 95
    draw_text_with_shadow(img, label_x, bar_y, f"{max_value:.1f}°", font)
    draw_text_with_shadow(img, label_x, bar_y + bar_height - 40, f"{min_value:.1f}°", font)
    draw_text_with_shadow(img, label_x, (bar_y + bar_height) // 2, f"{avg_value:.1f}°", font)