import multiprocessing as mp
import queue
from intent_schema import Intent


def _extract_open_target(text: str):
    if "open" not in text:
        return None

    target = text.split("open", 1)[1].strip()
    if target.startswith("the "):
        target = target[4:].strip()
    return target or None


def _resolve_intent(text: str):
    if "shutdown" in text:
        return "shutdown_system", None

    open_target = _extract_open_target(text)
    if open_target:
        return "open_item", open_target

    return "unknown_command", text


def intent_worker(intent_queue: mp.Queue, executor_queue: mp.Queue, stop_event=None):

    print("[INTENT] Engine started.")

    while not (stop_event is not None and stop_event.is_set()):
        try:
            event = intent_queue.get(timeout=0.5)
        except queue.Empty:
            continue

        if event is None:
            break

        text = str(event.payload).strip().lower()
        action, target = _resolve_intent(text)

        intent = Intent.create(
            action=action,
            target=target,
            source_event_id=event.event_id,
            raw_text=text
        )

        executor_queue.put(intent)
        print(f"[INTENT] action={intent.action} target={intent.target}")

    print("[INTENT] Stopped.")