import sys
import io
import keyword
import re
import subprocess
import traceback
from typing import List, Tuple, Dict, Set, Optional
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QRegExp, QSize, QTimer, QRect
from PyQt5.QtGui import (
    QColor, QTextCharFormat, QFont, QPalette, QSyntaxHighlighter,
    QTextCursor, QIcon, QPainter, QTextFormat
)
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QSplitter, QTextEdit, QPlainTextEdit, QFileDialog, QDialog,
    QLineEdit, QListWidget, QListWidgetItem, QPushButton, QLabel,
    QMessageBox, QInputDialog, QAction, QToolBar, QToolButton, QMenu
)

class Config:
    """Centralized configuration constants"""
    EDITOR_FONT = "Consolas"
    FONT_SIZE = 10
    BACKGROUND_COLOR = "#1E1E1E"
    TEXT_COLOR = "#D4D4D4"
    LINE_NUMBER_BG = "#262626"
    LINE_NUMBER_FG = "#8A8A8A"
    AUTO_SAVE_INTERVAL = 30000  # milliseconds

class HighlightRules:
    """Lazy-loaded syntax highlighting rules"""
    @staticmethod
    def get_comment_rule() -> Tuple[QRegExp, QTextCharFormat]:
        format_ = QTextCharFormat()
        format_.setForeground(QColor("#6A9955"))
        return QRegExp(r'#[^\n]*'), format_

    @staticmethod
    def get_keyword_rule(word: str) -> Tuple[QRegExp, QTextCharFormat]:
        format_ = QTextCharFormat()
        format_.setForeground(QColor("#569CD6"))
        format_.setFontWeight(QFont.Bold)
        return QRegExp(rf'\b{word}\b'), format_

    @staticmethod
    def get_function_rule() -> Tuple[QRegExp, QTextCharFormat]:
        format_ = QTextCharFormat()
        format_.setForeground(QColor("#DCDCAA"))
        return QRegExp(r'\b[A-Za-z0-9_]+(?=\()'), format_

    @staticmethod
    def get_string_rules() -> List[Tuple[QRegExp, QTextCharFormat]]:
        format_ = QTextCharFormat()
        format_.setForeground(QColor("#CE9178"))
        return [
            (QRegExp(r"'[^'\\]*(\\.[^'\\]*)*'"), format_),
            (QRegExp(r'"[^"\\]*(\\.[^"\\]*)*"'), format_)
        ]

class PythonHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for Python code"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.comment_rule = HighlightRules.get_comment_rule()
        self.rules: List[Tuple[QRegExp, QTextCharFormat]] = (
            [HighlightRules.get_function_rule()] +
            HighlightRules.get_string_rules() +
            [HighlightRules.get_keyword_rule(word) for word in keyword.kwlist]
        )

    def highlightBlock(self, text: str) -> None:
        index = self.comment_rule[0].indexIn(text)
        if index >= 0:
            self.setFormat(index, len(text) - index, self.comment_rule[1])
            return
        for pattern, format_ in self.rules:
            index = pattern.indexIn(text)
            while index >= 0:
                length = pattern.matchedLength()
                self.setFormat(index, length, format_)
                index = pattern.indexIn(text, index + length)

