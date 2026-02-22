import os
import ollama
import record_mic as rm
import shutil, os

MODEL = "phi"

# Record from mic and get the transcribed text
user_text = rm.get_transcription()
command = {}
if user_text:
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

Allowed schema:
{
  "action": string,
  "value": string
}

Allowed actions:
copy
paste
delete
type_text
open_app
open_directory
go_back
"""
            },
            {
                "role": "user",
                "content": user_text
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
    print(response["message"]["content"])
else:
    print("No transcription received.")

if command:
    action = command.get("action")
    value = command.get("value")
    if action == "delete":
        if value in os.listdir():
            if os.path.isfile(value):
                os.remove(value)
                print(f"Deleted file: {value}")
            elif os.path.isdir(value):
                shutil.rmtree(value)
                print(f"Deleted directory: {value}")
    elif action == "open_directory":
        os.system(f"explorer {value}")
    # Add more actions as needed