from queue import Queue
from threading import Thread
from time import sleep, time
import torch
from diffusers import DiffusionPipeline
from diffusers.utils import export_to_obj
from uuid import uuid4
from ..state import (
    task_queue,
    waiting_tasks,
    completed_tasks,
    failed_tasks,
    durations,
    inference_thread_busy,
    inference_thread_ready,
)


# Logic goes here
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
        task = task_queue.get()
        inference_thread_busy.set()
        start_time = time()
        try:
            generateWithPipe(task.prompt, task.guidance_scale, task.task_id)
            completed_tasks.add(task.task_id)
            durations.append(time() - start_time)
            print(durations)
        except Exception as e:
            print(f"Error during inference for task {task.task_id}: {str(e)}")
            failed_tasks.add(task.task_id)

        waiting_tasks.remove(task.task_id)
        task_queue.task_done()
        inference_thread_busy.clear()
