from threading import Event

# Global state objects
inference_thread_ready = Event()
inference_thread_busy = Event()