class LineNumberArea(QWidget):
    """Widget for displaying line numbers and fold indicators"""
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
        self.setMouseTracking(True)
        self.hovered_line = -1

    def sizeHint(self) -> QSize:
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(event.rect(), QColor(Config.LINE_NUMBER_BG))
        painter.setPen(QColor(Config.LINE_NUMBER_FG))

        block = self.editor.firstVisibleBlock()
        top = self.editor.blockBoundingGeometry(block).translated(self.editor.contentOffset()).top()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible():
                block_num = block.blockNumber()
                self._draw_line_info(painter, block_num, top)
            block = block.next()
            top += self.editor.blockBoundingRect(block).height()

    def _draw_line_info(self, painter: QPainter, block_num: int, top: float) -> None:
        if block_num in self.editor.foldable_lines:
            fold_type = self.editor.fold_types.get(block_num, "other")
            base_color = {"def": "#52585C", "class": "#61686D"}.get(fold_type, "#71797E")
            if block_num == self.hovered_line:
                highlight_color = QColor(
                    min(QColor(base_color).red() + 40, 255),
                    min(QColor(base_color).green() + 40, 255),
                    min(QColor(base_color).blue() + 40, 255)
                )
                painter.setPen(highlight_color)
            else:
                painter.setPen(QColor(base_color))
            arrow = "▼" if block_num not in self.editor.folded_blocks else "▶"
            painter.drawText(
                QRect(0, int(top), self.width() - 5, self.editor.fontMetrics().height()),
                Qt.AlignRight, arrow
            )
        painter.setPen(QColor(Config.LINE_NUMBER_FG))
        painter.drawText(
            QRect(5, int(top), self.width() - 20, self.editor.fontMetrics().height()),
            Qt.AlignRight, str(block_num + 1)
        )

    def mouseMoveEvent(self, event) -> None:
        block = self.editor.firstVisibleBlock()
        y_pos = event.y()
        line = -1
        while block.isValid():
            block_top = self.editor.blockBoundingGeometry(block).translated(self.editor.contentOffset()).top()
            if y_pos < block_top + self.editor.blockBoundingRect(block).height() and block.isVisible():
                line = block.blockNumber()
                break
            block = block.next()
        if line != self.hovered_line:
            self.hovered_line = line
            self.update()
        self.setCursor(Qt.PointingHandCursor if line in self.editor.foldable_lines else Qt.ArrowCursor)

    def leaveEvent(self, event) -> None:
        self.hovered_line = -1
        self.setCursor(Qt.ArrowCursor)
        self.update()

    def mousePressEvent(self, event) -> None:
        block = self.editor.firstVisibleBlock()
        y_pos = event.y()
        line = -1
        while block.isValid():
            block_top = self.editor.blockBoundingGeometry(block).translated(self.editor.contentOffset()).top()
            if y_pos < block_top + self.editor.blockBoundingRect(block).height() and block.isVisible():
                line = block.blockNumber()
                break
            block = block.next()
        if line in self.editor.foldable_lines:
            self.editor.toggle_fold(line)

