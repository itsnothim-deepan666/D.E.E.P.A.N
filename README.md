# D.E.E.P.A.N  
**Deep Embedded Execution & Personal Assistant Network**

okay so this whole thing started because i had this idea that just wouldn't leave me alone.

what if i could just... talk to my laptop? and it actually does stuff?

not like "hey siri what's the weather" kinda thing. i mean real stuff. open my files. delete folders. move things around. all by just speaking. and everything running locally — no cloud, no APIs, nothing leaving my machine.

so yeah, i started building it.

---

## 23rd February 2026 — the idea that wouldn't shut up

honestly it was pretty simple in my head:

i talk. the system does things.

no remote APIs. no external servers doing the thinking. everything runs on my hardware.

one rule i set for myself early on — if it can't run offline, it doesn't count.

---

## 24th February 2026 — getting the mic to work

started from scratch. first question was — how do i even get audio input in python?

found `sounddevice`, set it up at 16kHz mono (that's what Whisper likes), wrote a callback loop to record, saved it as a WAV file.

then loaded up Whisper (the `medium` model) on my GPU.

spoke into the mic.

and it actually transcribed what i said.

took me a few tries to figure out which Whisper model worked best — too small and it was garbage, too big and my GPU screamed. `medium` hit the sweet spot.

nothing was actually happening yet, no actions or anything. but seeing my own words show up on screen from just speaking? that felt like progress.

---

## 25th February 2026 — plugging in a brain

cool, i had text. but text by itself doesn't do anything.

so i brought in **Ollama** — basically lets you run LLMs locally. perfect for what i needed.

i didn't want it to be chatty or explain things. i just needed it to spit out structured JSON:

```json
{"action": "...", "value": "..."}
```

kinda felt harsh honestly, taking a language model and forcing it to be a dumb command parser. but that was exactly the point.

so when i said "Open Downloads", instead of some paragraph response, it just returned:

```json
{"action": "open", "value": "Downloads"}
```

and that triggered actual code. for the first time, i spoke and the computer did something.

was it rough? yeah. fragile? absolutely. but it worked.

> **Commit: `b4256e4` — First Commit**

---

## 26th February 2026 — giving it a face

up to this point everything was terminal-only. functional but ugly lol.

so i built a GUI using PyQt5. nothing fancy — just a voice button, a text box, and an output area.

the tricky part was making sure the UI didn't freeze while recording or processing. so threads everywhere. background recording, background LLM calls, all feeding back to the UI through signals.

but once it was running as a desktop app? it just felt different. like it went from being a script i was playing with to something i could actually use.

> **Commit: `242677d` — Added GUI**

---

## 27th February 2026 — the filesystem problem

then it broke lol.

"open documents" only worked if i hardcoded the path. that's not intelligent, that's just pretending.

so i built a file system crawler. it walks the entire `C:\` drive using `os.walk` and dumps everything into a SQLite database — file names, paths, extensions, sizes, timestamps. same for directories.

the first crawl took a while. drive spinning, CPU going brrr.

but once it finished? now the system actually *knew* where things were. "open downloads" wasn't a guess anymore — it was a database query.

that's when it stopped feeling like a script and started feeling like a system.

> **Commit: `95a11b0` — added crawler**

---

## 28th February 2026 — cleaning up the mess + handling typos

at this point i had all the pieces — mic, transcription, LLM, execution, file index — but they were all scattered across different files.

so i merged everything into one clean pipeline:

1. load the database
2. record voice
3. transcribe with Whisper
4. try the rule engine first (why burn GPU on "go back"?)
5. if no rule matches, send to the LLM
6. fuzzy-match the result against real files
7. execute

oh and fun problem — Whisper and Ollama were fighting over GPU memory. had to manually swap Whisper to CPU before calling the LLM, then bring it back after. kinda hacky but it works.

then came the next headache: voice input is messy. whisper mishears stuff. if i said "opn repotr" the whole thing would just crash.

so i added fuzzy matching using `difflib.get_close_matches`. tested it with a bunch of typos, tuned the threshold to 0.6. now "opn" correctly matches to "open", "delet" matches "delete", etc.

also had to handle ambiguity — what if "report" matches 5 different files? the system shouldn't just pick one and hope for the best. especially not for delete lol.

so i built a chooser. when there's multiple matches, it pauses, shows the options, and waits for the user to pick. felt like the right thing to do.

> **Commit: `ffce34c` — DB checks**

---

## 1st March 2026 — fixing the gui + docker

the gui was working but not cleanly with the new backend. rename and move were still using `input()` which just blocks forever in a GUI thread — oops.

fixed it by routing everything through the chooser callback. free-text input for things like rename (where you need to type a new name), numbered selection for disambiguation.

gui and backend finally playing nice together.

then i containerized the whole thing. CUDA base image, audio deps, GPU passthrough — runs clean inside Docker. portable, isolated, repeatable.

> **Commit: `ae02f5c` — GUI fix**

---

## 12th March 2026 — rethinking the whole architecture

So i hit a wall. the old pipeline was working, but it was one big chain — record, transcribe, parse, execute — all in one process, all tangled together. if one thing crashed, everything died. and i had to press spacebar every single time to start and stop recording. not exactly "hands-free".

So i rewrote the voice input from scratch.

Brought in **WebRTC VAD** (Voice Activity Detection). Now the mic runs continuously and automatically detects when i start and stop speaking. No button presses, no manual triggers. just talk and it picks it up.

Switched Whisper from `medium` to `small` — still accurate enough, but way faster for real-time use.

Then came the big change: **multiprocessing**.

Split the system into separate OS processes:
- **mic process** — owns the microphone and Whisper. captures audio, detects speech, transcribes, and pushes structured `Event` objects onto a shared queue.
- **router process** — pulls events from the queue, logs them, measures latency. placeholder for the intent parsing layer.

Each process has its own Python GIL.

Built an `Event` dataclass to standardize everything — event ID, type, source, payload, timestamp, confidence. every piece of data flowing through the system now has structure and traceability.

Also added a proper stop mechanism — press **spacebar** and everything shuts down cleanly. A shared `multiprocessing.Event` flag gets set, the mic loop breaks, the router follows, all processes join. no orphaned threads, no zombie processes.

The old pipeline was fine as a prototype. but this is the foundation for something real.

```
mic (VAD + Whisper) → Event Queue → Router → [future: intent parser → executor]
```

The router still just logs events for now. wiring up the intent parsing and execution layer is next. but the architecture is ready for it.

> **Commit: `TBD` — multiprocess VAD architecture + stop key**

---

## 13th March 2026 — unified pipeline + gui control

today was about making the architecture actually usable.

i didn't want separate code paths anymore where voice goes one way and typed text goes another.

so i built a new mic gui that can do both:
- continuous mic input (with VAD + Whisper)
- manual text input from the gui textbox

both now follow the exact same backend path:

```
input (voice or text) -> router -> intent engine -> executor -> result event
```

that part mattered a lot. now i can test with typed commands quickly, and whatever works there also works through speech.

also changed the spacebar behavior in the mic worker. it's no longer a global shutdown trigger.

now space is a **push key**: it finalizes the currently buffered speech and sends it downstream immediately.

next big change: added an executor worker and wired result events back through the pipeline, so actions are no longer just recognized and printed as intent.

and for safety/accuracy, open actions now verify target locations against `files.db` first (with fuzzy matching), similar to the older architecture. only after db lookup fails does it fall back to known shell folders.

this was the first point where the new architecture started feeling complete instead of just experimental.

> **Commit: `TBD` — gui + executor + db-verified open path**

---

## 13th March 2026 (later) — on-demand mic instead of always-on

small but important UX fix.

the gui used to start the mic process immediately on launch. so the moment you opened the app, Whisper was loaded, the mic was hot, and the VAD loop was spinning in the background whether you wanted it or not. felt wrong.

changed it so the mic is completely off by default.

added a **Start Listening / Stop Listening** toggle button. when you click it, the mic process spawns fresh. when you click it again, the stop event is set and the process is joined cleanly.

the rest of the pipeline — router, intent engine, executor — still starts at launch. they need to be ready for text input before the mic is even involved. that part makes sense to keep always-on.

mic process now gets its own separate stop event. the backend processes get theirs. clean separation.

also added a status label so you can see at a glance whether the mic is active or not.

small change, but it means the system is quiet unless you explicitly tell it to listen.

> **Commit: `TBD` — on-demand mic toggle button**
