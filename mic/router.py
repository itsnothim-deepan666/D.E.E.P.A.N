import multiprocessing as mp
import time
import queue
from schema import Event

INPUT_EVENT_TYPES = {"VOICE_TEXT", "TEXT_INPUT"}
RESULT_EVENT_TYPE = "RESULT_EVENT"


def router_worker(
    event_queue: mp.Queue,
    intent_queue: mp.Queue,
    ui_queue=None,
    stop_event=None,
):
    print("[ROUTER] Started.")

    while not (stop_event is not None and stop_event.is_set()):
        try:
            event = event_queue.get(timeout=0.5)
        except queue.Empty:
            continue

        if event is None:
            break

        if not isinstance(event, Event):
            continue

        latency = time.time() - event.timestamp

        print(
            f"[ROUTER] {event.event_type} | "
            f"{event.payload} | latency={latency:.2f}s"
        )

        if event.event_type in INPUT_EVENT_TYPES:
            intent_queue.put(event)
        elif event.event_type == RESULT_EVENT_TYPE and ui_queue is not None:
            ui_queue.put(event)

    print("[ROUTER] Stopped.")