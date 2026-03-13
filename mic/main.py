import multiprocessing as mp
import time
from mic import mic_worker
from router import router_worker
from intent_engine import intent_worker
from executor import executor_worker


def _shutdown(processes, stop_event, queues):
    stop_event.set()

    for q in queues:
        try:
            q.put_nowait(None)
        except Exception:
            pass

    for process in processes:
        process.join(timeout=3)
        if process.is_alive():
            process.terminate()
            process.join(timeout=2)


def main():

    ctx = mp.get_context("spawn")

    event_queue = ctx.Queue(maxsize=100)
    intent_queue = ctx.Queue(maxsize=100)
    executor_queue = ctx.Queue(maxsize=100)
    stop_event = ctx.Event()

    mic_process = ctx.Process(
        target=mic_worker,
        args=(event_queue, stop_event),
        name="MicProcess",
    )

    router_process = ctx.Process(
        target=router_worker,
        args=(event_queue, intent_queue, None, stop_event),
        name="RouterProcess",
    )

    intent_process = ctx.Process(
        target=intent_worker,
        args=(intent_queue, executor_queue, stop_event),
        name="IntentProcess",
    )

    executor_process = ctx.Process(
        target=executor_worker,
        args=(executor_queue, event_queue, stop_event),
        name="ExecutorProcess",
    )

    processes = [mic_process, router_process, intent_process, executor_process]

    for process in processes:
        process.start()

    print("[MAIN] Pipeline running: mic -> router -> intent -> executor")
    print("[MAIN] Press Ctrl+C to stop.")

    try:
        while all(process.is_alive() for process in processes):
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[MAIN] Stopping pipeline...")
    finally:
        _shutdown(processes, stop_event, [event_queue, intent_queue, executor_queue])
        print("[MAIN] Stopped.")


if __name__ == "__main__":
    main()