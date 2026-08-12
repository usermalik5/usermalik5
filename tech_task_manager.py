# -*- coding: utf-8 -*-
"""Small, reusable background-task manager for desktop operations.

Workers never touch Tk directly. UI callbacks are scheduled through the
callback supplied at construction time (normally ``self.after``).
"""

from concurrent.futures import ThreadPoolExecutor
import threading


class TaskManager:
    def __init__(self, ui_after, max_workers=4):
        self._after = ui_after
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="GeloTech")
        self._futures = set()
        self._lock = threading.Lock()
        self._closed = False

    def submit(self, worker, *, on_complete=None, on_error=None, name=None):
        if self._closed:
            raise RuntimeError("TaskManager is shut down")

        def run():
            try:
                result = worker()
                if on_complete is not None:
                    self.run_on_ui(on_complete, result)
                return result
            except Exception as exc:
                if on_error is not None:
                    self.run_on_ui(on_error, exc)
                raise

        future = self._executor.submit(run)
        with self._lock:
            self._futures.add(future)
        future.add_done_callback(self._forget)
        return future

    def _forget(self, future):
        with self._lock:
            self._futures.discard(future)

    def run_on_ui(self, callback, *args):
        """Schedule a callback on Tk's main thread."""
        if self._closed:
            return None
        return self._after(0, lambda: callback(*args))

    def cancel_all(self):
        with self._lock:
            futures = list(self._futures)
        for future in futures:
            future.cancel()

    def shutdown(self, wait=False):
        if self._closed:
            return
        self._closed = True
        self.cancel_all()
        self._executor.shutdown(wait=wait, cancel_futures=True)
