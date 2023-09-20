from datetime import timedelta
from time import sleep, time

import numpy as np
import torch
from diffusers import DiffusionPipeline

from mr_backend.app.models import TaskStatusEnum
from mr_backend.database.db_manager import (
    create_model_preview,
    finish_task,
    get_earliest_waiting_task,
    store_obj_file,
    update_task_status,
)
from mr_backend.state import inference_thread_busy, inference_thread_ready
from mr_backend.model_preview.render_preview import parse_lines
from .clean_mesh import clean_mesh


def export_ai_model_output_to_obj_str(mesh):
    verts = mesh.verts.detach().cpu().numpy()
    faces = mesh.faces.cpu().numpy()

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
            num_inference_steps=64,
            frame_size=256,
            output_type="mesh",
        ).images
        # Save to str
        return export_ai_model_output_to_obj_str(images[0])

    print("Running inference thread...")
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
            obj_str = generateWithPipe(task.prompt, task.guidance_scale)

            mesh_dict = parse_lines(obj_str.split("\n"))
            cleaned_mesh = clean_mesh(mesh_dict)
            obj_str = export_trimesh_to_obj_str(cleaned_mesh)

            store_obj_file(uuid=task.task_id, obj_str=obj_str)
            finish_task(task.task_id, timedelta(seconds=time() - start_time))
            create_model_preview(task.task_id)
        except Exception as e:
            print(f"Error during inference for task {task.task_id}: {str(e)}")
            update_task_status(task.task_id, TaskStatusEnum.failed)
        inference_thread_busy.clear()
