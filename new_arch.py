import json
from difflib import get_close_matches
import sounddevice as sd
import soundfile as sf
import whisper
import torch
import numpy as np
import keyboard
import ollama
import shutil, os
import sqlite3

conn = sqlite3.connect("files.db")
cursor = conn.cursor()
files = cursor.execute("SELECT name, path FROM files").fetchall()
directories = cursor.execute("SELECT name, path FROM directories").fetchall()

MODEL = "llama3:8b-instruct-q4_0"  # Ollama model name

ALLOWED_ACTIONS = [
    "open",
    "delete",
    "list_directory",
    "get_size",
    "show_space",
    "navigate",
    "go_back",
    "copy",
    "paste",
    "type_text",
    "rename",
    "move",
]

SAMPLERATE = 16000   # Whisper native rate
CHANNELS = 1         # Mono

# Load model once so it's reused across calls
_model = whisper.load_model("medium", device="cuda")

def get_close_action(word, target):
    matches = get_close_matches(word, target, n=1, cutoff=0.6)
    return matches[0] if matches else None

def get_close_file_or_dir(name):
    if not name:
        return None
    all_names = [f[0].lower() for f in files] + [d[0].lower() for d in directories]
    matches = get_close_matches(name.lower(), all_names, n=1, cutoff=0.6)
    if not matches:
        return None
    out = []
    match = matches[0]
    for f in files:
        if f[0].lower() == match:
            out.append(f[1])
    for d in directories:
        if d[0].lower() == match:
            out.append(d[1])
    return out if out else None

def check_files_and_directories(value, chooser=None):
    """Look up value in the DB using fuzzy matching.
    If multiple matches, ask the user to pick one.
    
    chooser: optional callable(prompt_str, options_list) -> selected_option_str
             Defaults to terminal input() when None.
    """
    paths = get_close_file_or_dir(value)
    if not paths:
        return None
    if len(paths) == 1:
        return paths[0]

    # Multiple matches – ask user to choose
    prompt = (f"Multiple matches found for '{value}'. Choose one:\n"
              + "\n".join(f"{i+1}. {opt}" for i, opt in enumerate(paths))
              + "\nEnter number: ")
    if chooser is not None:
        selected = chooser(prompt, paths)
        return selected
    else:
        op = input(prompt)
        try:
            return paths[int(op) - 1]
        except:
            print("Invalid choice. Defaulting to first option.")
            return paths[0]

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
        return {"action": "delete", "value": text.replace("delete", "", 1).strip()}
    elif "type" in text:
        return {"action": "type_text", "value": text.replace("type", "", 1).strip()}
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
- "open"            -> value: the app, file, folder, or thing to open
- "delete"          -> value: file or folder name to delete
- "list_directory"  -> value: directory name to list (or "" for current directory)
- "get_size"        -> value: file or folder name to get size of
- "show_space"      -> value: "" (shows disk space)
- "navigate"        -> value: directory name to navigate to
- "go_back"         -> value: "" (go to parent directory)
- "copy"            -> value: "" (copies current selection)
- "paste"           -> value: "" (pastes clipboard)
- "type_text"       -> value: the text to type
- "rename"          -> value: file or folder name to rename
- "move"            -> value: file or folder name to move

Examples:
User: "Open documents"       -> {"action": "open", "value": "documents"}
User: "Delete my_file.txt"   -> {"action": "delete", "value": "my_file.txt"}
User: "Type hello world"     -> {"action": "type_text", "value": "hello world"}
User: "Copy the selection"   -> {"action": "copy", "value": ""}
User: "Go back"              -> {"action": "go_back", "value": ""}
User: "Open Chrome"          -> {"action": "open", "value": "Chrome"}
User: "Show desktop"         -> {"action": "list_directory", "value": "desktop"}
User: "How much space"       -> {"action": "show_space", "value": ""}
User: "Rename report.pdf"    -> {"action": "rename", "value": "report.pdf"}
User: "Move my_file.txt"     -> {"action": "move", "value": "my_file.txt"}
User: "Navigate to downloads" -> {"action": "navigate", "value": "downloads"}
User: "Size of photos"       -> {"action": "get_size", "value": "photos"}
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
            command = json.loads(command)  # Convert string to dict
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

