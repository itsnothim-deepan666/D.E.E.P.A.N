import whisper
import time

model = whisper.load_model("small", device="cuda")

while True:
    file = input("Enter wav path: ")
    if file == "q":
        break
    t0 = time.time()
    result = model.transcribe(file)
    print(result["text"])
    print(f"Time taken: {time.time() - t0:.2f} seconds")