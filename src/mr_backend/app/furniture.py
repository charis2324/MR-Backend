from fastapi import APIRouter

from mr_backend.database.db_manager import get_models_info

from .models import FurnitureInfoBase, FurnitureInfos

furniture_router = APIRouter()


@furniture_router.get("/furnitures/info", response_model=FurnitureInfos)
def read_furniture_info(skip: int, limit: int):
    furniture_infos, count = get_models_info(skip, limit)
    furniture_infos = [
        FurnitureInfoBase.model_validate(info, from_attributes=True)
        for info in furniture_infos
    ]
    return FurnitureInfos(furniture_infos=furniture_infos, total_furniture_count=count)
