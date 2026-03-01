import sys
import io
import threading
from new_arch import send_to_llm, get_transcription
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout,
                             QWidget, QTextEdit, QLabel)

class TranscriptionThread(QThread):
    transcription_received = pyqtSignal(str)

    def run(self):
        text = get_transcription()
        self.transcription_received.emit(text)

class SendToLLMThread(QThread):
    finished = pyqtSignal()
    log_message = pyqtSignal(str)
    # Signal to request user choice: (prompt, option_list)
    choice_requested = pyqtSignal(str, list)

    def __init__(self, text):
        super().__init__()
        self.text = text
        # Used to wait for the GUI to provide the user's choice
        self._choice_event = threading.Event()
        self._choice_result = None

    def gui_chooser(self, prompt, options):
        """Called from the worker thread. Emits a signal and blocks
        until the main thread sets the result via set_choice()."""
        self._choice_event.clear()
        self._choice_result = None
        self.choice_requested.emit(prompt, options)
        self._choice_event.wait()  # Block until GUI responds
        return self._choice_result

    def set_choice(self, selected):
        """Called from the main thread to unblock gui_chooser()."""
        self._choice_result = selected
        self._choice_event.set()

    def run(self):
        # Redirect stdout so print() calls in new_arch go to the GUI
        old_stdout = sys.stdout
        sys.stdout = StreamRedirector(self.log_message)
        try:
            send_to_llm(self.text, chooser=self.gui_chooser)
        finally:
            sys.stdout = old_stdout
        self.finished.emit()


class StreamRedirector(io.TextIOBase):
    """Redirects writes to a pyqtSignal(str)."""
    def __init__(self, signal):
        super().__init__()
        self._signal = signal

    def write(self, text):
        if text and text.strip():
            self._signal.emit(text)
        return len(text)

    def flush(self):
        pass
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("My PyQt5 App")

        # Create a button
        self.button = QPushButton("Click Me")
        self.button.clicked.connect(self.on_button_click)
        self.voice = QPushButton("Voice Command")
        self.voice.clicked.connect(self.on_voice_click)
        self.inputbox = QTextEdit()

        # Output textbox for logs
        self.output_label = QLabel("Output:")
        self.output = QTextEdit()
        self.output.setReadOnly(True)

        # Set the central widget
        central_widget = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(self.button)
        layout.addWidget(self.voice)
        layout.addWidget(self.inputbox)
        layout.addWidget(self.output_label)
        layout.addWidget(self.output)
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        # State for waiting on user choice
        self._waiting_for_choice = False
        self._choice_options = []

    def on_button_click(self):
        if self._waiting_for_choice:
            # User is submitting a serial number choice
            self._submit_choice()
            return

        self.button.setEnabled(False)
        self.button.setText("Sending to LLM...")
        print("Button was clicked!")
        print("Input text:", self.inputbox.toPlainText())

        self.thread = SendToLLMThread(self.inputbox.toPlainText())
        self.thread.log_message.connect(self.append_output)
        self.thread.choice_requested.connect(self.on_choice_requested)
        self.thread.finished.connect(self.on_command_received)
        self.thread.start()
        self.inputbox.clear()

    def _submit_choice(self):
        """Read the sl no from the inputbox and unblock the worker thread."""
        text = self.inputbox.toPlainText().strip()

        if not self._choice_options:
            # Free text input mode (e.g. rename, move) — return raw text
            selected = text
        else:
            # Selection mode — pick from the options list by index
            try:
                idx = int(text) - 1
                if 0 <= idx < len(self._choice_options):
                    selected = self._choice_options[idx]
                else:
                    self.append_output(f"Invalid number. Defaulting to first option.")
                    selected = self._choice_options[0]
            except ValueError:
                self.append_output(f"Invalid input. Defaulting to first option.")
                selected = self._choice_options[0]

        self.inputbox.clear()
        self._waiting_for_choice = False
        self._choice_options = []
        self.button.setEnabled(False)
        self.button.setText("Sending to LLM...")
        self.thread.set_choice(selected)

    def on_command_received(self):
        self._waiting_for_choice = False
        self._choice_options = []
        self.button.setEnabled(True)
        self.button.setText("Click Me")
        self.inputbox.setFocus()

    def append_output(self, text):
        self.output.append(text)

    def on_choice_requested(self, prompt, options):
        """Show options in the output box and let the user type the sl no."""
        self._choice_options = options
        self._waiting_for_choice = True
        self.append_output(prompt)
        self.button.setEnabled(True)
        self.button.setText("Submit Choice")
        self.inputbox.setFocus()

    def on_voice_click(self):
        print("Voice command activated!")
        self.voice.setEnabled(False)
        self.voice.setText("Listening...")

        self.thread = TranscriptionThread()
        self.thread.transcription_received.connect(self.on_transcription_received)
        self.thread.start()

    def on_transcription_received(self, text):
        self.inputbox.setText(text)
        self.voice.setEnabled(True)
        self.voice.setText("Voice Command")
        self.inputbox.setFocus()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())