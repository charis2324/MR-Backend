from threading import Event


class ActiveLoginCodes:
    def __init__(self):
        self._set = set()

    def add(self, item):
        self._set.add(item)

    def remove(self, item):
        self._set.remove(item)

    def contains(self, item):
        return item in self._set

    def get_all(self):
        return self._set

    def replace(self, new_set):
        self._set = new_set

    def __repr__(self):
        return f"ActiveLoginCodes({self._set})"


# Global state objects
inference_thread_ready = Event()
inference_thread_busy = Event()
active_login_codes = ActiveLoginCodes()