class CodeEditor(QPlainTextEdit):
    """Custom code editor with folding and syntax highlighting"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.line_number_area = LineNumberArea(self)
        self.highlighter = PythonHighlighter(self.document())
        self.foldable_lines: Set[int] = set()
        self.folded_blocks: Set[int] = set()
        self.fold_ranges: Dict[int, int] = {}
        self.fold_types: Dict[int, str] = {}
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        font = QFont(Config.EDITOR_FONT, Config.FONT_SIZE)
        font.setFixedPitch(True)
        self.setFont(font)
        palette = QPalette()
        palette.setColor(QPalette.Base, QColor(Config.BACKGROUND_COLOR))
        palette.setColor(QPalette.Text, QColor(Config.TEXT_COLOR))
        self.setPalette(palette)
        self.setTabStopWidth(4 * self.fontMetrics().width(' '))

    def _connect_signals(self) -> None:
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)
        self.textChanged.connect(self.detect_foldable_lines)

    def line_number_area_width(self) -> int:
        digits = len(str(self.blockCount()))
        return 40 + self.fontMetrics().width('9') * digits

    def update_line_number_area_width(self) -> None:
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect: QRect, dy: int) -> None:
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        rect = self.contentsRect()
        self.line_number_area.setGeometry(rect.left(), rect.top(), self.line_number_area_width(), rect.height())

    def highlight_current_line(self) -> None:
        if self.isReadOnly():
            return
        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(QColor("#2A2D2E"))
        selection.format.setProperty(QTextFormat.FullWidthSelection, True)
        selection.cursor = self.textCursor()
        selection.cursor.clearSelection()
        self.setExtraSelections([selection])

    def detect_foldable_lines(self) -> None:
        self.foldable_lines.clear()
        self.fold_ranges.clear()
        self.fold_types.clear()
        indent_stack: List[Tuple[int, int, str]] = []

        block = self.document().firstBlock()
        while block.isValid():
            text = block.text().strip()
            if text:
                current_indent = len(block.text()) - len(block.text().lstrip())
                current_line = block.blockNumber()

                while indent_stack and indent_stack[-1][1] >= current_indent:
                    start_line, _, block_type = indent_stack.pop()
                    if current_line - start_line > 1:
                        self._add_foldable(start_line, current_line - 1, block_type)

                if text.startswith(("def ", "class ", "if ", "for ", "while ", "try:", "with ")):
                    block_type = "def" if text.startswith("def ") else "class" if text.startswith("class ") else "other"
                    indent_stack.append((current_line, current_indent, block_type))

            block = block.next()

        end_line = self.document().blockCount() - 1
        for start_line, _, block_type in indent_stack:
            if end_line - start_line > 1:
                self._add_foldable(start_line, end_line, block_type)

    def _add_foldable(self, start: int, end: int, block_type: str) -> None:
        self.foldable_lines.add(start)
        self.fold_ranges[start] = end
        self.fold_types[start] = block_type

    def toggle_fold(self, line_number: int) -> None:
        if line_number not in self.fold_ranges:
            return

        is_folding = line_number not in self.folded_blocks
        if is_folding:
            self.folded_blocks.add(line_number)
        else:
            self.folded_blocks.discard(line_number)

        document = self.document()
        with self._disable_updates():
            block = document.findBlockByNumber(line_number + 1)
            end_line = self.fold_ranges[line_number]
            while block.isValid() and block.blockNumber() <= end_line:
                block.setVisible(not is_folding)
                block = block.next()
            document.markContentsDirty(
                document.findBlockByNumber(line_number).position(),
                document.findBlockByNumber(end_line).position()
            )

    def _disable_updates(self):
        class DisableUpdates:
            def __init__(self, editor):
                self.editor = editor
            def __enter__(self):
                self.editor.setUpdatesEnabled(False)
                self.editor.document().blockSignals(True)
                return self
            def __exit__(self, *args):
                self.editor.document().blockSignals(False)
                self.editor.setUpdatesEnabled(True)
                self.editor.viewport().update()
        return DisableUpdates(self)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.StartOfLine, QTextCursor.KeepAnchor)
            line = cursor.selectedText()
            indent = " " * (len(line) - len(line.lstrip()))
            if line.strip().endswith(":"):
                indent += "    "
            super().keyPressEvent(event)
            self.insertPlainText(indent)
            return
        super().keyPressEvent(event)

    def format_code(self) -> None:
        try:
            import black
            formatted = black.format_str(self.toPlainText(), mode=black.FileMode())
            self.setPlainText(formatted)
            self.document().setModified(False)
        except ImportError:
            QMessageBox.warning(self, "Formatting Error", "Please install black: pip install black")
        except Exception as e:
            QMessageBox.warning(self, "Formatting Error", f"Failed to format: {str(e)}")

class ConsoleWidget(QTextEdit):
    """Integrated console widget"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self.input_buffer = ""
        self.reading_input = False
        self.input_pos = 0

    def _setup_ui(self) -> None:
        font = QFont(Config.EDITOR_FONT, Config.FONT_SIZE)
        font.setFixedPitch(True)
        self.setFont(font)
        palette = QPalette()
        palette.setColor(QPalette.Base, QColor(Config.BACKGROUND_COLOR))
        palette.setColor(QPalette.Text, QColor("#CCCCCC"))
        self.setPalette(palette)
        self.setReadOnly(True)

    def write(self, text: str) -> None:
        self.moveCursor(QTextCursor.End)
        self.insertPlainText(text)
        QApplication.processEvents()

    def start_input(self) -> None:
        self.reading_input = True
        self.setReadOnly(False)
        self.moveCursor(QTextCursor.End)
        self.input_pos = self.textCursor().position()

    def readline(self) -> str:
        self.start_input()
        while self.reading_input:
            QApplication.processEvents()
        return self.input_buffer + '\n'

    def keyPressEvent(self, event) -> None:
        if not self.reading_input:
            if event.key() == Qt.Key_C and event.modifiers() & Qt.ControlModifier:
                QApplication.clipboard().setText(self.textCursor().selectedText())
            return

        cursor = self.textCursor()
        if event.key() == Qt.Key_Backspace and cursor.position() <= self.input_pos:
            return
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            cursor.setPosition(self.input_pos, QTextCursor.MoveAnchor)
            cursor.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
            self.input_buffer = cursor.selectedText()
            self.insertPlainText('\n')
            self.reading_input = False
            self.setReadOnly(True)
            return
        if event.key() == Qt.Key_Left and cursor.position() <= self.input_pos:
            return
        if event.key() == Qt.Key_Home:
            cursor.setPosition(self.input_pos)
            self.setTextCursor(cursor)
            return
        super().keyPressEvent(event)

