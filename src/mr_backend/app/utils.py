import io
import random
import string

import cv2
import numpy as np
from PIL import Image


def get_duration_estimation(
    durations: list,
    task_queue_length: int,
    is_busy: bool,
    period=5,
    default_duration=20,
):
    if not durations:  # if durations list is empty
        duration = default_duration
    elif len(durations) < period:  # if there are less than 'period' durations
        duration = sum(durations) / len(durations)
    else:  # if there are 'period' or more durations
        duration = sum(durations[-period:]) / period
    n_tasks = task_queue_length + 2 if is_busy.is_set() else task_queue_length + 1
    return duration * n_tasks


def generate_random_string(length):
    # Define the characters that will be used
    characters = string.ascii_letters + string.digits

    # Generate the random string
    random_string = "".join(random.choice(characters) for i in range(length))

    return random_string


def extract_frame_from_bytes(gif_bytes, frame_index):
    gif_file = io.BytesIO(gif_bytes)
    frame = Image.open(gif_file)
    try:
        frame.seek(frame_index)
    except EOFError:
        raise ValueError(f"Frame {frame_index} not found")
    frame.convert("RGBA")
    # Create a BytesIO object, save the PNG in it, get the byte array from it
    png_bytes = io.BytesIO()
    frame.save(png_bytes, "PNG")
    png_bytes.seek(0)
    return png_bytes.read()


def extract_png_from_gif_bytes(gif_bytes, frame_index):
    gif_file = io.BytesIO(gif_bytes)
    frame = Image.open(gif_file)

    try:
        frame.seek(frame_index)
    except EOFError:
        raise ValueError(f"Frame {frame_index} not found")
    # Create a BytesIO object, save the PNG in it, get the byte array from it
    frame_bytes = io.BytesIO()
    frame.save(
        frame_bytes,
        "PNG",
    )
    frame_bytes.seek(0)
    png = Image.open(frame_bytes)
    png_rgba = png.convert("RGBA")

    return png_rgba


def image_to_bytes(image: Image):
    # image.save("debug.png", "PNG")
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    buffer.seek(0)
    return buffer.getvalue()


def count_transparent_pixels(image_array):
    transparent_pixels = image_array[:, :, 3] == 0
    count = np.count_nonzero(transparent_pixels)
    return count
