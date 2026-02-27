from pydoc import text
import sys
from new_arch import send_to_llm, get_transcription
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QTextEdit

class TranscriptionThread(QThread):
    transcription_received = pyqtSignal(str)

    def run(self):
        text = get_transcription()
        self.transcription_received.emit(text)

class SendToLLMThread(QThread):
    finished = pyqtSignal()
    def __init__(self, text):
        super().__init__()
        self.text = text

    def run(self):
        send_to_llm(self.text)
        self.finished.emit()
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

        # Set the central widget
        central_widget = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(self.button)
        layout.addWidget(self.voice)
        layout.addWidget(self.inputbox)
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

    def on_button_click(self):
        self.button.setEnabled(False)
        self.button.setText("Sending to LLM...")
        print("Button was clicked!")
        print("Input text:", self.inputbox.toPlainText())

        self.thread = SendToLLMThread(self.inputbox.toPlainText())
        self.thread.finished.connect(self.on_command_received)
        self.thread.start()
        self.inputbox.clear()

    def on_command_received(self, command):
        self.button.setEnabled(True)
        self.button.setText("Click Me")
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