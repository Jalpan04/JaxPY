import requests
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QTextEdit, QLineEdit,
                             QPushButton, QApplication, QHBoxLayout)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QTextCursor, QClipboard, QTextFormat, QFont, QPalette, QColor

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
    BUTTON_STYLE = """
        QPushButton {
            background-color: #353535;
            color: #ECDC51;
            border: 1px solid #FFC61A;
            padding: 6px 12px;
            border-radius: 6px;
            font-family: Consolas;
            font-weight: 600;
            font-size: 14px;
            transition: all 0.2s;
        }
        QPushButton:hover {
            background-color: #FFC61A;
            color: #1E1F22;
            border-color: #ECDC51;
            box-shadow: 0 0 8px rgba(236, 220, 81, 0.5);
        }
        QPushButton:pressed {
            background-color: #ECDC51;
            color: #1E1F22;
            border-color: #FFC61A;
            box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.2);
        }
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.worker: BoltAIWorker = None
        self.clipboard = QApplication.clipboard()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Chat display
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        font = QFont("Consolas", 10)
        font.setFixedPitch(True)
        self.chat_display.setFont(font)
        palette = QPalette()
        palette.setColor(QPalette.Base, QColor("#1E1F22"))
        palette.setColor(QPalette.Text, QColor("#D4D4D4"))
        self.chat_display.setPalette(palette)
        self.chat_display.setStyleSheet("""
            QTextEdit {
                border: 1px solid #353535;
                border-radius: 6px;
                padding: 8px;
                selection-background-color: #FFC61A;
                selection-color: #1E1F22;
            }
        """)
        self.chat_display.append(
            "<span style='color: #ECDC51; font-weight: 600;'>Bolt AI:</span> "
            "Hello! I'm here to help with coding questions and provide code examples."
        )
        layout.addWidget(self.chat_display)

        # Input layout with text input and send button
        input_layout = QHBoxLayout()
        input_layout.setSpacing(6)

        # Input field
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Ask Bolt AI about coding...")
        self.input_field.setFont(font)
        self.input_field.setStyleSheet("""
            QLineEdit {
                background-color: #2A2B2E;
                color: #D4D4D4;
                border: 1px solid #353535;
                padding: 6px;
                border-radius: 4px;
            }
            QLineEdit:focus {
                border-color: #FFC61A;
                box-shadow: 0 0 4px rgba(255, 198, 26, 0.5);
            }
        """)
        self.input_field.returnPressed.connect(self.send_message)
        input_layout.addWidget(self.input_field)

        # Send button
        send_button = QPushButton("Send")
        send_button.setStyleSheet(self.BUTTON_STYLE)
        send_button.clicked.connect(self.send_message)
        input_layout.addWidget(send_button)

        # Add input layout to main layout
        layout.addLayout(input_layout)

        self.setStyleSheet("""
            QWidget {
                background: #1E1F22;
            }
            QScrollBar:vertical, QScrollBar:horizontal {
                border: none;
                background: #2A2B2E;
                width: 10px;
                height: 10px;
                margin: 0;
            }
            QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
                background: #353535;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {
                background: #FFC61A;
            }
            QScrollBar::add-line, QScrollBar::sub-line {
                background: none;
            }
        """)

    def send_message(self):
        message = self.input_field.text().strip()
        if not message:
            return

        # Display user message
        self.chat_display.append(
            f"<span style='color: #FFC61A; font-weight: 600;'>You:</span> {message}"
        )
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
        formatted_response = "<span style='color: #ECDC51; font-weight: 600;'>Bolt AI:</span> "

        for i, part in enumerate(parts):
            if i % 2 == 0:  # Text outside code blocks
                formatted_response += part.replace("\n", "<br>")
            else:  # Code inside code blocks
                language = ""
                code_lines = part.strip().splitlines()
                if code_lines and not code_lines[0].startswith(" "):
                    language = code_lines[0].strip()
                    code = "\n".join(code_lines[1:]) if len(code_lines) > 1 else ""
                else:
                    code = part

                button_id = f"copy_{id(self)}_{i}"
                formatted_response += f"""
                    <table style='width: 100%; margin: 8px 0;'>
                        <tr>
                            <td style='
                                background-color: #2A2B2E;
                                color: #D4D4D4;
                                font-family: Consolas, monospace;
                                padding: 12px;
                                border: 1px solid #353535;
                                border-radius: 6px;
                                white-space: pre-wrap;
                                word-wrap: break-word;'>{code}</td>
                            <td style='width: 90px; vertical-align: top; padding-left: 6px;'>
                                <input type='button' value='Copy Code' id='{button_id}' 
                                    style='
                                        background-color: #353535;
                                        color: #ECDC51;
                                        border: 1px solid #FFC61A;
                                        padding: 6px 12px;
                                        border-radius: 6px;
                                        font-family: Consolas;
                                        font-weight: 600;
                                        cursor: pointer;
                                        transition: all 0.2s;'
                                    onmouseover='this.style.backgroundColor="#FFC61A"; this.style.color="#1E1F22";'
                                    onmouseout='this.style.backgroundColor="#353535"; this.style.color="#ECDC51";'>
                            </td>
                        </tr>
                    </table>
                """
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
                self.chat_display.document().find(f"id='{button_id}'").charFormat().setProperty(
                    QTextFormat.UserProperty, lambda: self._copy_to_clipboard(code))
                break

    def _copy_to_clipboard(self, code: str):
        """Copy the code to the clipboard"""
        self.clipboard.setText(code.strip())
        self.chat_display.append(
            "<span style='color: #FFC61A; font-style: italic;'>Copied to clipboard!</span>"
        )
        QTimer.singleShot(2000, lambda: self.chat_display.undo())

if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    window = BoltAI()
    window.show()
    sys.exit(app.exec_())