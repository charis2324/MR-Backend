import io
from gzip import compress

import imageio
import numpy as np

from mr_backend.app.models import TaskStatusEnum
from mr_backend.database.db_manager import (
    finish_model_preview,
    get_earliest_waiting_preview_uuid,
    get_trimesh,
    update_model_preview_status,
)
from mr_backend.model_preview.offscreen_renderer import render_preview
from mr_backend.shape_inference.clean_mesh import merge_geometry


def parse_lines(lines):
    colors = []
    vertices = []
    triangles = []

    for line in lines:
        data = line.split()
        if data[0] == "v":
            vertices.append([float(data[1]), float(data[2]), float(data[3])])
            colors.append([float(data[4]), float(data[5]), float(data[6])])
        elif data[0] == "f":
            triangles.append([int(data[1]) - 1, int(data[2]) - 1, int(data[3]) - 1])

    mesh_dict = {
        "vertices": np.array(vertices, dtype=np.float32),
        "triangles": np.array(triangles, dtype=np.int32),
        "colors": np.array(colors, dtype=np.float32),
    }
    return mesh_dict


def render_3d_object(file_or_bytes_or_str_or_trimesh):
    if isinstance(file_or_bytes_or_str_or_trimesh, io.BytesIO):
        lines = file_or_bytes_or_str_or_trimesh.getvalue().decode().split("\n")
        output = io.BytesIO()
    elif isinstance(file_or_bytes_or_str_or_trimesh, str):
        if "\n" in file_or_bytes_or_str_or_trimesh:
            # It's a string of file content
            lines = file_or_bytes_or_str_or_trimesh.split("\n")
            output = io.BytesIO()
        else:
            # It's a file path
            with open(file_or_bytes_or_str_or_trimesh, "r") as file:
                lines = file.readlines()
            output = file_or_bytes_or_str_or_trimesh.replace(".obj", ".gif")
    else:
        raise TypeError(
            "Input should be a file path, a string of file content, or a BytesIO object."
        )

    mesh = parse_lines(lines)
    frame_images = render_preview(mesh)
    imageio.mimsave(output, frame_images, format="GIF", duration=33, loop=0)
    if isinstance(output, io.BytesIO):
        output.seek(0)
    return output


def preview_generation_thread():
    while True:
        uuid = get_earliest_waiting_preview_uuid()
        if uuid is not None:
            update_model_preview_status(uuid, TaskStatusEnum.processing)
            try:
                # need to merge the meshes from scene.
                trimesh = merge_geometry(get_trimesh(uuid))
                frame_images = render_preview(trimesh)
                output = io.BytesIO()
                imageio.mimsave(output, frame_images, format="GIF", duration=33, loop=0)
                output.seek(0)
                gif_bytes = output.getvalue()
                gif_bytes_compressed = compress(gif_bytes)
                finish_model_preview(uuid, "gif", gif_bytes_compressed)
            except Exception as e:
                update_model_preview_status(uuid, TaskStatusEnum.failed)
