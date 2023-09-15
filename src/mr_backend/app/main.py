from threading import Thread

from fastapi import FastAPI

from mr_backend.model_preview.render_preview import preview_generation_thread
from mr_backend.shape_inference.inference_server import inference_thread
from mr_backend.state import inference_thread_ready

from . import tasks

inference_thread = Thread(target=inference_thread, daemon=True)
inference_thread.start()
preview_generation_thread = Thread(target=preview_generation_thread, daemon=True)
preview_generation_thread.start()
inference_thread_ready.wait()
app = FastAPI()
app.include_router(tasks.router)
