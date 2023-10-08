import os
from datetime import timedelta
from gzip import decompress
from io import BytesIO
from tempfile import TemporaryDirectory
from time import time
from typing import Annotated
from uuid import uuid4
from zipfile import ZipFile

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import Response, StreamingResponse

from mr_backend.database.db_manager import (
    add_task,
    get_actual_durations,
    get_model_preview_status,
    get_preview,
    get_preview_status,
    get_task_status,
    get_task_user_uuid,
    get_trimesh,
    get_waiting_tasks_count,
)
from mr_backend.shape_inference.clean_mesh import merge_geometry
from mr_backend.shape_inference.inference_server import export_trimesh_to_obj_str

from ..state import inference_thread_busy
from .auth import get_current_user
from .models import (
    GenerationTaskRequest,
    GenerationTaskResponse,
    TaskStatus,
    TaskStatusEnum,
    UserInDB,
)
from .utils import get_duration_estimation

task_router = APIRouter()


@task_router.post("/generate", response_model=GenerationTaskResponse)
def receive_generation_equest(
    current_user: Annotated[UserInDB, Depends(get_current_user)],
    request_body: GenerationTaskRequest = Body(...),
):
    prompt = request_body.prompt
    guidance_scale = request_body.guidance_scale
    task_id = str(uuid4())
    estimated_duration = timedelta(
        seconds=get_duration_estimation(
            get_actual_durations(5), get_waiting_tasks_count(), inference_thread_busy
        )
    )
    add_task(task_id, current_user.uuid, prompt, guidance_scale, estimated_duration)
    print(estimated_duration)
    return GenerationTaskResponse(
        task_id=task_id, estimated_duration=estimated_duration
    )


@task_router.get("/tasks/{task_id}/result/status", response_model=TaskStatus)
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


@task_router.get("/tasks/{task_id}/result")
def get_task_results(task_id: str):
    status = get_task_status(task_id)
    if status == TaskStatusEnum.completed:
        # it is actually a Scene
        trimesh = merge_geometry(get_trimesh(task_id))
        obj_str = export_trimesh_to_obj_str(trimesh)
        obj_bytes = BytesIO(obj_str.encode())
        return StreamingResponse(
            obj_bytes,
            media_type="application/obj",
            headers={
                "Content-Disposition": f"attachment; filename={task_id}.obj",
            },
        )
    else:
        raise HTTPException(
            status_code=400,
            detail="Results not ready. Please check the task's status before retrieving the results.",
        )


@task_router.get("/tasks/{task_id}/preview/status", response_model=TaskStatus)
def read_task_preview_status(task_id: str):
    status = get_model_preview_status(task_id)
    if status == TaskStatusEnum.completed:
        return TaskStatus(
            task_id=task_id,
            status=TaskStatusEnum.completed,
            message="Your task preview has been completed. You may now retrieve the results.",
        )
    if status == TaskStatusEnum.waiting or status == TaskStatusEnum.processing:
        return TaskStatus(
            task_id=task_id,
            status=TaskStatusEnum.processing,
            message="Your task preview is still being processed.",
        )
    if status == TaskStatusEnum.failed:
        return TaskStatus(
            task_id=task_id,
            status=TaskStatusEnum.failed,
            message="Your task preview failed.",
        )
    raise HTTPException(
        status_code=400,
        detail="Invalid task ID. Please check your task ID.",
    )


@task_router.get("/tasks/{task_id}/preview")
def get_task_results(task_id: str):
    status = get_preview_status(task_id)
    if status == TaskStatusEnum.completed:
        compress_preview, file_type = get_preview(task_id)
        decompress_preview = decompress(compress_preview)
        return Response(content=decompress_preview, media_type=f"image/{file_type}")
    else:
        raise HTTPException(
            status_code=400,
            detail="Results not ready. Please check the task's status before retrieving the results.",
        )
