import sys
import queue
import multiprocessing as mp
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from schema import Event
from mic import mic_worker
from router import router_worker
from intent_engine import intent_worker
from executor import executor_worker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("D.E.E.P.A.N")
        self.resize(760, 580)

        self.ctx = mp.get_context("spawn")
        self.event_queue = self.ctx.Queue(maxsize=200)
        self.intent_queue = self.ctx.Queue(maxsize=200)
        self.executor_queue = self.ctx.Queue(maxsize=200)
        self.ui_queue = self.ctx.Queue(maxsize=200)
        self.pipeline_stop_event = self.ctx.Event()
        self.mic_stop_event = self.ctx.Event()

        self._backend_processes = []
        self._mic_process = None

        self._setup_ui()
        self._start_backend()

        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self._poll_results)
        self.poll_timer.start(120)

    # ------------------------------------------------------------------ UI --

    def _setup_ui(self):
        container = QWidget()
        layout = QVBoxLayout()

        layout.addWidget(QLabel("D.E.E.P.A.N  —  voice or text → router → intent → executor"))

        # Text input row
        self.input_box = QTextEdit()
        self.input_box.setFixedHeight(60)
        self.input_box.setPlaceholderText("Type a command here… (e.g. open downloads)")

        self.send_button = QPushButton("Send")
        self.send_button.setFixedWidth(80)
        self.send_button.clicked.connect(self.on_send_text)

        text_row = QHBoxLayout()
        text_row.addWidget(self.input_box)
        text_row.addWidget(self.send_button)
        layout.addLayout(text_row)

        # Voice button
        self.mic_button = QPushButton("🎙  Start Listening")
        self.mic_button.setCheckable(True)
        self.mic_button.clicked.connect(self.on_mic_toggle)
        layout.addWidget(self.mic_button)

        self.mic_status = QLabel("Mic: off")
        layout.addWidget(self.mic_status)

        # Output
        layout.addWidget(QLabel("Pipeline Output:"))
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)

        self.clear_button = QPushButton("Clear Output")
        self.clear_button.clicked.connect(self.output.clear)
        layout.addWidget(self.clear_button)

        container.setLayout(layout)
        self.setCentralWidget(container)

    # -------------------------------------------------------- backend start --

    def _start_backend(self):
        """Start router, intent, executor — but NOT the mic process."""
        router_process = self.ctx.Process(
            target=router_worker,
            args=(self.event_queue, self.intent_queue, self.ui_queue, self.pipeline_stop_event),
            name="RouterProcess",
        )
        intent_process = self.ctx.Process(
            target=intent_worker,
            args=(self.intent_queue, self.executor_queue, self.pipeline_stop_event),
            name="IntentProcess",
        )
        executor_process = self.ctx.Process(
            target=executor_worker,
            args=(self.executor_queue, self.event_queue, self.pipeline_stop_event),
            name="ExecutorProcess",
        )

        self._backend_processes = [router_process, intent_process, executor_process]
        for p in self._backend_processes:
            p.start()

        self._append("[GUI] Backend pipeline ready. Press Start Listening or type a command.")

    # --------------------------------------------------------- mic control --

    def on_mic_toggle(self, checked: bool):
        if checked:
            self._start_mic()
        else:
            self._stop_mic()

    def _start_mic(self):
        if self._mic_process and self._mic_process.is_alive():
            return

        self.mic_stop_event.clear()
        self._mic_process = self.ctx.Process(
            target=mic_worker,
            args=(self.event_queue, self.mic_stop_event),
            name="MicProcess",
        )
        self._mic_process.start()
        self.mic_button.setText("🔴  Stop Listening")
        self.mic_status.setText("Mic: listening…  (press SPACE to flush speech)")
        self._append("[GUI] Mic started. Speak now — press SPACE to send current speech.")

    def _stop_mic(self):
        self.mic_stop_event.set()
        if self._mic_process:
            self._mic_process.join(timeout=4)
            if self._mic_process.is_alive():
                self._mic_process.terminate()
                self._mic_process.join(timeout=2)
            self._mic_process = None

        self.mic_button.setText("🎙  Start Listening")
        self.mic_button.setChecked(False)
        self.mic_status.setText("Mic: off")
        self._append("[GUI] Mic stopped.")

    # ---------------------------------------------------------- text input --

    def on_send_text(self):
        text = self.input_box.toPlainText().strip()
        if not text:
            return

        event = Event.create(
            event_type="TEXT_INPUT",
            source="gui_text",
            payload=text,
            confidence=None,
        )
        self.event_queue.put(event)
        self._append(f"[GUI] Sent: {text}")
        self.input_box.clear()

    # ------------------------------------------------------------ polling --

    def _poll_results(self):
        # Check if mic process died unexpectedly
        if (
            self._mic_process is not None
            and not self._mic_process.is_alive()
            and self.mic_button.isChecked()
        ):
            self._append("[GUI] Mic process ended unexpectedly.")
            self._stop_mic()

        while True:
            try:
                event = self.ui_queue.get_nowait()
            except queue.Empty:
                break

            if not isinstance(event, Event):
                self._append(f"[GUI] Unknown message: {event}")
                continue

            if event.event_type == "RESULT_EVENT":
                payload = event.payload if isinstance(event.payload, dict) else {"message": str(event.payload)}
                status = payload.get("status", "unknown")
                action = payload.get("action", "")
                message = payload.get("message", "")
                self._append(f"[RESULT] {status} | {action} | {message}")
            else:
                self._append(f"[{event.event_type}] {event.payload}")

    def _append(self, text: str):
        self.output.append(text)

    # ------------------------------------------------------- clean shutdown --

    def _shutdown(self):
        self._stop_mic()

        self.pipeline_stop_event.set()
        for q in (self.event_queue, self.intent_queue, self.executor_queue):
            try:
                q.put_nowait(None)
            except Exception:
                pass

        for p in self._backend_processes:
            p.join(timeout=3)
            if p.is_alive():
                p.terminate()
                p.join(timeout=2)

    def closeEvent(self, event):
        self.poll_timer.stop()
        self._append("[GUI] Shutting down…")
        self._shutdown()
        event.accept()


if __name__ == "__main__":
    mp.freeze_support()
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
