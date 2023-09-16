from threading import Thread
import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

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

templates_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_dir)

static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", response_class=HTMLResponse)
async def read_items(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
