import sounddevice as sd
import soundfile as sf
import whisper
import torch
import os
import numpy as np
import keyboard
import os
import ollama
import shutil, os

MODEL = "llama3:8b-instruct-q4_0"  # Ollama model name

SAMPLERATE = 16000   # Whisper native rate
CHANNELS = 1         # Mono

# Load model once so it's reused across calls
_model = whisper.load_model("medium", device="cuda")

def unload_whisper():
    """Move Whisper model to CPU and free GPU VRAM for Ollama."""
    global _model
    _model.cpu()
    torch.cuda.empty_cache()

def reload_whisper():
    """Move Whisper model back to GPU."""
    global _model
    _model.cuda()

def normalize_text(text):
    return text.strip().lower()

def rule_engine(text):
    text = normalize_text(text)
    if "copy" in text:
        return {"action": "copy", "value": ""}
    elif "paste" in text:
        return {"action": "paste", "value": ""}
    elif "delete" in text:
        return {"action": "delete", "value": ""}
    elif "type" in text:
        return {"action": "type_text", "value": text.replace("type", "", 1).strip()}
    elif "open app" in text:
        return {"action": "open_app", "value": text.replace("open app", "", 1).strip()} 
    elif "open" in text:
        return {"action": "open", "value": text.replace("open", "", 1).strip()}
    elif "go back" in text:
        return {"action": "go_back", "value": ""}
    else:
        return {}

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

    return None

def llm(command):
    if command:
        response = ollama.chat(
        format="json",
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": """
You are a command parser.

Output ONLY valid JSON.
No explanations.
No extra text.
If the value is not specified, return an empty string for value.

Allowed schema:
{
  "action": string,
  "value": string
}

Allowed actions and what "value" should contain:
- "copy"      -> value: what to copy (or "" if unspecified)
- "paste"     -> value: "" (no target needed)
- "delete"    -> value: file or folder name to delete
- "type_text" -> value: the text to type
- "open"      -> value: the app, file, folder, or thing to open
- "go_back"   -> value: "" (no target needed)

Examples:
User: "Open documents"       -> {"action": "open", "value": "documents"}
User: "Delete my_file.txt"   -> {"action": "delete", "value": "my_file.txt"}
User: "Type hello world"     -> {"action": "type_text", "value": "hello world"}
User: "Copy the selection"   -> {"action": "copy", "value": ""}
User: "Go back"              -> {"action": "go_back", "value": ""}
User: "Open Chrome"          -> {"action": "open", "value": "Chrome"}
"""
            },
            {
                "role": "user",
                "content": command
            }
        ],
        options={"num_predict": 40, "temperature": 0}
    )
        command = response.get("message", {}).get("content", "")
        try:
            command = eval(command)  # Convert string to dict
        except Exception as e:
            print("Error parsing command:", e)
            command = {}
        return command
    else:
        print("No transcription received.")
        return {}

SHELL_FOLDERS = {
    "download": "shell:Downloads",
    "documents": "shell:Documents",
    "desktop":   "shell:Desktop",
    "pictures":  "shell:Pictures",
    "music":     "shell:Music",
    "videos":    "shell:Video",
}

def execute(command):
    print("Executing Command:", command)
    action = command.get("action")
    value = command.get("value", "").strip()
    if action == "delete":
        if value in os.listdir("."):
            if os.path.isfile(value):
                os.remove(value)
                print(f"File {value} is removed")
            elif os.path.isdir(value):
                shutil.rmtree(value)
                print(f"Directory {value} is removed")
    elif action == "open":
        target = SHELL_FOLDERS.get(value.lower(), value)
        print(f"Opening: {target}")
        os.system(f'explorer "{target}"')

def send_to_llm(text):
    if rule_engine(text)  :
        print("Rule Engine Matched. Executing...")
        print("Parsed Command:", rule_engine(text))
        execute(rule_engine(text))
                    
    else:
        print("No rule matched. Sending to LLM...")
        unload_whisper()  # Free GPU VRAM for Ollama
        try:
            print("Parsed Command:", llm(text))
            execute(llm(text))
        finally:
            reload_whisper()  # Restore Whisper to GPU


if __name__ == "__main__":  
    while True:
        text = get_transcription()
        if text:
            send = input("Send? (Enter y if u have to): ")
            if send.strip().lower() == "y":
                print("Transcription:", text)
                send_to_llm(text)
            else:
                pass
                    
        wait = input("Enter q to stop: ")
        if wait.strip().lower() == "q":
            break