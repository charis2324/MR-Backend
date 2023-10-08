import io
import math
import tempfile
from pathlib import Path
from typing import Annotated, List
from uuid import uuid4

import imageio
import trimesh
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from icecream import ic

from mr_backend.app.auth import get_current_user
from mr_backend.database.db_manager import (
    create_model_info,
    create_model_preview,
    get_models_info,
    store_trimesh,
)
from mr_backend.model_preview.offscreen_renderer import render_preview
from mr_backend.shape_inference.clean_mesh import (
    merge_geometry,
    rotate_all_geometries,
    rotate_mesh,
)

from .models import FurnitureInfoBase, FurnitureInfos, UserInDB

furniture_router = APIRouter()


@furniture_router.get("/furnitures/info", response_model=FurnitureInfos)
def read_furniture_info(skip: int, limit: int):
    furniture_infos, count = get_models_info(skip, limit)
    furniture_infos = [
        FurnitureInfoBase.model_validate(info, from_attributes=True)
        for info in furniture_infos
    ]
    return FurnitureInfos(furniture_infos=furniture_infos, total_furniture_count=count)


@furniture_router.post("/furnitures/upload", response_model=FurnitureInfoBase)
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
