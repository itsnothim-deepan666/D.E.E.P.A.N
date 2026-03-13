import multiprocessing as mp
import queue
import os
import sqlite3
from difflib import get_close_matches
from intent_schema import Intent
from schema import Event

DB_PATH = "files.db"
FUZZY_CUTOFF = 0.6

SHELL_FOLDERS = {
    "download": "shell:Downloads",
    "downloads": "shell:Downloads",
    "document": "shell:Documents",
    "documents": "shell:Documents",
    "desktop": "shell:Desktop",
    "picture": "shell:Pictures",
    "pictures": "shell:Pictures",
    "music": "shell:Music",
    "video": "shell:Video",
    "videos": "shell:Video",
}


class DbPathResolver:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.name_to_paths = {}
        self.entry_count = 0
        self._ready = False
        self._load_index()

    def _add_key(self, key, path):
        key = (key or "").strip().lower()
        if not key:
            return
        existing = self.name_to_paths.setdefault(key, [])
        if path not in existing:
            existing.append(path)

    def _load_index(self):
        if not os.path.exists(self.db_path):
            print(f"[EXECUTOR] DB not found: {self.db_path}")
            self._ready = False
            return

        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            file_rows = cursor.execute("SELECT name, extension, path FROM files").fetchall()
            dir_rows = cursor.execute("SELECT name, path FROM directories").fetchall()

            for name, ext, path in file_rows:
                base_name = (name or "").strip()
                extension = (ext or "").strip()

                self._add_key(base_name, path)
                if extension:
                    self._add_key(f"{base_name}{extension}", path)

            for name, path in dir_rows:
                self._add_key(name, path)

            self.entry_count = len(self.name_to_paths)
            self._ready = self.entry_count > 0
            print(f"[EXECUTOR] DB index loaded: {self.entry_count} names.")

        except Exception as e:
            print(f"[EXECUTOR] Failed to load DB index: {e}")
            self._ready = False
        finally:
            if conn is not None:
                conn.close()

    def resolve(self, target):
        query = (target or "").strip().strip("\"'").lower()
        if not query or not self._ready:
            return []

        exact = self.name_to_paths.get(query)
        if exact:
            return exact

        matches = get_close_matches(query, list(self.name_to_paths.keys()), n=1, cutoff=FUZZY_CUTOFF)
        if not matches:
            return []

        return self.name_to_paths.get(matches[0], [])


def _execute_intent(intent: Intent, resolver: DbPathResolver):
    action = intent.action
    target = (intent.target or "").strip()

    if action in {"open_item", "open_folder"}:
        resolved_paths = resolver.resolve(target)
        if resolved_paths:
            selected_path = resolved_paths[0]
            try:
                os.startfile(selected_path)
            except Exception as e:
                return "error", f"Open failed for '{selected_path}': {e}"

            if len(resolved_paths) > 1:
                return "ok", f"Opened {selected_path} (first match for '{target}')."
            return "ok", f"Opened {selected_path}"

        shell_path = SHELL_FOLDERS.get(target.lower())
        try:
            if shell_path:
                os.startfile(shell_path)
                return "ok", f"Opened {target}"
        except Exception as e:
            return "error", f"Open failed: {e}"

        return "error", f"No matching file or directory found in files.db for '{target}'."

    if action == "shutdown_system":
        return "blocked", "Shutdown intent recognized, but execution is blocked by safety policy."

    if action == "unknown_command":
        return "no_intent", f"No intent recognized for: {intent.raw_text}"

    return "error", f"Unsupported action: {action}"


def executor_worker(executor_queue: mp.Queue, event_queue: mp.Queue, stop_event=None):
    print("[EXECUTOR] Started.")
    resolver = DbPathResolver(DB_PATH)

    while not (stop_event is not None and stop_event.is_set()):
        try:
            intent = executor_queue.get(timeout=0.5)
        except queue.Empty:
            continue

        if intent is None:
            break

        if not isinstance(intent, Intent):
            continue

        status, message = _execute_intent(intent, resolver)

        result_event = Event.create(
            event_type="RESULT_EVENT",
            source="executor_01",
            payload={
                "status": status,
                "message": message,
                "action": intent.action,
                "target": intent.target,
                "source_intent_id": intent.intent_id,
            },
            confidence=None,
        )

        event_queue.put(result_event)
        print(f"[EXECUTOR] {status}: {message}")

    print("[EXECUTOR] Stopped.")
