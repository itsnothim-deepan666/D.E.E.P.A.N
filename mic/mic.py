import sounddevice as sd
import numpy as np
import queue
import multiprocessing as mp
import webrtcvad
import time
import threading
import keyboard
from schema import Event

SAMPLE_RATE = 16000
FRAME_DURATION = 30  # ms
FRAME_SIZE = int(SAMPLE_RATE * FRAME_DURATION / 1000)
VAD_MODE = 2
SILENCE_THRESHOLD = 1.0  # seconds
MAX_AUDIO_DURATION = 30  # seconds - max recording length to prevent OOM
PUSH_KEY = "space"  # Press spacebar to finalize the current utterance


def _push_key_listener(flush_event, stop_event=None):
    def handle_press(_event):
        if not flush_event.is_set():
            print(f"\n[MIC] Push key ({PUSH_KEY}) pressed. Finalizing current utterance...")
            flush_event.set()

    hook = keyboard.on_press_key(PUSH_KEY, handle_press)

    while not (stop_event is not None and stop_event.is_set()):
        time.sleep(0.2)

    keyboard.unhook(hook)


def _transcribe_and_publish(model, audio_buffer, event_queue):
    if not audio_buffer:
        return

    audio_data = np.concatenate(audio_buffer, axis=0)
    audio_float = audio_data.flatten().astype(np.float32) / 32768.0

    try:
        result = model.transcribe(
            audio_float,
            fp16=getattr(model, "_use_fp16", False)
        )

        text = result["text"].strip()

        if text:
            event = Event.create(
                event_type="VOICE_TEXT",
                source="mic_01",
                payload=text,
                confidence=None
            )
            event_queue.put(event)
            print(f"[MIC] Captured: {text}")
        else:
            print("[MIC] No speech recognized.")

    except Exception as e:
        print(f"[MIC ERROR] {e}")


def _load_whisper_model():
    try:
        import whisper
    except Exception as e:
        return None, None, f"Whisper import failed: {e}"

    try:
        model = whisper.load_model("small", device="cuda")
        model._use_fp16 = True
        return model, "cuda", None
    except Exception as cuda_error:
        print(f"[MIC WARNING] CUDA load failed, trying CPU: {cuda_error}")

    try:
        model = whisper.load_model("small", device="cpu")
        model._use_fp16 = False
        return model, "cpu", None
    except Exception as cpu_error:
        return None, None, f"CUDA failed and CPU fallback failed: {cpu_error}"


def mic_worker(event_queue: mp.Queue, stop_event=None):
    print("[MIC] Loading Whisper base model...")
    model, device_name, load_error = _load_whisper_model()
    if model is None:
        error_message = f"Whisper model load failed. Voice input disabled. {load_error}"
        print(f"[MIC ERROR] {error_message}")
        event_queue.put(
            Event.create(
                event_type="RESULT_EVENT",
                source="mic_01",
                payload={"status": "error", "message": error_message},
                confidence=None,
            )
        )

        while not (stop_event is not None and stop_event.is_set()):
            time.sleep(0.5)

        print("[MIC] Stopped.")
        return

    print(f"[MIC] Model loaded on {device_name}.")

    vad = webrtcvad.Vad(VAD_MODE)

    audio_buffer = []
    silence_start = None
    flush_event = threading.Event()

    q = queue.Queue()

    def audio_callback(indata, frames, time_info, status):
        if status:
            print(status)
        q.put(indata.copy())

    push_thread = threading.Thread(target=_push_key_listener, args=(flush_event, stop_event), daemon=True)
    push_thread.start()

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        blocksize=FRAME_SIZE,
        channels=1,
        dtype="int16",
        callback=audio_callback,
    ):
        print(f"[MIC] Listening... (press {PUSH_KEY} to send current speech)")

        while not (stop_event is not None and stop_event.is_set()):
            try:
                frame = q.get(timeout=0.3)
            except queue.Empty:
                if flush_event.is_set():
                    flush_event.clear()
                    if audio_buffer:
                        _transcribe_and_publish(model, audio_buffer, event_queue)
                        audio_buffer = []
                        silence_start = None
                    else:
                        print("[MIC] Push requested, but no speech has been buffered yet.")
                continue

            is_speech = vad.is_speech(frame.tobytes(), SAMPLE_RATE)

            if is_speech:
                audio_buffer.append(frame)
                silence_start = None
            elif audio_buffer and silence_start is None:
                silence_start = time.time()
            
            max_frames = int(MAX_AUDIO_DURATION * SAMPLE_RATE / FRAME_SIZE)
            buffer_too_long = len(audio_buffer) >= max_frames
            should_flush = False

            if audio_buffer:
                if flush_event.is_set():
                    flush_event.clear()
                    should_flush = True
                elif buffer_too_long:
                    should_flush = True
                elif silence_start and time.time() - silence_start > SILENCE_THRESHOLD:
                    should_flush = True

            if should_flush:
                _transcribe_and_publish(model, audio_buffer, event_queue)
                audio_buffer = []
                silence_start = None

        if audio_buffer:
            _transcribe_and_publish(model, audio_buffer, event_queue)

    print("[MIC] Stopped.")


if __name__ == "__main__":
    q = mp.Queue()
    stop = mp.Event()
    mic_worker(q, stop)