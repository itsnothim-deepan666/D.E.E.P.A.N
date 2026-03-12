import multiprocessing as mp
from mic import mic_worker
from router import router_worker


def main():
    mp.set_start_method("spawn")  # Required for Windows

    event_queue = mp.Queue(maxsize=100)
    stop_event = mp.Event()

    mic_process = mp.Process(
        target=mic_worker,
        args=(event_queue, stop_event),
        name="MicProcess"
    )

    router_process = mp.Process(
        target=router_worker,
        args=(event_queue, stop_event),
        name="RouterProcess"
    )

    mic_process.start()
    router_process.start()

    print("[MAIN] Processes started. Press SPACE to stop.")

    mic_process.join()
    stop_event.set()  # Ensure router also stops when mic exits
    router_process.join()

    print("[MAIN] All processes stopped.")


if __name__ == "__main__":
    main()