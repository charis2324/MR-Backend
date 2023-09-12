from fastapi import FastAPI
from . import tasks
from ..state import inference_thread_ready
from threading import Thread
from ..shape_inference.inference_server import inferenceThread

inference_thread = Thread(target=inferenceThread, daemon=True)
inference_thread_ready.wait()
app = FastAPI()
app.include_router(tasks.router)
