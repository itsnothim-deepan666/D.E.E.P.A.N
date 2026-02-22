import sounddevice as sd
import soundfile as sf
import whisper
import os
import numpy as np
import keyboard

SAMPLERATE = 16000   # Whisper native rate
CHANNELS = 1         # Mono

# Load model once so it's reused across calls
_model = whisper.load_model("medium", device="cuda")


def get_transcription():
    """Record from mic until space is pressed, transcribe with Whisper, return text."""
    recording = []
    is_recording = True

    def callback(indata, frames, time, status):
        nonlocal is_recording
        if is_recording:
            recording.append(indata.copy())

    print("Recording... Press space to stop.")

    with sd.InputStream(
        samplerate=SAMPLERATE,
        channels=CHANNELS,
        dtype="float32",
        callback=callback
    ):
        keyboard.wait("space")
        is_recording = False

    print("Saving file...")
    audio_data = np.concatenate(recording, axis=0)
    sf.write("test.wav", audio_data, SAMPLERATE)
    print("Done. Saved as test.wav")

    if os.path.exists("test.wav"):
        result = _model.transcribe("test.wav")
        text = result["text"]
        print("TEXT:", text)
        os.remove("test.wav")
        return text

    return ""


if __name__ == "__main__":
    while True:
        text = get_transcription()
        if text:
            send = input("Send? (Enter y if u have to): ")
            if send == "y":
                print("Transcription:", text)
        wait = input("Enter q to stop: ")
        if wait == "q":
            break