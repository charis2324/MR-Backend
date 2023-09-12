from datetime import timedelta
from time import time, sleep

import torch
from diffusers import DiffusionPipeline
from diffusers.utils import export_to_obj

from mr_backend.app.models import TaskStatusEnum
from mr_backend.database.db_manager import (
    finish_task,
    get_earliest_waiting_task,
    update_task_status,
)
from mr_backend.state import inference_thread_busy, inference_thread_ready


def inference_thread():
    def generateWithPipe(prompt: str, guidance_scale: float, task_id: str):
        images = pipe(
            prompt,
            guidance_scale=guidance_scale,
            num_inference_steps=64,
            frame_size=256,
            output_type="mesh",
        ).images
        fname = f"{task_id}.obj"
        # Save to file
        export_to_obj(images[0], fname)

    print("Running inference thread.")
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
            generateWithPipe(task.prompt, task.guidance_scale, task.task_id)
            finish_task(task.task_id, timedelta(seconds=time() - start_time))

        except Exception as e:
            print(f"Error during inference for task {task.task_id}: {str(e)}")
            update_task_status(task.task_id, TaskStatusEnum.failed)
        inference_thread_busy.clear()
