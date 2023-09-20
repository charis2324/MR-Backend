import numpy as np
import pygame
from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *
from pygame.locals import *


def draw(mesh):
    glEnable(GL_COLOR_MATERIAL)
    glEnable(GL_DEPTH_TEST)
    glBegin(GL_TRIANGLES)
    for i in range(len(mesh["triangles"])):
        glColor3fv(mesh["colors"][mesh["triangles"][i][0]])
        for j in range(3):
            glVertex3fv(mesh["vertices"][mesh["triangles"][i][j]])
    glEnd()


def render_preview(mesh_dict):
    pygame.init()
    display = (800, 600)
    pygame.display.set_mode(display, DOUBLEBUF | OPENGL | HWSURFACE)
    gluPerspective(45, (display[0] / display[1]), 0.1, 50.0)
    glTranslatef(0.0, 0.0, -5)
    gluLookAt(0, 1, 1, 0, 0, 0, 0, -1, 0)

    mesh_list = glGenLists(1)
    glNewList(mesh_list, GL_COMPILE)
    draw(mesh_dict)
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
