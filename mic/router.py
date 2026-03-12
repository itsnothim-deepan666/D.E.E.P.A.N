import multiprocessing as mp
import time
from schema import Event


def router_worker(event_queue: mp.Queue, stop_event):
    print("[ROUTER] Started.")

    while not stop_event.is_set():
        try:
            event = event_queue.get(timeout=1)
        except Exception:
            continue

        # Basic type validation
        if not isinstance(event, Event):
            print("[ROUTER WARNING] Invalid event object received.")
            continue

        # Latency measurement
        now = time.time()
        latency = now - event.timestamp

        # Log event
        print(
            f"[ROUTER] "
            f"type={event.event_type} | "
            f"source={event.source} | "
            f"payload={event.payload} | "
            f"latency={latency:.3f}s"
        )

        # Future:
        # forward_to_intent_layer(event)

    print("[ROUTER] Stopped.")