class PythonInterpreter(QThread):
    """Thread for executing Python code"""
    output_ready = pyqtSignal(str)
    error_detected = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, code: str, console: ConsoleWidget):
        super().__init__()
        self.code = code
        self.console = console

    def run(self) -> None:
        stdout, stderr, stdin = sys.stdout, sys.stderr, sys.stdin
        captured_output = io.StringIO()
        try:
            sys.stdout = self.console
            sys.stderr = captured_output
            sys.stdin = self.console
            exec(compile(self.code, '<ide>', 'exec'), {'__name__': '__main__'})
        except ModuleNotFoundError as e:
            module = str(e).split("'")[1] if "'" in str(e) else None
            if module:
                self.error_detected.emit(module)
            self.console.write(f"{str(e)}\n")
            traceback.print_exc(file=self.console)
        except Exception as e:
            traceback.print_exc(file=self.console)
        finally:
            if error_output := captured_output.getvalue():
                self.console.write(error_output)
            sys.stdout, sys.stderr, sys.stdin = stdout, stderr, stdin
            self.finished.emit()

class PackageInstaller(QThread):
    """Thread for installing packages"""
    output_ready = pyqtSignal(str)
    finished = pyqtSignal(bool)

    def __init__(self, package_name: str, console: ConsoleWidget):
        super().__init__()
        self.package_name = package_name
        self.console = console
        self.success = False

    def run(self) -> None:
        try:
            self.output_ready.emit(f"Installing {self.package_name}...\n")
            process = subprocess.Popen(
                [sys.executable, "-m", "pip", "install", self.package_name],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            stdout, stderr = process.communicate()
            self.success = process.returncode == 0
            self.output_ready.emit(
                f"{'Successfully installed' if self.success else 'Failed to install'} "
                f"{self.package_name}:\n{stdout if self.success else stderr}\n"
            )
        except Exception as e:
            self.output_ready.emit(f"Error: {str(e)}\n")
        finally:
            self.finished.emit(self.success)

class PythonIDE(QMainWindow):
    """Main IDE window"""
    def __init__(self):
        super().__init__()
        self.current_file: Optional[str] = None
        self.code_is_running = False
        self.child_windows: List['PythonIDE'] = []
        self._init_ui()

    def _init_ui(self) -> None:
        self.setWindowTitle("JaxPY")
        self.setWindowIcon(QIcon("JaxPY.ico"))
        self.setGeometry(100, 100, 1000, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        splitter = QSplitter(Qt.Vertical)
        self.code_editor = CodeEditor()
        self.code_editor.textChanged.connect(self._mark_unsaved)
        splitter.addWidget(self.code_editor)

        console_container = QWidget()
        console_layout = QVBoxLayout(console_container)
        console_layout.setContentsMargins(0, 0, 0, 0)

        header = QHBoxLayout()
        terminal_label = QLabel("Terminal")
        terminal_label.setStyleSheet("color: #CCCCCC; background-color: #2D2D2D; padding: 3px; font-weight: bold;")
        header.addWidget(terminal_label)
        header.addStretch()
        self.save_status_dot = QLabel("●")
        self.save_status_dot.setStyleSheet("color: red; background-color: #2D2D2D; padding: 3px")
        header.addWidget(self.save_status_dot)
        console_layout.addLayout(header)

        self.console = ConsoleWidget()
        console_layout.addWidget(self.console)
        splitter.addWidget(console_container)
        splitter.setSizes([600, 200])
        main_layout.addWidget(splitter)

        self._setup_toolbar()
        self._setup_auto_save()
        self.code_editor.setPlainText(
            '# Welcome to Python IDE\n\nprint("Hello, World!")\n'
            'name = input("Enter your name: ")\nprint(f"Hello, {name}!")'
        )
        self.setStyleSheet("""
            QMainWindow, QWidget {background-color: #1E1E1E; color: #CCCCCC;}
            QToolBar {background-color: #2D2D2D; border: none;}
            QSplitter::handle {background-color: #2D2D2D;}
            QPushButton {background-color: #0E639C; color: white; padding: 5px 10px;}
            QPushButton:hover {background-color: #1177BB;}
        """)

    def _setup_toolbar(self) -> None:
        toolbar = QToolBar()
        self.addToolBar(toolbar)
        button_style = "background-color: #1e1e1e; color: white; padding: 5px 10px; border-radius: 5px;"

        self.run_button = QToolButton()
        self.run_button.setText("RUN")
        self.run_button.setShortcut("F5")
        self.run_button.clicked.connect(self.run_code)
        self.run_button.setStyleSheet("background-color: green; color: white; padding: 5px 10px; border-radius: 5px;")
        toolbar.addWidget(self.run_button)

        for name, shortcut, callback in [
            ("File", None, lambda: None),
            ("Open", None, self.open_file),
            ("Save", None, self.save_file),
            ("Find / Replace", "Ctrl+F", self.find_and_replace),
            ("Packages", None, lambda: None),
            ("Format", "Ctrl+Shift+F", self.format_code)
        ]:
            if name in ("File", "Packages"):
                btn = QToolButton()
                btn.setText(name)
                btn.setPopupMode(QToolButton.InstantPopup)
                btn.setStyleSheet(button_style)
                menu = QMenu(self)
                btn.setMenu(menu)
                if name == "File":
                    menu.addAction("New", self.new_file)
                    menu.addAction("New Window", self.new_window)
                else:
                    menu.addAction("Install Packages", self.show_package_installer)
                    menu.addAction("Installed Packages", self.show_installed_packages)
                toolbar.addWidget(btn)
            else:
                action = QAction(name, self)
                if shortcut:
                    action.setShortcut(shortcut)
                action.triggered.connect(callback)
                toolbar.addAction(action)

    def _setup_auto_save(self) -> None:
        self.auto_save_timer = QTimer(self)
        self.auto_save_timer.timeout.connect(self.auto_save)
        self.auto_save_timer.start(Config.AUTO_SAVE_INTERVAL)

    def run_code(self) -> None:
        if self.code_is_running:
            self.console.write("\n[Stopping previous execution...]\n")
            self.interpreter.terminate()
            self.interpreter.wait()
            self.code_is_running = False
            self.run_code()
            return

        self.code_is_running = True
        self.run_button.setStyleSheet("background-color: red; color: white; padding: 5px 10px; border-radius: 5px;")
        self.console.clear()
        self.interpreter = PythonInterpreter(self.code_editor.toPlainText(), self.console)
        self.interpreter.finished.connect(self._on_execution_finished)
        self.interpreter.error_detected.connect(self._handle_module_error)
        self.interpreter.start()

    def _on_execution_finished(self) -> None:
        self.console.write("\n>>> ")
        self.run_button.setStyleSheet("background-color: green; color: white; padding: 5px 10px; border-radius: 5px;")
        self.code_is_running = False

    def new_file(self) -> None:
        self.code_editor.clear()
        self.console.clear()
        self.current_file = None
        self._mark_unsaved()

    def open_file(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, "Open Python File", "", "Python Files (*.py);;All Files (*)")
        if filename:
            try:
                with open(filename, 'r', encoding="utf-8") as f:
                    self.code_editor.setPlainText(f.read())
                self.current_file = filename
                self._mark_saved()
            except Exception as e:
                self.console.write(f"Error opening file: {str(e)}\n")

    def save_file(self) -> None:
        if not self.current_file:
            self.current_file, _ = QFileDialog.getSaveFileName(self, "Save Python File", "", "Python Files (*.py)")
        if self.current_file:
            self._save_to_file(self.current_file)

    def _save_to_file(self, path: str, silent: bool = False) -> None:
        try:
            with open(path, 'w', encoding="utf-8") as f:
                f.write(self.code_editor.toPlainText())
            if not silent:
                self.console.write(f"\n[Saved] {path}\n")
            self._mark_saved()
        except Exception as e:
            self.console.write(f"\n[Save Failed] {str(e)}\n")

    def auto_save(self) -> None:
        self._save_to_file(self.current_file or "autosave.py", silent=True)

    def _mark_unsaved(self) -> None:
        self.save_status_dot.setStyleSheet("color: red; background-color: #2D2D2D; padding: 3px")

    def _mark_saved(self) -> None:
        self.save_status_dot.setStyleSheet("color: green; background-color: #2D2D2D; padding: 3px")

    def new_window(self) -> None:
        try:
            new_ide = PythonIDE()
            self.child_windows.append(new_ide)
            new_ide.show()
        except Exception as e:
            print(f"Failed to open new window: {e}")

    def find_and_replace(self) -> None:
        self.find_replace_dialog = QDialog(self)
        self.find_replace_dialog.setWindowTitle("Find and Replace")
        self.find_replace_dialog.setGeometry(300, 300, 350, 150)
        layout = QVBoxLayout(self.find_replace_dialog)

        self.find_input = QLineEdit()
        self.replace_input = QLineEdit()
        self.match_label = QLabel("Matches: 0")
        self.match_positions: List[int] = []
        self.current_match_index = -1

        layout.addWidget(QLabel("Find:"))
        layout.addWidget(self.find_input)
        layout.addWidget(QLabel("Replace:"))
        layout.addWidget(self.replace_input)

        match_layout = QHBoxLayout()
        match_layout.addWidget(self.match_label)
        for text, callback in [("◀", self.prev_match), ("▶", self.next_match)]:
            btn = QPushButton(text)
            btn.setFixedSize(30, 30)
            btn.clicked.connect(callback)
            match_layout.addWidget(btn)
        layout.addLayout(match_layout)

        for text, callback in [
            ("Find", self.find_text),
            ("Replace", self.replace_text),
            ("Replace All", self.replace_all_text)
        ]:
            layout.addWidget(QPushButton(text, clicked=callback))

        self.find_replace_dialog.exec_()

    def find_text(self) -> None:
        search_text = self.find_input.text().strip()
        if not search_text:
            return

        document = self.code_editor.document()
        cursor = QTextCursor(document)
        self.match_positions.clear()
        regex = QRegExp(rf'\b{re.escape(search_text)}\b')

        while not cursor.isNull() and not cursor.atEnd():
            cursor = document.find(regex, cursor)
            if cursor.isNull():
                break
            self.match_positions.append(cursor.position())

        match_count = len(self.match_positions)
        self.match_label.setText(f"Matches: {match_count}")
        if match_count > 0:
            self.current_match_index = 0
            self._highlight_match()
        elif self.find_replace_dialog.isVisible():
            self.find_replace_dialog.accept()

    def _highlight_match(self) -> None:
        if self.current_match_index >= 0 and self.match_positions:
            cursor = self.code_editor.textCursor()
            search_len = len(self.find_input.text())
            cursor.setPosition(self.match_positions[self.current_match_index] - search_len)
            cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, search_len)
            self.code_editor.setTextCursor(cursor)
            self.match_label.setText(f"Matches: {len(self.match_positions)} (Current: {self.current_match_index + 1})")

    def next_match(self) -> None:
        if self.match_positions:
            self.current_match_index = (self.current_match_index + 1) % len(self.match_positions)
            self._highlight_match()

    def prev_match(self) -> None:
        if self.match_positions:
            self.current_match_index = (self.current_match_index - 1) % len(self.match_positions)
            self._highlight_match()

    def replace_text(self) -> None:
        if self.current_match_index >= 0 and self.match_positions:
            cursor = self.code_editor.textCursor()
            search_text = self.find_input.text()
            if cursor.hasSelection() and cursor.selectedText() == search_text:
                replace_text = self.replace_input.text()
                cursor.insertText(replace_text)
                self.match_positions[self.current_match_index] += len(replace_text) - len(search_text)
            self.find_text()

    def replace_all_text(self) -> None:
        search_text = self.find_input.text().strip()
        replace_text = self.replace_input.text()
        if not search_text:
            return

        document = self.code_editor.document()
        cursor = QTextCursor(document)
        cursor.beginEditBlock()
        regex = QRegExp(rf'\b{re.escape(search_text)}\b')
        cursor.movePosition(QTextCursor.Start)

        while True:
            cursor = document.find(regex, cursor)
            if cursor.isNull():
                break
            cursor.insertText(replace_text)
        cursor.endEditBlock()
        if self.find_replace_dialog.isVisible():
            self.find_replace_dialog.accept()

    def _handle_module_error(self, module_name: str) -> None:
        if QMessageBox.question(
            self, "Missing Package",
            f"Module '{module_name}' not found. Install it?",
            QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes:
            self.install_package(module_name)

    def show_package_installer(self) -> None:
        package_name, ok = QInputDialog.getText(self, "Install Package", "Enter package name:")
        if ok and package_name:
            self.install_package(package_name)

    def show_installed_packages(self) -> None:
        try:
            result = subprocess.run([sys.executable, "-m", "pip", "list"], capture_output=True, text=True)
            packages = result.stdout.split("\n")[2:]

            dialog = QDialog(self)
            dialog.setWindowTitle("Installed Packages")
            dialog.setGeometry(200, 200, 400, 400)
            dialog.setStyleSheet("background-color: #1E1E1E; color: #CCCCCC;")
            layout = QVBoxLayout(dialog)

            search_bar = QLineEdit()
            search_bar.setPlaceholderText("Search packages...")
            search_bar.setStyleSheet("background-color: #2D2D2D; color: white; padding: 5px;")
            layout.addWidget(search_bar)

            package_list = QListWidget()
            package_list.setStyleSheet("background-color: #262626; color: white;")
            for pkg in packages:
                if pkg.strip():
                    QListWidgetItem(pkg.strip(), package_list)
            layout.addWidget(package_list)

            search_bar.textChanged.connect(
                lambda text: [package_list.item(i).setHidden(text.lower() not in package_list.item(i).text().lower())
                            for i in range(package_list.count())]
            )

            close_btn = QPushButton("Close", clicked=dialog.accept)
            close_btn.setStyleSheet("background-color: #0E639C; color: white; padding: 5px;")
            layout.addWidget(close_btn)
            dialog.exec_()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to list packages: {str(e)}")

    def install_package(self, package_name: str) -> None:
        self.console.write(f"\nInstalling {package_name}...\n")
        self.installer = PackageInstaller(package_name, self.console)
        self.installer.output_ready.connect(self.console.write)
        self.installer.finished.connect(lambda success: self._on_installation_finished(success, package_name))
        self.installer.start()

    def _on_installation_finished(self, success: bool, package_name: str) -> None:
        msg = f"Package '{package_name}' {'installed successfully' if success else 'installation failed'}"
        (QMessageBox.information if success else QMessageBox.warning)(self, "Installation", msg)
        self.console.write("\n>>> ")

    def format_code(self) -> None:
        self.code_editor.format_code()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    ide = PythonIDE()
    ide.show()
    sys.exit(app.exec_())