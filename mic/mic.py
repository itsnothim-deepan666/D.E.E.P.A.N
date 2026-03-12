import sounddevice as sd
import numpy as np
import queue
import multiprocessing as mp
import webrtcvad
import time
import threading
import whisper
import keyboard
from schema import Event

SAMPLE_RATE = 16000
FRAME_DURATION = 30  # ms
FRAME_SIZE = int(SAMPLE_RATE * FRAME_DURATION / 1000)
VAD_MODE = 2
SILENCE_THRESHOLD = 1.0  # seconds
MAX_AUDIO_DURATION = 30  # seconds - max recording length to prevent OOM
STOP_KEY = "space"  # Press spacebar to stop listening


def _stop_key_listener(stop_event):
    """Runs in a daemon thread, waits for the stop key and sets the event."""
    keyboard.wait(STOP_KEY)
    print(f"\n[MIC] Stop key ({STOP_KEY}) pressed. Shutting down...")
    stop_event.set()


def mic_worker(event_queue: mp.Queue, stop_event):
    print("[MIC] Loading Whisper base model...")
    model = whisper.load_model("small", device="cuda")
    print("[MIC] Model loaded.")

    vad = webrtcvad.Vad(VAD_MODE)

    audio_buffer = []
    silence_start = None

    q = queue.Queue()

    def audio_callback(indata, frames, time_info, status):
        if status:
            print(status)
        q.put(indata.copy())

    # Start a daemon thread that listens for the stop key
    stop_thread = threading.Thread(target=_stop_key_listener, args=(stop_event,), daemon=True)
    stop_thread.start()

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        blocksize=FRAME_SIZE,
        channels=1,
        dtype="int16",
        callback=audio_callback,
    ):
        print(f"[MIC] Listening... (press {STOP_KEY} to stop)")

        while not stop_event.is_set():
            try:
                frame = q.get(timeout=0.3)
            except queue.Empty:
                continue

            is_speech = vad.is_speech(frame.tobytes(), SAMPLE_RATE)

            if is_speech:
                audio_buffer.append(frame)
                silence_start = None
            
            # Check if buffer exceeded max duration
            max_frames = int(MAX_AUDIO_DURATION * SAMPLE_RATE / FRAME_SIZE)
            buffer_too_long = len(audio_buffer) >= max_frames

            if not is_speech or buffer_too_long:
                if audio_buffer:
                    if silence_start is None and not buffer_too_long:
                        silence_start = time.time()

                    if buffer_too_long or (silence_start and time.time() - silence_start > SILENCE_THRESHOLD):
                        # Utterance complete
                        audio_data = np.concatenate(audio_buffer, axis=0)
                        audio_buffer = []
                        silence_start = None

                        audio_float = audio_data.flatten().astype(np.float32) / 32768.0

                        try:
                            result = model.transcribe(
                                audio_float,
                                fp16=True  # Using GPU
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

                        except Exception as e:
                            print(f"[MIC ERROR] {e}")

    print("[MIC] Stopped.")


if __name__ == "__main__":
    q = mp.Queue()
    stop = mp.Event()
    mic_worker(q, stop)