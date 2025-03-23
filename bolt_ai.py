import requests
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QLineEdit, QPushButton
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QTextCursor

class BoltAIWorker(QThread):
    """Worker thread to handle AI responses from Ollama via API"""
    response_ready = pyqtSignal(str)

    def __init__(self, prompt: str):
        super().__init__()
        self.prompt = prompt

    def run(self):
        try:
            # Use Ollama's REST API to generate a response
            url = "http://localhost:11434/api/generate"
            payload = {
                "model": "qwen2.5-coder:3b",
                "prompt": self.prompt,
                "stream": False  # Get full response at once
            }
            response = requests.post(url, json=payload)
            if response.status_code == 200:
                result = response.json()
                self.response_ready.emit(result["response"])
            else:
                self.response_ready.emit(f"Error: API returned status {response.status_code} - {response.text}")
        except requests.exceptions.ConnectionError:
            self.response_ready.emit("Error: Could not connect to Ollama server. Is it running?")
        except Exception as e:
            self.response_ready.emit(f"Error: {str(e)}")


class BoltAI(QWidget):
    """Bolt AI chat interface for coding assistance"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.worker: BoltAIWorker = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Chat display
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("""
            background-color: #262626;
            color: #D4D4D4;
            border: none;
            padding: 5px;
        """)
        self.chat_display.append("Bolt AI: Hello! I'm here to help with coding questions and provide code examples.")
        layout.addWidget(self.chat_display)

        # Input field
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Ask Bolt AI about coding...")
        self.input_field.setStyleSheet("""
            background-color: #2D2D2D;
            color: #D4D4D4;
            border: 1px solid #555555;
            padding: 5px;
        """)
        self.input_field.returnPressed.connect(self.send_message)
        layout.addWidget(self.input_field)

        # Send button
        send_button = QPushButton("Send")
        send_button.setStyleSheet("""
            background-color: #0E639C;
            color: white;
            padding: 5px;
        """)
        send_button.clicked.connect(self.send_message)
        layout.addWidget(send_button)

    def send_message(self):
        message = self.input_field.text().strip()
        if not message:
            return

        # Display user message
        self.chat_display.append(f"<b>You:</b> {message}")
        self.input_field.clear()

        # Start worker thread to get AI response
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait()

        self.worker = BoltAIWorker(message)
        self.worker.response_ready.connect(self.display_response)
        self.worker.start()

    def display_response(self, response: str):
        self.chat_display.append(f"<b>Bolt AI:</b> {response}")
        self.chat_display.moveCursor(QTextCursor.End)
        if self.worker:
            self.worker.deleteLater()
            self.worker = None


if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    import sys
    app = QApplication(sys.argv)
    window = BoltAI()
    window.show()
    sys.exit(app.exec_())