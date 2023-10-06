from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, constr


class GenerationTaskRequest(BaseModel):
    prompt: str
    guidance_scale: float


class GenerationTask(BaseModel):
    task_id: str
    prompt: str
    guidance_scale: float
    estimated_duration: timedelta


class GenerationTaskResponse(BaseModel):
    task_id: str
    estimated_duration: timedelta


class TaskStatusEnum(str, Enum):
    waiting = "waiting"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class TaskStatus(BaseModel):
    task_id: str
    status: TaskStatusEnum
    message: str


class UserInDB(BaseModel):
    uuid: str
    username: str
    hashed_password: str
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str


class UserCreate(BaseModel):
    username: constr(pattern="^[a-zA-Z0-9_]+$") = Field(
        ..., min_length=3, max_length=50
    )
    password: constr(pattern="^[a-zA-Z0-9_]+$") = Field(
        ..., min_length=3, max_length=50
    )


class FurnitureInfoBase(BaseModel):
    uuid: str
    name: str
    user_uuid: str
    username: Optional[str]
    description: Optional[str]
    scale_type: int
    scale_x: Optional[float]
    scale_y: Optional[float]
    scale_z: Optional[float]
    source: Optional[str]


class FurnitureInfos(BaseModel):
    furniture_infos: List[FurnitureInfoBase]
    total_furniture_count: int
