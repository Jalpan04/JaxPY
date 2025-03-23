import requests
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit, QPushButton, QApplication
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QTextCursor, QClipboard, QTextFormat


class BoltAIWorker(QThread):
    """Worker thread to handle AI responses from Ollama via API"""
    response_ready = pyqtSignal(str)

    def __init__(self, prompt: str):
        super().__init__()
        self.prompt = prompt

    def run(self):
        try:
            url = "http://localhost:11434/api/generate"
            payload = {
                "model": "qwen2.5-coder:3b",
                "prompt": self.prompt,
                "stream": False
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
    """Bolt AI chat interface for coding assistance with enhanced UI"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.worker: BoltAIWorker = None
        self.clipboard = QApplication.clipboard()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Chat display
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("""
            QTextEdit {
                background-color: #353535;
                color: #D4D4D4;
                border: none;
                padding: 15px;
                font-size: 14px;
            }
        """)
        self.chat_display.append("<b style='color: #ECDC51;'>Bolt AI:</b> Hello! I'm here to help with coding questions and provide code examples.")
        layout.addWidget(self.chat_display)

        # Input field and Send button container
        input_container = QWidget()
        input_layout = QHBoxLayout(input_container)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(8)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Ask Bolt AI about coding...")
        self.input_field.setStyleSheet("""
            QLineEdit {
                background-color: #1E1F22;
                color: #D4D4D4;
                border: 1px solid #555555;
                padding: 10px;
                font-size: 14px;
            }
        """)
        self.input_field.returnPressed.connect(self.send_message)
        input_layout.addWidget(self.input_field)

        send_button = QPushButton("Send")
        send_button.setStyleSheet("""
            QPushButton {
                background-color: #ECDC51;
                color: #1E1F22;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #FFC61A;
            }
        """)
        send_button.clicked.connect(self.send_message)
        input_layout.addWidget(send_button)

        layout.addWidget(input_container)

    def send_message(self):
        message = self.input_field.text().strip()
        if not message:
            return

        # Display user message
        self.chat_display.append(f"<b style='color: #FFC61A;'>You:</b> {message}")
        self.input_field.clear()

        # Start worker thread to get AI response
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait()

        self.worker = BoltAIWorker(message)
        self.worker.response_ready.connect(self.display_response)
        self.worker.start()

    def display_response(self, response: str):
        """Display AI response with code blocks and copy buttons"""
        parts = response.split("```")
        formatted_response = "<b style='color: #ECDC51;'>Bolt AI:</b> "

        for i, part in enumerate(parts):
            if i % 2 == 0:  # Text outside code blocks
                formatted_response += part.replace("\n", "<br>")
            else:  # Code inside code blocks
                # Detect language if specified (e.g., ```python)
                language = ""
                code_lines = part.strip().splitlines()
                if code_lines and not code_lines[0].startswith(" "):
                    language = code_lines[0].strip()
                    code = "\n".join(code_lines[1:]) if len(code_lines) > 1 else ""
                else:
                    code = part

                # Unique ID for the copy button
                button_id = f"copy_{id(self)}_{i}"
                formatted_response += f"""
                    <table style='width: 100%; margin: 8px 0;'>
                        <tr>
                            <td style='
                                background-color: #1E1F22;
                                color: #D4D4D4;
                                font-family: Consolas, monospace;
                                padding: 15px;
                                border: 1px solid #555555;
                                white-space: pre-wrap;
                                word-wrap: break-word;
                                font-size: 14px;'>{code}</td>
                            <td style='width: 100px; vertical-align: top;'>
                                <input type='button' value='Copy Code' id='{button_id}' 
                                    style='
                                        background-color: #ECDC51;
                                        color: #1E1F22;
                                        padding: 8px;
                                        border: none;
                                        cursor: pointer;
                                        font-size: 14px;
                                        font-weight: bold;'
                                    onmouseover='this.style.backgroundColor="#FFC61A"'
                                    onmouseout='this.style.backgroundColor="#ECDC51"'>
                            </td>
                        </tr>
                    </table>
                """
                # Delay binding the button click until the HTML is rendered
                QTimer.singleShot(100, lambda c=code, b=button_id: self._bind_copy_button(c, b))

        self.chat_display.append(formatted_response)
        self.chat_display.moveCursor(QTextCursor.End)
        if self.worker:
            self.worker.deleteLater()
            self.worker = None

    def _bind_copy_button(self, code: str, button_id: str):
        """Bind the copy button to copy the code to clipboard"""
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.Start)
        while cursor.movePosition(QTextCursor.NextBlock):
            block_text = cursor.block().text()
            if button_id in block_text:
                self.chat_display.setTextCursor(cursor)
                # Connect a signal to copy the code when clicked
                self.chat_display.document().find(f"id='{button_id}'").charFormat().setProperty(
                    QTextFormat.UserProperty, lambda: self._copy_to_clipboard(code))
                break

    def _copy_to_clipboard(self, code: str):
        """Copy the code to the clipboard"""
        self.clipboard.setText(code.strip())
        # Provide feedback
        self.chat_display.append("<i style='color: #FFC61A;'>Copied to clipboard!</i>")
        QTimer.singleShot(2000, lambda: self.chat_display.undo())  # Remove feedback after 2 seconds


if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    window = BoltAI()
    window.show()
    sys.exit(app.exec_())