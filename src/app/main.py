from threading import Thread

from fastapi import FastAPI

from ..shape_inference.inference_server import inferenceThread
from ..state import inference_thread_ready
from . import tasks

inference_thread = Thread(target=inferenceThread, daemon=True)
inference_thread_ready.wait()
app = FastAPI()
app.include_router(tasks.router)
