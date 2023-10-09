from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse, RedirectResponse

from mr_backend.app.auth import get_current_user
from mr_backend.database.db_manager import create_user

from .models import UserCreate, UserInDB, UserInfoResponse
from .security import get_password_hash

user_router = APIRouter()


@user_router.post("/register")
def register(new_user: UserCreate):
    hashed_password = get_password_hash(new_user.password)
    user = create_user(new_user.username, hashed_password)
    if user is None:
        raise HTTPException(status_code=400, detail="Username is already taken")
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message": "User registered successfully"},
    )


@user_router.get("/logout")
def logout():
    response = RedirectResponse("/login")
    response.delete_cookie("access_token")
    return response


@user_router.get("/user-info", response_model=UserInfoResponse)
def get_self_info(
    current_user: Annotated[UserInDB, Depends(get_current_user)],
):
    return UserInfoResponse(
        uuid=current_user.uuid,
        username=current_user.username,
        created_at=current_user.created_at,
    )
