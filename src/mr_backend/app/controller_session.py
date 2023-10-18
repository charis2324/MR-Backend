# A class for maintaining a controller session for the Fronten Client with the backend server.
# The session is maintained by a queue of events.
# When an event is failed to be sent to the client, a background task will be created to clear the queue after a timeout.

import asyncio
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from mr_backend.app.controller_event import ControllerEvent

error_logger = logging.getLogger("uvicorn.error")

logging.basicConfig()  # Initialize logging
logging.getLogger("apscheduler").setLevel(logging.DEBUG)
event_session_scheduler = BackgroundScheduler()

HEART_BEAT_RATE_IN_SECONDS = 20


class ControllerSession:
    uuid: str
    event_queue: asyncio.Queue
    last_event_time: datetime
    active: bool
    deactivate_scheduler: BackgroundScheduler

    def __init__(
        self,
        uuid: str,
        background_scheduler: BackgroundScheduler = event_session_scheduler,
    ):
        if background_scheduler is None:
            raise ValueError("background_scheduler cannot be None")
        self.uuid = uuid
        self.active = True
        self.event_queue = asyncio.Queue()
        self.deactivate_scheduler = background_scheduler
        self._set_deactivate_job()

    def _set_deactivate_job(self):
        if self.deactivate_scheduler.get_job(self.deactivate_job):
            self.deactivate_scheduler.remove_job(self.deactivate_job)
        self.deactivate_job = self.event_scheduler.add_job(
            self.deactivate,
            "date",
            run_date=datetime.now() + timedelta(seconds=HEART_BEAT_RATE_IN_SECONDS),
        )

    def deactivate(self):
        self.active = False
        self.event_queue = asyncio.Queue()

    def add_event(self, event: ControllerEvent):
        self.event_queue.put_nowait(event)

    async def event_iterator(self):
        while True:
            try:
                # event is a controller event object
                event = await asyncio.wait_for(self.event_queue.get(), timeout=30)
                yield str(event)
                error_logger.info(f"Session:{self.uuid} Event sent: {event}")
                self._set_deactivate_job()
            except asyncio.TimeoutError:
                # yield a heartbeat for every 30 seconds of silence
                yield ":heartbeat\n\n"
                error_logger.info(f"Session:{self.uuid} Heartbeat sent")
                self._set_deactivate_job()
            except Exception:
                error_logger.info(f"Session:{self.uuid} Event generator stopped")
                break
