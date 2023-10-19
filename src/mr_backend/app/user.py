from typing import Annotated

from fastapi import APIRouter, Depends

from mr_backend.app.auth import get_current_user
from mr_backend.database.db_manager import get_model_info_by_user

from .models import FurnitureInfoBase, FurnitureInfos, UserInDB, UserInfoResponse

user_router = APIRouter()


@user_router.get("/me", response_model=UserInfoResponse)
def get_self_info(
    current_user: Annotated[UserInDB, Depends(get_current_user)],
):
    return UserInfoResponse(
        uuid=current_user.uuid,
        username=current_user.username,
        created_at=current_user.created_at,
    )


@user_router.get("/users/{user_uuid}/furnitures/info")
def read_user_furnitures_info(user_uuid: str):
    user_model_info, username = get_model_info_by_user(user_uuid)
    model_info_bases = [
        FurnitureInfoBase(**{**info.__dict__, "username": username})
        for info in user_model_info
    ]
    return FurnitureInfos(
        furniture_infos=model_info_bases, total_furniture_count=len(model_info_bases)
    )
