from datetime import timedelta
from enum import Enum

from pydantic import BaseModel


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
