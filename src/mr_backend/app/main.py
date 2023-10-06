import os
from threading import Thread
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from mr_backend.model_preview.render_preview import preview_generation_thread
from mr_backend.shape_inference.inference_server import inference_thread
from mr_backend.state import inference_thread_ready

from .auth import (
    UnauthorizedRedirectException,
    auth_router,
    get_current_user,
    get_current_user_update_token_or_redirect,
    update_token_cookie,
)
from .models import UserInDB
from .tasks import task_router
from .user import user_router

inference_thread = Thread(target=inference_thread, daemon=True)
inference_thread.start()
preview_generation_thread = Thread(target=preview_generation_thread, daemon=True)
preview_generation_thread.start()
inference_thread_ready.wait()

app = FastAPI()
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.include_router(auth_router)
app.include_router(task_router)
app.include_router(user_router)

templates_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_dir)

static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")


# For triggering redirect to login on website.
@app.exception_handler(UnauthorizedRedirectException)
def unauthorized_handler(request: Request, exc: UnauthorizedRedirectException):
    return RedirectResponse("/login")


@app.get("/", response_class=HTMLResponse)
def read_items(
    request: Request,
    current_user_and_token: Annotated[
        UserInDB, Depends(get_current_user_update_token_or_redirect)
    ],
):
    response = templates.TemplateResponse(
        "index.html",
        {"request": request, "username": current_user_and_token["user"].username},
    )
    if current_user_and_token["new_token"]:
        update_token_cookie(response, current_user_and_token["new_token"])
    return response


@app.get("/api_test", response_class=HTMLResponse)
async def read_items(request: Request):
    return templates.TemplateResponse("api_test.html", {"request": request})


@app.get("/register", response_class=HTMLResponse)
async def read_items(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@app.get("/login", response_class=HTMLResponse)
async def read_items(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})
