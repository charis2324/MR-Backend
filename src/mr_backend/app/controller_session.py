# A class for maintaining a controller session for the Fronten Client with the backend server.
# The session is maintained by a queue of events.
# When an event is failed to be sent to the client, a background task will be created to clear the queue after a timeout.

import asyncio
import logging
from datetime import datetime, timedelta

from apscheduler.job import Job
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from mr_backend.app.controller_event import PollingControllerEvent, SSEControllerEvent

error_logger = logging.getLogger("uvicorn.error")

logging.basicConfig()  # Initialize logging
logging.getLogger("apscheduler").setLevel(logging.DEBUG)
event_session_scheduler = AsyncIOScheduler()
event_session_scheduler.start()
HEART_BEAT_RATE_IN_SECONDS = 20


class SSEControllerSession:
    uuid: str
    event_queue: asyncio.Queue
    active: bool
    deactivate_scheduler: AsyncIOScheduler

    def __init__(
        self,
        uuid: str,
        background_scheduler: AsyncIOScheduler = event_session_scheduler,
    ):
        if background_scheduler is None:
            raise ValueError("background_scheduler cannot be None")
        self.uuid = uuid
        self.active = True
        self.event_queue = asyncio.Queue()
        self.deactivate_scheduler = background_scheduler
        self.deactivate_job = None
        self._set_deactivate_job()

    def _set_deactivate_job(self):
        if self.deactivate_job is not None and self.deactivate_scheduler.get_job(
            self.deactivate_job.id
        ):
            self.deactivate_scheduler.remove_job(self.deactivate_job.id)

        self.deactivate_job = self.deactivate_scheduler.add_job(
            self.deactivate,
            "date",
            run_date=datetime.now() + timedelta(seconds=HEART_BEAT_RATE_IN_SECONDS + 5),
        )
        error_logger.info(
            f"Session:{self.uuid} Deactivate job set job: {self.deactivate_job}"
        )

    def deactivate(self):
        self.active = False
        self.event_queue = asyncio.Queue()

    def add_event(self, event: SSEControllerEvent):
        self.event_queue.put_nowait(event)

    async def event_iterator(self):
        while True:
            try:
                error_logger.info(f"Session:{self.uuid} Event generator new iteration")
                if not self.active:
                    error_logger.info(f"Session:{self.uuid} Event generator stopped")
                    break
                # event is a controller event object
                event = await asyncio.wait_for(
                    self.event_queue.get(), timeout=HEART_BEAT_RATE_IN_SECONDS
                )
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


POLLING_SESSION_TIMEOUT = 30


class PollingControllerSession:
    uuid: str
    event_queue: asyncio.Queue
    active: bool
    background_scheduler: AsyncIOScheduler
    deactivate_job: Job

    def __init__(
        self,
        uuid: str,
        background_scheduler: AsyncIOScheduler = event_session_scheduler,
    ) -> None:
        self.uuid = uuid
        self.active = True
        self.event_queue = asyncio.Queue()
        self.background_scheduler = background_scheduler
        self.deactivate_job = None
        self._set_deactive_job()

    def add_event(self, event: PollingControllerEvent):
        self.event_queue.put_nowait(event)
        self._set_deactive_job()

    def deactivate(self):
        self.active = False
        self.event_queue = asyncio.Queue()  # clear the queue
        error_logger.info(f"Session:{self.uuid} Deactivated")

    def _set_deactive_job(self):
        if self.deactivate_job is not None:
            error_logger.info("Removing deactivate job")
            try:
                self.deactivate_job.remove()
            except:
                error_logger.info("Deactivate job already removed")
        self.deactivate_job = self.background_scheduler.add_job(
            self.deactivate,
            "date",
            run_date=datetime.now() + timedelta(seconds=POLLING_SESSION_TIMEOUT),
        )
        error_logger.info(
            f"Session:{self.uuid} Deactivate job set job: {self.deactivate_job}"
        )

    def get_events_dict(self):
        events = []

        # get all the event from the queue
        while not self.event_queue.empty():
            try:
                event = self.event_queue.get_nowait()
                events.append(event.data_as_dict())
            except asyncio.QueueEmpty:
                break
        self._set_deactive_job()
        return events

    def get_events(self):
        events = []

        # get all the event from the queue
        while not self.event_queue.empty():
            try:
                event = self.event_queue.get_nowait()
                events.append(event)
            except asyncio.QueueEmpty:
                break
        self._set_deactive_job()
        return events
