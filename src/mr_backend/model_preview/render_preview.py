import io
from gzip import compress

import imageio
import numpy as np
import pygame
from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *
from pygame.locals import *

from mr_backend.app.models import TaskStatusEnum
from mr_backend.database.db_manager import (
    finish_model_preview,
    get_earliest_waiting_preview_uuid,
    get_obj_file,
    update_model_preview_status,
)


def draw(mesh):
    glEnable(GL_COLOR_MATERIAL)
    glEnable(GL_DEPTH_TEST)
    glBegin(GL_TRIANGLES)
    for i in range(len(mesh["triangles"])):
        glColor3fv(mesh["colors"][mesh["triangles"][i][0]])
        for j in range(3):
            glVertex3fv(mesh["vertices"][mesh["triangles"][i][j]])
    glEnd()


def render_loop(mesh):
    pygame.init()
    display = (800, 600)
    pygame.display.set_mode(display, DOUBLEBUF | OPENGL | HWSURFACE)
    gluPerspective(45, (display[0] / display[1]), 0.1, 50.0)
    glTranslatef(0.0, 0.0, -5)
    gluLookAt(0, 1, 1, 0, 0, 0, 0, -1, 0)

    mesh_list = glGenLists(1)
    glNewList(mesh_list, GL_COMPILE)
    draw(mesh)
    glEndList()

    frame_images = []  # List to store each captured frame
    num_frames = 180  # Number of frames to capture for the GIF
    rotation_per_frame = 2
    for _ in range(num_frames):
        # Rotate the model
        glRotatef(rotation_per_frame, 0, 0, 1)
        glClearColor(1.0, 1.0, 1.0, 0.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        # Draw the model
        glCallList(mesh_list)
        pygame.display.flip()
        glReadBuffer(GL_FRONT)
        pixels = glReadPixels(0, 0, display[0], display[1], GL_RGB, GL_UNSIGNED_BYTE)
        pixels_as_array = np.frombuffer(pixels, dtype=np.uint8).reshape(
            display[1], display[0], 3
        )
        flipped_pixels = np.flipud(pixels_as_array)
        frame_images.append(flipped_pixels)

    pygame.quit()
    return frame_images


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

    mesh = {
        "vertices": np.array(vertices, dtype=np.float32),
        "triangles": np.array(triangles, dtype=np.int32),
        "colors": np.array(colors, dtype=np.float32),
    }
    return mesh


def render_3d_object(file_or_bytes_or_str):
    if isinstance(file_or_bytes_or_str, io.BytesIO):
        lines = file_or_bytes_or_str.getvalue().decode().split("\n")
        output = io.BytesIO()
    elif isinstance(file_or_bytes_or_str, str):
        if "\n" in file_or_bytes_or_str:
            # It's a string of file content
            lines = file_or_bytes_or_str.split("\n")
            output = io.BytesIO()
        else:
            # It's a file path
            with open(file_or_bytes_or_str, "r") as file:
                lines = file.readlines()
            output = file_or_bytes_or_str.replace(".obj", ".gif")
    else:
        raise TypeError(
            "Input should be a file path, a string of file content, or a BytesIO object."
        )

    mesh = parse_lines(lines)
    frame_images = render_loop(mesh)
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
                obj_str = get_obj_file(uuid)
                gif_bytes = render_3d_object(obj_str).getvalue()
                gif_bytes_compressed = compress(gif_bytes)
                finish_model_preview(uuid, "gif", gif_bytes_compressed)
            except Exception as e:
                update_model_preview_status(uuid, TaskStatusEnum.failed)
