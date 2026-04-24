from __future__ import annotations

from collections import deque
from pathlib import Path
from statistics import median
from typing import BinaryIO

from PIL import Image, ImageChops, ImageFilter, ImageOps


MAX_PROCESSING_DIMENSION = 1600
CANVAS_SIZE = 1400
CANVAS_PADDING_RATIO = 0.08
BASE_BG_TOLERANCE = 68
NEAR_WHITE_THRESHOLD = 235
LOW_ALPHA_THRESHOLD = 10


def _resize_for_processing(image: Image.Image) -> Image.Image:
    longest_side = max(image.size)
    if longest_side <= MAX_PROCESSING_DIMENSION:
        return image

    scale = MAX_PROCESSING_DIMENSION / float(longest_side)
    new_size = (
        max(1, int(round(image.width * scale))),
        max(1, int(round(image.height * scale))),
    )
    return image.resize(new_size, Image.Resampling.LANCZOS)


def _open_rgba_image(source: str | Path | BinaryIO) -> Image.Image:
    with Image.open(source) as raw_image:
        image = ImageOps.exif_transpose(raw_image)
        image.load()
        return _resize_for_processing(image.convert("RGBA"))


def _sample_border_pixels(image: Image.Image) -> list[tuple[int, int, int, int]]:
    pixels = image.load()
    width, height = image.size
    border_pixels: list[tuple[int, int, int, int]] = []

    for x in range(width):
        border_pixels.append(pixels[x, 0])
        border_pixels.append(pixels[x, height - 1])

    for y in range(1, height - 1):
        border_pixels.append(pixels[0, y])
        border_pixels.append(pixels[width - 1, y])

    return border_pixels


def _estimate_border_reference(image: Image.Image) -> tuple[tuple[int, int, int], int]:
    border_pixels = [pixel for pixel in _sample_border_pixels(image) if pixel[3] > LOW_ALPHA_THRESHOLD]
    if not border_pixels:
        return (255, 255, 255), BASE_BG_TOLERANCE

    reference = tuple(int(median(pixel[channel] for pixel in border_pixels)) for channel in range(3))
    border_distances = [
        max(
            abs(pixel[0] - reference[0]),
            abs(pixel[1] - reference[1]),
            abs(pixel[2] - reference[2]),
        )
        for pixel in border_pixels
    ]
    adaptive_tolerance = min(96, max(BASE_BG_TOLERANCE, int(median(border_distances)) + 24))
    return reference, adaptive_tolerance


def _is_background_like(
    pixel: tuple[int, int, int, int],
    reference: tuple[int, int, int],
    tolerance: int,
) -> bool:
    red, green, blue, alpha = pixel
    if alpha <= LOW_ALPHA_THRESHOLD:
        return True

    max_channel_delta = max(abs(red - reference[0]), abs(green - reference[1]), abs(blue - reference[2]))
    if max_channel_delta <= tolerance:
        return True

    if min(red, green, blue) >= NEAR_WHITE_THRESHOLD and max(red, green, blue) - min(red, green, blue) <= 26:
        return True

    return False


def _build_background_mask(image: Image.Image) -> Image.Image:
    width, height = image.size
    pixels = image.load()
    reference, tolerance = _estimate_border_reference(image)
    visited = bytearray(width * height)
    background_mask = Image.new("L", (width, height), 255)
    background_pixels = background_mask.load()
    queue: deque[tuple[int, int]] = deque()

    def enqueue(x: int, y: int) -> None:
        index = y * width + x
        if visited[index]:
            return
        if not _is_background_like(pixels[x, y], reference, tolerance):
            return
        visited[index] = 1
        queue.append((x, y))

    for x in range(width):
        enqueue(x, 0)
        enqueue(x, height - 1)

    for y in range(height):
        enqueue(0, y)
        enqueue(width - 1, y)

    while queue:
        x, y = queue.popleft()
        background_pixels[x, y] = 0

        if x > 0:
            enqueue(x - 1, y)
        if x + 1 < width:
            enqueue(x + 1, y)
        if y > 0:
            enqueue(x, y - 1)
        if y + 1 < height:
            enqueue(x, y + 1)

    return background_mask.filter(ImageFilter.GaussianBlur(radius=1.2))


def _normalize_cutout_canvas(image: Image.Image) -> Image.Image:
    alpha = image.getchannel("A")
    bbox = alpha.getbbox()
    if not bbox:
        bbox = (0, 0, image.width, image.height)

    cropped = image.crop(bbox)
    canvas = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), (0, 0, 0, 0))
    inner_box = int(round(CANVAS_SIZE * (1 - CANVAS_PADDING_RATIO * 2)))
    scale = min(inner_box / cropped.width, inner_box / cropped.height)
    resized = cropped.resize(
        (
            max(1, int(round(cropped.width * scale))),
            max(1, int(round(cropped.height * scale))),
        ),
        Image.Resampling.LANCZOS,
    )

    offset = (
        (CANVAS_SIZE - resized.width) // 2,
        (CANVAS_SIZE - resized.height) // 2,
    )
    canvas.alpha_composite(resized, offset)
    return canvas


def build_item_cutout(source: str | Path | BinaryIO) -> Image.Image:
    image = _open_rgba_image(source)
    background_mask = _build_background_mask(image)
    combined_alpha = ImageChops.multiply(image.getchannel("A"), background_mask)
    image.putalpha(combined_alpha)
    return _normalize_cutout_canvas(image)


def build_processed_item_filename(original_name: str) -> str:
    stem = Path(original_name).stem or "item"
    safe_stem = "".join(character if character.isalnum() or character in {"-", "_"} else "-" for character in stem)
    safe_stem = safe_stem.strip("-_") or "item"
    return f"{safe_stem}.png"