def execute(command, chooser=None):
    print("Executing Command:", command)
    raw_action = command.get("action")
    if not raw_action:
        print("No action provided in command.")
        return
    action = get_close_action(raw_action, ALLOWED_ACTIONS)
    value = command.get("value", "").strip()

    if not action:
        print(f"Unknown action '{raw_action}'. No close match found in allowed actions.")
        return

    if action == "delete":
        value_ = check_files_and_directories(value, chooser=chooser)
        if value_:
            if os.path.isfile(value_):
                os.remove(value_)
                print(f"Deleted file: {value_}")
            elif os.path.isdir(value_):
                shutil.rmtree(value_)
                print(f"Deleted directory: {value_}")
            else:
                print(f"Path exists but is neither file nor directory: {value_}")
        else:
            print(f"No matching file or directory for '{value}'.")

    elif action == "open":
        value_ = check_files_and_directories(value, chooser=chooser)
        if value_:
            os.startfile(value_)
        else:
            print(f"Trying to open '{value}' as shell folder...")
            shell_path = SHELL_FOLDERS.get(value.lower())
            if shell_path:
                os.startfile(shell_path)
            else:
                print(f"No matching file, directory, or shell folder found for '{value}'.")

    elif action == "list_directory":
        value_ = check_files_and_directories(value, chooser=chooser) if value else os.getcwd()
        if value_ and os.path.isdir(value_):
            contents = os.listdir(value_)
            print(f"Contents of '{value_}':")
            for item in contents:
                print(f"  {item}")
        else:
            print(f"No matching directory found for '{value}'.")

    elif action == "get_size":
        value_ = check_files_and_directories(value, chooser=chooser)
        if value_:
            if os.path.isfile(value_):
                size = os.path.getsize(value_)
                print(f"Size of '{value_}': {size} bytes ({size / 1024:.2f} KB)")
            elif os.path.isdir(value_):
                total = sum(
                    os.path.getsize(os.path.join(dp, f))
                    for dp, _, fnames in os.walk(value_)
                    for f in fnames
                )
                print(f"Size of '{value_}': {total} bytes ({total / (1024*1024):.2f} MB)")
        else:
            print(f"No matching file or directory for '{value}'.")

    elif action == "show_space":
        usage = shutil.disk_usage(os.getcwd())
        print(f"Disk space — Total: {usage.total / (1024**3):.2f} GB, "
              f"Used: {usage.used / (1024**3):.2f} GB, "
              f"Free: {usage.free / (1024**3):.2f} GB")

    elif action == "navigate":
        value_ = check_files_and_directories(value, chooser=chooser)
        if value_:
            if os.path.isdir(value_):
                os.chdir(value_)
                print(f"Navigated to: {os.getcwd()}")
            else:
                # Navigate to the parent directory of a file
                parent = os.path.dirname(value_)
                os.chdir(parent)
                print(f"Navigated to parent directory: {os.getcwd()}")
        else:
            shell_path = SHELL_FOLDERS.get(value.lower())
            if shell_path:
                os.startfile(shell_path)
            else:
                print(f"No matching directory found for '{value}'.")

    elif action == "go_back":
        parent = os.path.dirname(os.getcwd())
        if parent and parent != os.getcwd():
            os.chdir(parent)
            print(f"Went back to: {os.getcwd()}")
        else:
            print("Already at the root directory.")

    elif action == "copy":
        keyboard.send("ctrl+c")
        print("Sent Ctrl+C (copy).")

    elif action == "paste":
        keyboard.send("ctrl+v")
        print("Sent Ctrl+V (paste).")

    elif action == "type_text":
        if value:
            keyboard.write(value)
            print(f"Typed: {value}")
        else:
            print("No text provided to type.")

    elif action == "rename":
        value_ = check_files_and_directories(value, chooser=chooser)
        if value_:
            prompt = f"Enter new name for '{os.path.basename(value_)}': "
            if chooser is not None:
                new_name = chooser(prompt, [])  # empty list = free text input
            else:
                new_name = input(prompt)
            new_name = (new_name or "").strip()
            if new_name:
                new_path = os.path.join(os.path.dirname(value_), new_name)
                os.rename(value_, new_path)
                print(f"Renamed '{value_}' -> '{new_path}'")
            else:
                print("No new name provided. Rename cancelled.")
        else:
            print(f"No matching file or directory for '{value}'.")

    elif action == "move":
        value_ = check_files_and_directories(value, chooser=chooser)
        if value_:
            prompt = f"Enter destination path for '{os.path.basename(value_)}': "
            if chooser is not None:
                dest = chooser(prompt, [])  # empty list = free text input
            else:
                dest = input(prompt)
            dest = (dest or "").strip()
            if dest:
                dest_path = check_files_and_directories(dest, chooser=chooser) or dest
                shutil.move(value_, dest_path)
                print(f"Moved '{value_}' -> '{dest_path}'")
            else:
                print("No destination provided. Move cancelled.")
        else:
            print(f"No matching file or directory for '{value}'.")


def send_to_llm(text, chooser=None):
    rule = rule_engine(text)
    if rule:
        print("Rule Engine Matched. Executing...")
        print("Parsed Command:", rule)
        execute(rule, chooser=chooser)
                    
    else:
        print("No rule matched. Sending to LLM...")
        unload_whisper()  # Free GPU VRAM for Ollama
        try:
            command = llm(text)
            print("Parsed Command:", command)
            execute(command, chooser=chooser)
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