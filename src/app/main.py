from fastapi import FastAPI
from . import models, tasks

app = FastAPI()

app.include_router(tasks.router)