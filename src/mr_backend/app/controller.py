import asyncio
import logging
from typing import Annotated, Callable

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import StreamingResponse

from mr_backend.app.auth import get_current_user
from mr_backend.app.controller_event import ImportFurnitureEvent
from mr_backend.app.controller_session import ControllerSession
from mr_backend.app.models import ImportFurnitureEventRequest, UserInDB

error_logger = logging.getLogger("uvicorn.error")

controller_sessions = {}
controller_router = APIRouter(prefix="/controller")


def clear_user_event_session(user_uuid: str):
    try:
        controller_sessions.pop(user_uuid)  # Clear the queue
        logging.info(f"User {user_uuid} event session cleared")
    except KeyError:
        logging.info(f"User {user_uuid} event session not found")


async def controller_event_generator(event_queue: asyncio.Queue):
    # Keep getting events from the queue and yielding them
    while True:
        try:
            # event is a controller event object
            event = await asyncio.wait_for(event_queue.get(), timeout=30)

            yield str(event)
            error_logger.info(f"Event sent: {event}")
        except asyncio.TimeoutError:
            # yield a heartbeat for every 30 seconds of silence
            yield ":heartbeat\n\n"
            error_logger.info(f"heartbeat sent")
        except Exception:
            error_logger.info(f"Event generator stopped")
            break


@controller_router.get("/event")
async def send_controller_events(
    current_user: Annotated[UserInDB, Depends(get_current_user)]
):
    current_user_uuid = current_user.uuid
    if current_user_uuid not in controller_sessions:
        controller_sessions[current_user_uuid] = ControllerSession(current_user_uuid)
    error_logger.info(f"Sessions: {controller_sessions}")
    try:
        return StreamingResponse(
            # controller_event_generator(controller_sessions[current_user_uuid]),
            controller_sessions[current_user_uuid].event_iterator(),
            media_type="text/event-stream",
            # background=clear_user_event_session(current_user_uuid),
        )
    except Exception:
        error_logger.info(f"User {current_user_uuid} disconnected")


@controller_router.post("/event/import-furniture")
def add_import_furniture_events(
    current_user: Annotated[UserInDB, Depends(get_current_user)],
    importFurnitureEvent: ImportFurnitureEventRequest = Body(...),
):
    current_user_uuid = current_user.uuid
    error_logger.info(f"User {current_user_uuid} tries to add import furniture event")
    error_logger.info(f"Sessions: {controller_sessions}")
    if controller_sessions.get(current_user_uuid, None) is None:
        raise HTTPException(status_code=400, detail="User not connected controller")
    if not controller_sessions[current_user_uuid].active:
        raise HTTPException(status_code=400, detail="User not connected controller")
    furniture_uuid = importFurnitureEvent.uuid
    event = ImportFurnitureEvent(furniture_uuid=furniture_uuid)
    controller_sessions[current_user_uuid].add_event(event)
    return {"detail": "Event added to queue"}
