from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from .models import UserCreate
from .security import get_password_hash
from mr_backend.database.db_manager import create_user


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
