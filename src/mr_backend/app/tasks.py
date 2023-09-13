from datetime import timedelta
from uuid import uuid4

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import FileResponse, Response

from mr_backend.database.db_manager import (
    add_task,
    get_actual_durations,
    get_task_status,
    get_waiting_tasks_count,
    get_obj_file,
)

from ..state import inference_thread_busy
from .models import (
    GenerationTask,
    GenerationTaskRequest,
    GenerationTaskResponse,
    TaskStatus,
    TaskStatusEnum,
)
from .utils import get_duration_estimation

router = APIRouter()


@router.post("/generate", response_model=GenerationTaskResponse)
def receive_generation_equest(request_body: GenerationTaskRequest = Body(...)):
    prompt = request_body.prompt
    guidance_scale = request_body.guidance_scale
    task_id = str(uuid4())
    estimated_duration = timedelta(
        seconds=get_duration_estimation(
            get_actual_durations(5), get_waiting_tasks_count(), inference_thread_busy
        )
    )
    add_task(task_id, prompt, guidance_scale, estimated_duration)
    print(estimated_duration)
    return GenerationTaskResponse(
        task_id=task_id, estimated_duration=estimated_duration
    )


@router.get("/task/{task_id}/status", response_model=TaskStatus)
def read_task_status(task_id: str):
    status = get_task_status(task_id)
    if status == TaskStatusEnum.completed:
        return TaskStatus(
            task_id=task_id,
            status=TaskStatusEnum.completed,
            message="Your task has been completed. You may now retrieve the results.",
        )
    if status == TaskStatusEnum.waiting or status == TaskStatusEnum.processing:
        return TaskStatus(
            task_id=task_id,
            status=TaskStatusEnum.processing,
            message="Your task is still being processed.",
        )
    if status == TaskStatusEnum.failed:
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
    status = get_task_status(task_id)
    if status == TaskStatusEnum.completed:
        obj_file_str = get_obj_file(task_id)
        return Response(content=obj_file_str, media_type="text/plain")
    else:
        raise HTTPException(
            status_code=400,
            detail="Results not ready. Please check the task's status before retrieving the results.",
        )
