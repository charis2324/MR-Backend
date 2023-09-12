from pydantic import BaseModel
from enum import Enum
from datetime import timedelta


class GenerationTaskRequest(BaseModel):
    prompt: str
    guidance_scale: float


class GenerationTask(BaseModel):
    task_id: str
    prompt: str
    guidance_scale: float
    estimated_duration: timedelta


class TaskStatusEnum(str, Enum):
    processing = "processing"
    completed = "completed"
    failed = "failed"


class TaskStatus(BaseModel):
    task_id: str
    status: TaskStatusEnum
    message: str
