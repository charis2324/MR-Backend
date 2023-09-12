from queue import Queue
from threading import Event

# Global state objects
task_queue = Queue()
waiting_tasks = set()
completed_tasks = set()
failed_tasks = set()
durations = []
inference_thread_ready = Event()
inference_thread_busy = Event()
