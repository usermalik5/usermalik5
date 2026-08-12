import threading

from tech_task_manager import TaskManager


def test_task_manager_runs_worker_and_completes_on_ui_callback():
    ui_calls = []
    event = threading.Event()
    manager = TaskManager(lambda delay, callback: (ui_calls.append(callback), callback())[1], max_workers=1)
    try:
        future = manager.submit(lambda: 42, on_complete=lambda value: (ui_calls.append(value), event.set()))
        assert future.result(timeout=3) == 42
        assert event.wait(1)
        assert 42 in ui_calls
    finally:
        manager.shutdown(wait=True)
