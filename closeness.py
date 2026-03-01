from difflib import get_close_matches
import torch
import io

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

while True:  # --- Sample test for get_close_matches ---
    test_inputs = input("Enter a command: ").strip().lower()
    word = test_inputs.split()[0] if test_inputs else ""

    matches = get_close_matches(word, ALLOWED_ACTIONS, n=1, cutoff=0.6)
    if matches:
        print(f"'{word}' -> best match: '{matches[0]}'")
    else:
        print(f"'{word}' -> no close match found")