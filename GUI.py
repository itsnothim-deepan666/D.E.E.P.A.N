import sys
from new_arch import send_to_llm
import PyQt5
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QTextEdit

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("My PyQt5 App")

        # Create a button
        self.button = QPushButton("Click Me")
        self.button.clicked.connect(self.on_button_click)
        self.inputbox = QTextEdit()

        # Set the central widget
        central_widget = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(self.button)
        layout.addWidget(self.inputbox)
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

    def on_button_click(self):
        print("Button was clicked!")
        print("Input text:", self.inputbox.toPlainText())
        send_to_llm(self.inputbox.toPlainText())
        self.inputbox.clear()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())