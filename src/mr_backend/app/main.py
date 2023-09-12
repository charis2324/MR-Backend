from threading import Thread

from fastapi import FastAPI

from mr_backend.shape_inference.inference_server import inference_thread
from mr_backend.state import inference_thread_ready
from . import tasks

inference_thread = Thread(target=inference_thread, daemon=True)
inference_thread.start()
print("waiting")
print(inference_thread_ready)
inference_thread_ready.wait()
print("done waiting")
app = FastAPI()
app.include_router(tasks.router)
