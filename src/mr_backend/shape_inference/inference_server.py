import logging
from datetime import timedelta
from time import sleep, time

import numpy as np
import torch
from diffusers import DiffusionPipeline

from mr_backend.app.controller import polling_controller_sessions
from mr_backend.app.controller_event import PollingImportFurnitureEvent
from mr_backend.app.models import TaskStatusEnum
from mr_backend.database.db_manager import (
    create_model_info_from_task,
    create_model_preview,
    finish_task,
    get_earliest_waiting_task,
    get_task_user_uuid,
    store_trimesh,
    update_task_status,
)
from mr_backend.model_preview.render_preview import parse_lines
from mr_backend.state import inference_thread_busy, inference_thread_ready

from .clean_mesh import clean_mesh, split_model_output


def export_ai_model_output_to_obj_str(mesh):
    verts = mesh.verts.detach().cpu().numpy()
    faces = mesh.faces.cpu().numpy()
    print(f"verts: {verts.shape}")
    print(f"verts: {faces.shape}")
    vertex_colors = np.stack(
        [mesh.vertex_channels[x].detach().cpu().numpy() for x in "RGB"], axis=1
    )
    vertices = [
        "{} {} {} {} {} {}".format(*coord, *color)
        for coord, color in zip(verts.tolist(), vertex_colors.tolist())
    ]

    faces = [
        "f {} {} {}".format(str(tri[0] + 1), str(tri[1] + 1), str(tri[2] + 1))
        for tri in faces.tolist()
    ]

    combined_data = ["v " + vertex for vertex in vertices] + faces
    return "\n".join(combined_data)


def export_trimesh_to_obj_str(mesh):
    verts = mesh.vertices
    faces = mesh.faces

    # trimesh doesn't natively support vertex colors, so you'll need to check if they exist
    if hasattr(mesh.visual, "vertex_colors"):
        vertex_colors = (
            mesh.visual.vertex_colors[:, :3] / 255.0
        )  # normalize colors to [0, 1]
    else:
        # if there are no vertex colors, default to white for all vertices
        vertex_colors = np.ones((verts.shape[0], 3))

    vertices = [
        "{} {} {} {} {} {}".format(*coord, *color)
        for coord, color in zip(verts.tolist(), vertex_colors.tolist())
    ]

    faces = [
        "f {} {} {}".format(str(tri[0] + 1), str(tri[1] + 1), str(tri[2] + 1))
        for tri in faces.tolist()
    ]

    combined_data = ["v " + vertex for vertex in vertices] + faces
    return "\n".join(combined_data)


def inference_thread():
    def generateWithPipe(prompt: str, guidance_scale: float):
        images = pipe(
            prompt,
            guidance_scale=guidance_scale,
            num_inference_steps=100,
            frame_size=256,
            output_type="mesh",
        ).images
        # Save to str
        return images[0]

    error_logger = logging.getLogger("uvicorn.error")
    # print("Running inference thread...")
    error_logger.info("Running inference thread...")
    # Load the model
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    repo = "openai/shap-e"
    pipe = DiffusionPipeline.from_pretrained(
        repo, torch_dtype=torch.float16, variant="fp16"
    )
    pipe = pipe.to(device)
    inference_thread_ready.set()
    # Main worker loop
    while True:
        task = get_earliest_waiting_task()
        if not task:
            sleep(1)
            continue
        update_task_status(task.task_id, TaskStatusEnum.processing)
        inference_thread_busy.set()
        start_time = time()
        try:
            image = generateWithPipe(task.prompt, task.guidance_scale)
            verts, faces, colors = split_model_output(image)
            cleaned_mesh = clean_mesh(verts, faces, colors)
            store_trimesh(task.task_id, cleaned_mesh)
            finish_task(task.task_id, timedelta(seconds=time() - start_time))
            create_model_info_from_task(task.task_id)
            create_model_preview(task.task_id)
            # user_uuid = get_task_user_uuid(task.task_id)
            # if polling_controller_sessions.sessions.get(user_uuid, None) != None:
            #     event = PollingImportFurnitureEvent(furniture_uuid=task.task_id)
            #     polling_controller_sessions.sessions[user_uuid].add_event(event)
            #     error_logger.info(
            #         f"MR Session: {user_uuid} is active. New generated furniture pushed to MR."
            #     )
            # else:
            #     error_logger.info(f"MR Session: {user_uuid} is not currently active.")
        except Exception as e:
            print(f"Error during inference for task {task.task_id}: {str(e)}")
            update_task_status(task.task_id, TaskStatusEnum.failed)
        inference_thread_busy.clear()
