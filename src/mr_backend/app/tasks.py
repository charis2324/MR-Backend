from datetime import timedelta
from uuid import uuid4

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import Response, FileResponse, StreamingResponse

from mr_backend.database.db_manager import (
    add_task,
    get_actual_durations,
    get_trimesh,
    get_task_status,
    get_waiting_tasks_count,
    get_preview_status,
    get_preview,
)

from ..state import inference_thread_busy
from .models import (
    GenerationTaskRequest,
    GenerationTaskResponse,
    TaskStatus,
    TaskStatusEnum,
)
from mr_backend.shape_inference.inference_server import export_trimesh_to_obj_str
from .utils import get_duration_estimation
from gzip import decompress
from trimesh import Trimesh
from tempfile import TemporaryDirectory
from zipfile import ZipFile
import os
from io import BytesIO
from time import time

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


@router.get("/tasks/{task_id}/status", response_model=TaskStatus)
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
    start = time()
    status = get_task_status(task_id)
    if status == TaskStatusEnum.completed:
        trimesh = get_trimesh(task_id)
        with TemporaryDirectory() as temp_dir:
            obj_path = os.path.join(temp_dir, f"{task_id}.obj")
            if hasattr(trimesh.visual, "vertex_colors"):
                trimesh.export(obj_path)
            else:
                obj_str = export_trimesh_to_obj_str(trimesh)
                with open(obj_path, "w") as f:
                    f.write(obj_str)
            with TemporaryDirectory() as zip_dir:
                zip_path = os.path.join(zip_dir, f"{task_id}.zip")
                with ZipFile(zip_path, "w") as zipf:
                    for filename in os.listdir(temp_dir):
                        file_path = os.path.join(temp_dir, filename)
                        if os.path.isfile(file_path):
                            zipf.write(file_path, arcname=filename)
                with open(zip_path, "rb") as f:
                    zip_bytes = f.read()
        print(f"time: {time()-start}")
        return StreamingResponse(
            BytesIO(zip_bytes),
            media_type="application/zip",
        )
    else:
        raise HTTPException(
            status_code=400,
            detail="Results not ready. Please check the task's status before retrieving the results.",
        )


@router.get("/tasks/{task_id}/preview")
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
