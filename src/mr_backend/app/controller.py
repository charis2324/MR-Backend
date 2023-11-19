import asyncio
import logging
from typing import Annotated, Callable, List

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import StreamingResponse

from mr_backend.app.auth import get_current_user
from mr_backend.app.controller_event import (
    PollingImportFurnitureEvent,
    SSEImportFurnitureEvent,
)
from mr_backend.app.controller_session import (
    PollingControllerSession,
    SharedPollingControllerSessions,
    SSEControllerSession,
)
from mr_backend.app.models import (
    EventPollingResponse,
    ImportFurnitureEventRequest,
    UserInDB,
)

error_logger = logging.getLogger("uvicorn.error")

# sse_controller_sessions = {}

polling_controller_sessions = SharedPollingControllerSessions()

controller_router = APIRouter(prefix="/controller")


# def clear_user_event_session(user_uuid: str):
#     try:
#         sse_controller_sessions.pop(user_uuid)  # Clear the queue
#         logging.info(f"User {user_uuid} event session cleared")
#     except KeyError:
#         logging.info(f"User {user_uuid} event session not found")


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


# @controller_router.get("/event")
# async def send_controller_events(
#     current_user: Annotated[UserInDB, Depends(get_current_user)]
# ):
#     current_user_uuid = current_user.uuid
#     error_logger.info(f"Sessions: {sse_controller_sessions}")
#     if sse_controller_sessions.get(current_user_uuid, None) is None:
#         sse_controller_sessions[current_user_uuid] = SSEControllerSession(
#             current_user_uuid
#         )
#         error_logger.info(f"New session created for user {current_user_uuid}")
#     else:
#         sse_controller_sessions[current_user_uuid].active = True
#         error_logger.info(f"Session {current_user_uuid} reactivated")
#     try:
#         return StreamingResponse(
#             # controller_event_generator(controller_sessions[current_user_uuid]),
#             sse_controller_sessions[current_user_uuid].event_iterator(),
#             media_type="text/event-stream",
#             # background=clear_user_event_session(current_user_uuid),
#         )
#     except Exception:
#         error_logger.info(f"User {current_user_uuid} disconnected")


@controller_router.post("/event/import-furniture")
def add_import_furniture_events(
    current_user: Annotated[UserInDB, Depends(get_current_user)],
    importFurnitureEvent: ImportFurnitureEventRequest = Body(...),
):
    current_user_uuid = current_user.uuid
    error_logger.info(f"User {current_user_uuid} tries to add import furniture event")
    error_logger.info(f"Sessions: {polling_controller_sessions.sessions}")
    if polling_controller_sessions.sessions.get(current_user_uuid, None) is None:
        raise HTTPException(status_code=400, detail="User not connected controller")
    if not polling_controller_sessions.sessions[current_user_uuid].active:
        raise HTTPException(status_code=400, detail="User not connected controller")
    furniture_uuid = importFurnitureEvent.uuid
    event = PollingImportFurnitureEvent(furniture_uuid=furniture_uuid)
    polling_controller_sessions.sessions[current_user_uuid].add_event(event)
    error_logger.info(f"Furniture {furniture_uuid} added to queue")
    return {"detail": "Event added to queue"}


@controller_router.get("/event/connect")
def create_polling_controller_session(
    current_user: Annotated[UserInDB, Depends(get_current_user)],
):
    current_user_uuid = current_user.uuid
    error_logger.info(
        f"User {current_user_uuid} tries to create polling controller session"
    )
    if polling_controller_sessions.sessions.get(current_user_uuid, None) == None:
        polling_controller_sessions.sessions[
            current_user_uuid
        ] = PollingControllerSession(current_user_uuid)
        error_logger.info(f"New polling session created for user {current_user_uuid}")
    else:
        polling_controller_sessions.sessions[current_user_uuid].active = True
        error_logger.info(f"Polling session {current_user_uuid} reactivated")
    return {"detail": "Polling session created"}


@controller_router.get("/event/poll", response_model=EventPollingResponse)
def poll_controller_session(
    current_user: Annotated[UserInDB, Depends(get_current_user)],
):
    current_user_uuid = current_user.uuid
    if polling_controller_sessions.sessions.get(current_user_uuid, None) == None:
        error_logger.warning("User not connected controller")
        raise HTTPException(status_code=400, detail="User not connected controller")
    if not polling_controller_sessions.sessions[current_user_uuid].active:
        error_logger.warning("User session is not active")
        raise HTTPException(status_code=400, detail="User session is not active")
    events_dicts = polling_controller_sessions.sessions[
        current_user_uuid
    ].get_events_dict()
    error_logger.info(f"Events polled: {events_dicts}")
    return {"events": events_dicts}
