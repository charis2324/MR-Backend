from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import FileResponse
from uuid import uuid4
from ..state import (
    task_queue,
    waiting_tasks,
    completed_tasks,
    failed_tasks,
    durations,
    inference_thread_busy,
)
from .models import GenerationTask, GenerationTaskRequest, TaskStatus, TaskStatusEnum
from .utils import get_duration_estimation

router = APIRouter()


@router.post("/generate", response_model=GenerationTask)
def onReceivedGenerationRequest(request_body: GenerationTaskRequest = Body(...)):
    prompt = request_body.prompt
    guidance_scale = request_body.guidance_scale
    task = GenerationTask(
        task_id=str(uuid4()),
        prompt=prompt,
        guidance_scale=guidance_scale,
        estimated_duration=get_duration_estimation(
            durations, task_queue.qsize(), inference_thread_busy
        ),
    )
    task_queue.put(task)
    waiting_tasks.add(task.task_id)
    return task


@router.get("/task/{task_id}/status", response_model=TaskStatus)
def get_task_status(task_id: str):
    if task_id in completed_tasks:
        return TaskStatus(
            task_id=task_id,
            status=TaskStatusEnum.completed,
            message="Your task has been completed. You may now retrieve the results.",
        )
    if task_id in waiting_tasks:
        return TaskStatusEnum(
            task_id=task_id,
            status=TaskStatusEnum.processing,
            message="Your task is still being processed.",
        )
    if task_id in failed_tasks:
        return TaskStatus(
            task_id=task_id,
            status=TaskStatusEnum.failed,
            message="Your task failed.",
        )
    raise HTTPException(
        status_code=400,
        detail="Invalid task ID. Please check your task ID.",
    )


@router.get("/tasks/{task_id}/results")
def get_task_results(task_id: str):
    if task_id in completed_tasks:
        fname = f"{task_id}.obj"
        return FileResponse(fname)
    else:
        raise HTTPException(
            status_code=400,
            detail="Results not ready. Please check the task's status before retrieving the results.",
        )
