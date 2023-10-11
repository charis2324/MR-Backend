import io
import math
import tempfile
from gzip import decompress
from pathlib import Path
from typing import Annotated, List, Optional
from uuid import uuid4

import imageio
import trimesh
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from fastapi.responses import StreamingResponse
from icecream import ic

from mr_backend.app.auth import get_current_user
from mr_backend.app.utils import extract_frame_from_bytes
from mr_backend.database.db_manager import (
    create_model_info,
    create_model_preview,
    get_model_info_by_user,
    get_model_info_by_uuid,
    get_model_preview_status,
    get_models_info,
    get_preview,
    get_preview_status,
    get_trimesh,
    store_trimesh,
    update_model_info_by_uuid,
)
from mr_backend.model_preview.offscreen_renderer import render_preview
from mr_backend.shape_inference.clean_mesh import (
    merge_geometry,
    rotate_all_geometries,
    rotate_mesh,
)
from mr_backend.shape_inference.inference_server import export_trimesh_to_obj_str

from .models import (
    FurnitureInfoBase,
    FurnitureInfos,
    ModelInfoUpdate,
    TaskStatus,
    TaskStatusEnum,
    UserInDB,
)

furniture_router = APIRouter(prefix="/furnitures")


@furniture_router.get("/info", response_model=FurnitureInfos)
def read_furniture_info(skip: int, limit: int):
    furniture_infos, count = get_models_info(skip, limit)
    furniture_infos = [
        FurnitureInfoBase.model_validate(info, from_attributes=True)
        for info in furniture_infos
    ]
    return FurnitureInfos(furniture_infos=furniture_infos, total_furniture_count=count)


@furniture_router.post("/upload", response_model=FurnitureInfoBase)
async def upload_furniture(
    current_user: Annotated[UserInDB, Depends(get_current_user)],
    files: List[UploadFile] = File(...),
):
    httpExecption = HTTPException(status_code=400, detail="Incorrect file compositions")
    file_type_allowance = {".obj": 1, ".mtl": 1}
    obj_path = None
    with tempfile.TemporaryDirectory() as temp_dir:
        for file in files:
            path = Path(temp_dir) / file.filename
            if file_type_allowance.get(path.suffix, 0) == 0:
                raise httpExecption
            file_type_allowance[path.suffix] -= 1
            if path.suffix == ".obj":
                obj_path = path
            contents = await file.read()
            with open(path, "wb") as f:
                f.write(contents)

        if obj_path is None:
            raise httpExecption
        try:
            scene = trimesh.load(obj_path, force="scene")
            rotate_all_geometries(scene)
            furniture_uuid = str(uuid4())
            furniture_info = create_model_info(
                furniture_uuid, current_user.uuid, current_user.username
            )
            store_trimesh(furniture_uuid, scene)
            create_model_preview(furniture_uuid)
            furniture_info_dict = furniture_info.__dict__
            furniture_info_dict["username"] = current_user.username
            furniture_info_dict.pop("_sa_instance_state", None)
            return FurnitureInfoBase(**furniture_info_dict)
        except Exception:
            httpExecption.detail = "Model parsing failed."
            raise httpExecption


@furniture_router.get("/{uuid}/info")
def read_furnitures_info_by_uuid(uuid: str):
    model_info = get_model_info_by_uuid(uuid)
    if model_info is None:
        raise HTTPException(status_code=404, detail="Furniture not found")
    furniture_info_dict = model_info.__dict__
    furniture_info_dict["username"] = ""
    furniture_info_dict.pop("_sa_instance_state", None)
    return FurnitureInfoBase(**furniture_info_dict)


@furniture_router.put("/{uuid}/info")
def update_furniture_info(
    current_user: Annotated[UserInDB, Depends(get_current_user)],
    uuid: str,
    update_data: ModelInfoUpdate,
):
    user_uuid = current_user.uuid
    is_success = update_model_info_by_uuid(
        uuid,
        user_uuid,
        update_data.name,
        update_data.description,
        update_data.scale_type,
        update_data.scale_x,
        update_data.scale_y,
        update_data.scale_z,
    )
    if not is_success:
        raise HTTPException(status_code=400, detail="Failed to update furniture info")
    new_model_info = get_model_info_by_uuid(uuid)
    furniture_info_dict = new_model_info.__dict__
    furniture_info_dict["username"] = ""
    print(furniture_info_dict)
    furniture_info_dict.pop("_sa_instance_state", None)
    return FurnitureInfoBase(**furniture_info_dict)


@furniture_router.get("/{uuid}")
def get_furniture_model(uuid: str):
    # it is actually a Scene
    scene = get_trimesh(uuid)
    if scene is None:
        raise HTTPException(
            status_code=404,
            detail="Furnture model not found.",
        )
    trimesh = merge_geometry(scene)
    obj_str = export_trimesh_to_obj_str(trimesh)
    obj_bytes = io.BytesIO(obj_str.encode())
    return StreamingResponse(
        obj_bytes,
        media_type="application/obj",
        headers={
            "Content-Disposition": f"attachment; filename={uuid}.obj",
        },
    )


@furniture_router.get("/{uuid}/preview")
def get_furniture_preview(task_id: str, return_png: Optional[bool] = None):
    status = get_preview_status(task_id)
    if status == TaskStatusEnum.completed:
        compress_preview, file_type = get_preview(task_id)
        decompress_preview = decompress(compress_preview)
        if return_png:
            try:
                decompress_preview = extract_frame_from_bytes(decompress_preview, 0)
                file_type = "png"
            except:
                raise HTTPException(
                    status_code=400,
                    detail="Failed to convert preview to PNG.",
                )
        return Response(content=decompress_preview, media_type=f"image/{file_type}")
    else:
        raise HTTPException(
            status_code=400,
            detail="Results not ready. Please check the task's status before retrieving the results.",
        )


@furniture_router.get("/{uuid}/preview/status", response_model=TaskStatus)
def read_furniture_preview_status(task_id: str):
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
