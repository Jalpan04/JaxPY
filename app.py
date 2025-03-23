import sys
import io
import os
import keyword
import re
import subprocess
import traceback
import builtins
from typing import List, Tuple, Dict, Set, Optional

from PyQt5 import QtCore
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QRegExp, QSize, QTimer, QRect, QSettings
from PyQt5.QtGui import (
    QColor, QTextCharFormat, QFont, QPalette, QSyntaxHighlighter,
    QTextCursor, QIcon, QPainter, QTextFormat
)
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QSplitter, QTextEdit, QPlainTextEdit, QFileDialog, QDialog,
    QLineEdit, QPushButton, QLabel, QMessageBox, QInputDialog,
    QAction, QToolBar, QToolButton, QMenu, QCompleter, QListWidget, QListWidgetItem
)

from bolt_ai import BoltAI  # Import the BoltAI class from bolt_ai.py

class Config:
    """Centralized configuration constants"""
    EDITOR_FONT = "Consolas"
    FONT_SIZE = 10
    BACKGROUND_COLOR = "#1E1E1E"
    TEXT_COLOR = "#D4D4D4"
    LINE_NUMBER_BG = "#262626"
    LINE_NUMBER_FG = "#8A8A8A"
    ERROR_COLOR = "#FF5555"
    WARNING_COLOR = "#FFC107"
    AUTO_SAVE_INTERVAL = 30000  # milliseconds
    PYTHON_BUILTINS = dir(builtins)
    COMMON_IMPORTS = [
        "os", "sys", "math", "random", "datetime", "time", "json",
        "re", "subprocess", "threading", "multiprocessing", "socket",
        "requests", "numpy", "pandas", "matplotlib", "tkinter"
    ]
    AUTOCOMPLETE_TRIGGERS = [".", "im"]
    DEFAULT_PROJECT_DIR = os.getcwd()


class HighlightRules:
    """Static syntax highlighting rules"""
    _formats: Dict[str, QTextCharFormat] = {}

    @classmethod
    def _create_format(cls, color: str, bold: bool = False) -> QTextCharFormat:
        key = f"{color}_{bold}"
        if key not in cls._formats:
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            if bold:
                fmt.setFontWeight(QFont.Bold)
            cls._formats[key] = fmt
        return cls._formats[key]

    @classmethod
    def get_rules(cls) -> List[Tuple[QRegExp, QTextCharFormat]]:
        return [
            (QRegExp(r'#[^\n]*'), cls._create_format("#6A9955")),  # Comments
            (QRegExp(r'\b[A-Za-z0-9_]+(?=\()'), cls._create_format("#DCDCAA")),  # Functions
            (QRegExp(r"'[^'\\]*(\\.[^'\\]*)*'"), cls._create_format("#CE9178")),  # Single quotes
            (QRegExp(r'"[^"\\]*(\\.[^"\\]*)*"'), cls._create_format("#CE9178")),  # Double quotes
        ] + [(QRegExp(rf'\b{word}\b'), cls._create_format("#569CD6", True)) for word in keyword.kwlist]


class PythonHighlighter(QSyntaxHighlighter):
    """Efficient Python syntax highlighter"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rules = HighlightRules.get_rules()
        self.errors: Dict[int, str] = {}
        self.warnings: Dict[int, str] = {}
        self._last_text = ""

    def update_full_code(self, full_text: str) -> None:
        if full_text != self._last_text:
            self._last_text = full_text
            self._check_full_syntax()
            self.rehighlight()

    def _check_full_syntax(self) -> None:
        self.errors.clear()
        if not self._last_text.strip():
            return
        try:
            compile(self._last_text, '<document>', 'exec')
        except SyntaxError as e:
            if hasattr(e, 'lineno') and e.lineno is not None:
                self.errors[e.lineno - 1] = str(e)

    def _check_warnings(self, text: str, line_number: int) -> None:
        self.warnings.pop(line_number, None)
        stripped = text.strip()
        if not stripped or stripped.startswith('#'):
            return
        if re.search(r'\bprint\s+[^("]', text) and not re.search(r'["\'].*print\s+[^("].*["\']', text):
            self.warnings[line_number] = "Old-style print statement (use print())"
        elif re.search(r'^\s*from\s+\w+\s+import\s+\*', text):
            self.warnings[line_number] = "Wildcard import detected (avoid 'from ... import *')"

    def highlightBlock(self, text: str) -> None:
        line_number = self.currentBlock().blockNumber()
        for pattern, fmt in self.rules:
            index = pattern.indexIn(text)
            while index >= 0:
                length = pattern.matchedLength()
                self.setFormat(index, length, fmt)
                index = pattern.indexIn(text, index + length)

        self._check_warnings(text, line_number)
        if line_number in self.errors:
            fmt = HighlightRules._create_format(Config.ERROR_COLOR)
            fmt.setUnderlineStyle(QTextCharFormat.WaveUnderline)
            self.setFormat(0, len(text), fmt)
        elif line_number in self.warnings:
            fmt = HighlightRules._create_format(Config.WARNING_COLOR)
            fmt.setUnderlineStyle(QTextCharFormat.DashWaveUnderline)
            self.setFormat(0, len(text), fmt)


class LineNumberArea(QWidget):
    """Optimized line number area"""

    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
        self.hovered_line = -1
        self.setMouseTracking(True)

    def sizeHint(self) -> QSize:
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(event.rect(), QColor(Config.LINE_NUMBER_BG))
        block = self.editor.firstVisibleBlock()
        top = int(self.editor.blockBoundingGeometry(block).translated(self.editor.contentOffset()).top())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible():
                block_num = block.blockNumber()
                painter.setPen(QColor(Config.LINE_NUMBER_FG))
                painter.drawText(
                    QRect(5, top, self.width() - 20, self.editor.fontMetrics().height()),
                    Qt.AlignRight, str(block_num + 1)
                )
                if block_num in self.editor.foldable_lines:
                    fold_type = self.editor.fold_types.get(block_num, "other")
                    base_color = {"def": "#52585C", "class": "#61686D"}.get(fold_type, "#71797E")
                    painter.setPen(
                        QColor(base_color if block_num != self.hovered_line else QColor(base_color).lighter(140)))
                    arrow = "▼" if block_num not in self.editor.folded_blocks else "▶"
                    painter.drawText(
                        QRect(0, top, self.width() - 5, self.editor.fontMetrics().height()),
                        Qt.AlignRight, arrow
                    )
            block = block.next()
            top += int(self.editor.blockBoundingRect(block).height())

    def mouseMoveEvent(self, event) -> None:
        block = self.editor.cursorForPosition(event.pos()).block()
        self.hovered_line = block.blockNumber() if block.isValid() and block.isVisible() else -1
        self.setCursor(Qt.PointingHandCursor if self.hovered_line in self.editor.foldable_lines else Qt.ArrowCursor)
        self.update()

    def leaveEvent(self, event) -> None:
        self.hovered_line = -1
        self.setCursor(Qt.ArrowCursor)
        self.update()

    def mousePressEvent(self, event) -> None:
        block = self.editor.cursorForPosition(event.pos()).block()
        if block.isValid() and block.blockNumber() in self.editor.foldable_lines:
            self.editor.toggle_fold(block.blockNumber())


class CodeEditor(QPlainTextEdit):
    """Optimized code editor with folding and autocomplete"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.line_number_area = LineNumberArea(self)
        self.highlighter = PythonHighlighter(self.document())
        self.foldable_lines: Set[int] = set()
        self.folded_blocks: Set[int] = set()
        self.fold_ranges: Dict[int, int] = {}
        self.fold_types: Dict[int, str] = {}
        self._setup_ui()
        self._setup_autocomplete()
        self.error_warning_label = QLabel(self)
        self.error_warning_label.setStyleSheet(
            f"color: {Config.TEXT_COLOR}; background-color: {Config.BACKGROUND_COLOR}; padding: 3px;"
        )
        self._autocomplete_active = False

    def _setup_ui(self) -> None:
        font = QFont(Config.EDITOR_FONT, Config.FONT_SIZE)
        font.setFixedPitch(True)
        self.setFont(font)
        palette = QPalette()
        palette.setColor(QPalette.Base, QColor(Config.BACKGROUND_COLOR))
        palette.setColor(QPalette.Text, QColor(Config.TEXT_COLOR))
        self.setPalette(palette)
        self.setTabStopWidth(self.fontMetrics().width(' ') * 4)
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)
        self.textChanged.connect(self._on_text_changed)
        self.setAcceptDrops(True)

    def _on_text_changed(self) -> None:
        self.highlighter.update_full_code(self.toPlainText())
        self.detect_foldable_lines()
        self.update_error_warning_count()

    def line_number_area_width(self) -> int:
        return 40 + self.fontMetrics().width('9') * max(1, len(str(self.blockCount())))

    def update_line_number_area_width(self) -> None:
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect: QRect, dy: int) -> None:
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.line_number_area.setGeometry(0, 0, self.line_number_area_width(), self.contentsRect().height())

    def highlight_current_line(self) -> None:
        if not self.isReadOnly():
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
            text = block.text().rstrip()
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
        self.folded_blocks.add(line_number) if is_folding else self.folded_blocks.discard(line_number)
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
            def __init__(self, editor): self.editor = editor

            def __enter__(self):
                self.editor.setUpdatesEnabled(False)
                self.editor.document().blockSignals(True)
                return self

            def __exit__(self, *args):
                self.editor.document().blockSignals(False)
                self.editor.setUpdatesEnabled(True)
                self.editor.viewport().update()

        return DisableUpdates(self)

    def _setup_autocomplete(self) -> None:
        self.completer = QCompleter(Config.PYTHON_BUILTINS + Config.COMMON_IMPORTS + keyword.kwlist, self)
        self.completer.setCompletionMode(QCompleter.PopupCompletion)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.activated.connect(self.insert_completion)
        self.completer.popup().setStyleSheet("""
            QListView { background-color: #2D2D2D; color: #D4D4D4; border: 1px solid #555555; }
            QListView::item:hover { background-color: #3A3A3A; }
        """)

    def insert_completion(self, completion: str) -> None:
        cursor = self.textCursor()
        extra = len(completion) - len(self.completer.completionPrefix())
        cursor.movePosition(QTextCursor.Left)
        cursor.movePosition(QTextCursor.EndOfWord)
        cursor.insertText(completion[-extra:] if extra > 0 else completion)
        self.setTextCursor(cursor)

    def show_autocomplete(self) -> None:
        if self._autocomplete_active:
            return
        self._autocomplete_active = True
        try:
            cursor = self.textCursor()
            cursor.select(QTextCursor.WordUnderCursor)
            prefix = cursor.selectedText()
            line_start = self.toPlainText().rfind('\n', 0, cursor.position()) + 1
            current_line = self.toPlainText()[line_start:cursor.position()]
            is_import = current_line.strip().startswith(('import ', 'from '))
            prefix = current_line.split()[-1] if is_import and current_line.split() else prefix

            if prefix and (any(prefix.startswith(t) for t in Config.AUTOCOMPLETE_TRIGGERS) or len(prefix) > 1):
                self.completer.setCompletionPrefix(prefix[1:] if prefix.startswith('.') else prefix)
                if self.completer.completionCount():
                    rect = self.cursorRect()
                    rect.setWidth(self.completer.popup().sizeHintForColumn(0) +
                                  self.completer.popup().verticalScrollBar().sizeHint().width())
                    self.completer.complete(rect)
                else:
                    self.completer.popup().hide()
            else:
                self.completer.popup().hide()
        finally:
            self._autocomplete_active = False

    def keyPressEvent(self, event) -> None:
        if self.completer.popup().isVisible():
            if event.key() in (Qt.Key_Enter, Qt.Key_Return, Qt.Key_Tab):
                self.insert_completion(self.completer.currentCompletion())
                return
            elif event.key() == Qt.Key_Escape:
                self.completer.popup().hide()
                return
            elif event.key() in (Qt.Key_Up, Qt.Key_Down):
                self.completer.popup().event(event)
                return

        if event.key() in (Qt.Key_Enter, Qt.Key_Return):
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
        if event.text() and (event.text().isalnum() or event.text() in Config.AUTOCOMPLETE_TRIGGERS):
            QTimer.singleShot(50, self.show_autocomplete)

    def format_code(self) -> None:
        try:
            import black
            formatted = black.format_str(self.toPlainText(), mode=black.Mode(line_length=88))
            self.setPlainText(formatted)
            self.document().setModified(False)
        except ImportError:
            pass
        except Exception as e:
            if hasattr(self, 'parent') and hasattr(self.parent(), 'console'):
                self.parent().console.write(f"Error formatting code: {str(e)}\n")

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        parent = self.parent()
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path.endswith('.py'):
                try:
                    with open(file_path, 'r', encoding="utf-8") as f:
                        self.setPlainText(f.read())
                    parent.current_file = file_path
                    parent._mark_saved()
                    parent.console.write(f"\n[Opened] {file_path}\n")
                except Exception as e:
                    parent.console.write(f"Error opening file: {str(e)}\n")
        event.acceptProposedAction()

    def update_error_warning_count(self) -> None:
        errors, warnings = len(self.highlighter.errors), len(self.highlighter.warnings)
        self.error_warning_label.setText(
            f"<span style='color:{Config.ERROR_COLOR}'>ⓘ {errors}</span> "
            f"<span style='color:{Config.WARNING_COLOR}'>⚠ {warnings}</span>"
        )
        self.error_warning_label.move(
            self.viewport().width() - self.error_warning_label.width() - 10, 5
        )

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        self.update_error_warning_count()


class ConsoleWidget(QTextEdit):
    """Efficient console widget"""

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
        self._running = True

    def run(self) -> None:
        if not self._running:
            return
        stdout, stderr, stdin = sys.stdout, sys.stderr, sys.stdin
        captured_output = io.StringIO()
        try:
            sys.stdout = self.console
            sys.stderr = captured_output
            sys.stdin = self.console
            exec(self.code, {'__name__': '__main__'})
        except ModuleNotFoundError as e:
            module = str(e).split("'")[1] if "'" in str(e) else str(e)
            self.error_detected.emit(module)
            self.console.write(f"{str(e)}\n")
            traceback.print_exc(file=self.console)
        except Exception as e:
            traceback.print_exc(file=self.console)
        finally:
            if error_output := captured_output.getvalue():
                self.console.write(error_output)
            sys.stdout, sys.stderr, sys.stdin = stdout, stderr, stdin
            captured_output.close()
            if self._running:
                self.finished.emit()

    def stop(self) -> None:
        self._running = False
        self.terminate()
        self.wait()

    def __del__(self):
        self.stop()


class PackageInstaller(QThread):
    """Thread for installing packages"""
    output_ready = pyqtSignal(str)
    finished = pyqtSignal(bool)

    def __init__(self, package_name: str, console: ConsoleWidget):
        super().__init__()
        self.package_name = package_name
        self.console = console
        self._running = True

    def run(self) -> None:
        if not self._running:
            return
        try:
            self.output_ready.emit(f"Installing {self.package_name}...\n")
            process = subprocess.Popen(
                [sys.executable, "-m", "pip", "install", self.package_name],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            stdout, stderr = process.communicate()
            success = process.returncode == 0
            self.output_ready.emit(
                f"{'Successfully installed' if success else 'Failed to install'} "
                f"{self.package_name}:\n{stdout if success else stderr}\n"
            )
            if self._running:
                self.finished.emit(success)
        except Exception as e:
            self.output_ready.emit(f"Error: {str(e)}\n")
            self.finished.emit(False)

    def stop(self) -> None:
        self._running = False
        self.terminate()
        self.wait()

    def __del__(self):
        self.stop()


class PythonIDE(QMainWindow):
    """Main IDE window with editor, fixed toolbar, and resizable components"""

    def __init__(self):
        super().__init__()
        self.current_file: Optional[str] = None
        self.code_is_running = False
        self.child_windows: List['PythonIDE'] = []
        self.project_dir = Config.DEFAULT_PROJECT_DIR
        self.settings = QSettings("xAI", "JaxPY")
        self.project_dir = self.settings.value("project_dir", Config.DEFAULT_PROJECT_DIR, type=str)
        self.interpreter: Optional[PythonInterpreter] = None
        self.installer: Optional[PackageInstaller] = None
        self.sidebar: Optional[Sidebar] = None
        self._init_ui()

    def _init_ui(self) -> None:
        self.setWindowTitle("JaxPY")
        self.setWindowIcon(QIcon("JaxPY.ico"))
        self.setGeometry(100, 100, 1000, 800)

        # Toolbar setup (fixed at top)
        toolbar = QToolBar()
        toolbar.setMovable(False)
        self.addToolBar(Qt.TopToolBarArea, toolbar)

        # Add JaxPY logo to toolbar
        logo_label = QLabel()
        logo_label.setPixmap(QIcon("JaxPY.ico").pixmap(24, 24))
        logo_label.setStyleSheet("padding: 5px;")
        toolbar.addWidget(logo_label)

        # Add Run button and other toolbar actions
        self.run_button = QToolButton()
        self.run_button.setText("RUN")
        self.run_button.setShortcut("F5")
        self.run_button.clicked.connect(self.run_code)
        self.run_button.setStyleSheet("background-color: green; color: white; padding: 5px 10px; border-radius: 5px;")
        toolbar.addWidget(self.run_button)

        button_style = "background-color: #1e1e1e; color: white; padding: 5px 10px; border-radius: 5px;"
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
                    menu.addAction("Set Project Directory", self.set_project_directory)
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

        # Central widget for content below toolbar
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Toggle button container (fixed below logo)
        toggle_container = QWidget()
        toggle_layout = QHBoxLayout(toggle_container)
        toggle_layout.setContentsMargins(0, 0, 0, 0)
        toggle_layout.setSpacing(0)

        # Setup sidebar (toggle button added to toggle_layout)
        self.sidebar = Sidebar(self)
        toggle_layout.addWidget(self.sidebar.toggle_button)
        toggle_layout.addStretch()
        toggle_container.setFixedHeight(40)
        toggle_container.setStyleSheet("background-color: #2D2D2D;")
        main_layout.addWidget(toggle_container)

        # Main content splitter (resizable)
        content_splitter = QSplitter(Qt.Horizontal)
        self.sidebar_content = QWidget()  # Container for Bolt AI chat
        sidebar_layout = QVBoxLayout(self.sidebar_content)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        self.bolt_ai = BoltAI(self)  # Initialize Bolt AI
        sidebar_layout.addWidget(self.bolt_ai)
        self.sidebar_content.setMinimumWidth(250)
        self.sidebar_content.setVisible(False)  # Hidden by default
        content_splitter.addWidget(self.sidebar_content)

        # Editor and console splitter (resizable vertically)
        editor_console_splitter = QSplitter(Qt.Vertical)
        self.code_editor = CodeEditor(self)
        self.code_editor.textChanged.connect(self._mark_unsaved)
        editor_console_splitter.addWidget(self.code_editor)

        console_container = QWidget()
        console_layout = QVBoxLayout(console_container)
        console_layout.setContentsMargins(0, 0, 0, 0)
        header = QHBoxLayout()
        header.addWidget(QLabel("Terminal",
                                styleSheet="color: #CCCCCC; background-color: #2D2D2D; padding: 3px; font-weight: bold;"))
        header.addStretch()
        self.save_status_dot = QLabel("●", styleSheet="color: red; background-color: #2D2D2D; padding: 3px")
        header.addWidget(self.save_status_dot)
        console_layout.addLayout(header)
        self.console = ConsoleWidget()
        console_layout.addWidget(self.console)
        editor_console_splitter.addWidget(console_container)
        editor_console_splitter.setSizes([600, 200])

        content_splitter.addWidget(editor_console_splitter)
        content_splitter.setSizes([0, 1000])  # Sidebar hidden by default
        main_layout.addWidget(content_splitter)

        self._setup_auto_save()
        self.code_editor.setPlainText(
            '# Welcome to Python IDE\n\nprint("Hello, World!")\nname = input("Enter your name: ")\nprint(f"Hello, {name}!")')
        self.setStyleSheet("""
            QMainWindow, QWidget {background-color: #1E1E1E; color: #CCCCCC;}
            QToolBar {background-color: #2D2D2D; border: none;}
            QSplitter::handle {background-color: #2D2D2D;}
            QPushButton {background-color: #0E639C; color: white; padding: 5px 10px;}
            QPushButton:hover {background-color: #1177BB;}
        """)

    def _setup_auto_save(self) -> None:
        self.auto_save_timer = QTimer(self)
        self.auto_save_timer.timeout.connect(self.auto_save)
        self.auto_save_timer.start(Config.AUTO_SAVE_INTERVAL)

    def set_project_directory(self) -> None:
        dir_path = QFileDialog.getExistingDirectory(self, "Select Project Directory", self.project_dir)
        if dir_path:
            self.project_dir = dir_path
            self.settings.setValue("project_dir", self.project_dir)
            self.console.write(f"\n[Project Directory Set] {self.project_dir}\n")

    def run_code(self) -> None:
        if self.code_is_running:
            self.console.write("\n[Stopping previous execution...]\n")
            if self.interpreter:
                self.interpreter.stop()
            self.code_is_running = False
            QTimer.singleShot(100, self.run_code)
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
        if self.interpreter:
            self.interpreter.deleteLater()
            self.interpreter = None

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
        if self.current_file and self.code_editor.document().isModified():
            self._save_to_file(self.current_file, silent=True)

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
            self.console.write(f"Failed to open new window: {str(e)}\n")

    def find_and_replace(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Find and Replace")
        dialog.setGeometry(300, 300, 350, 150)
        layout = QVBoxLayout(dialog)

        find_input = QLineEdit()
        replace_input = QLineEdit()
        match_label = QLabel("Matches: 0")
        match_positions: List[int] = []
        current_match_index = -1

        layout.addWidget(QLabel("Find:"))
        layout.addWidget(find_input)
        layout.addWidget(QLabel("Replace:"))
        layout.addWidget(replace_input)

        match_layout = QHBoxLayout()
        match_layout.addWidget(match_label)
        for text, callback in [("◀", lambda: self._prev_match(match_positions, match_label, find_input)),
                               ("▶", lambda: self._next_match(match_positions, match_label, find_input))]:
            btn = QPushButton(text)
            btn.setFixedSize(30, 30)
            btn.clicked.connect(callback)
            match_layout.addWidget(btn)
        layout.addLayout(match_layout)

        for text, callback in [
            ("Find", lambda: self._find_text(find_input, match_label, match_positions)),
            ("Replace", lambda: self._replace_text(find_input, replace_input, match_positions, match_label)),
            ("Replace All", lambda: self._replace_all_text(find_input, replace_input, dialog))
        ]:
            layout.addWidget(QPushButton(text, clicked=callback))

        dialog.exec_()

    def _find_text(self, find_input: QLineEdit, match_label: QLabel, match_positions: List[int]) -> None:
        search_text = find_input.text().strip()
        if not search_text:
            return
        document = self.code_editor.document()
        cursor = QTextCursor(document)
        match_positions.clear()
        regex = QRegExp(rf'\b{re.escape(search_text)}\b')
        while not cursor.isNull() and not cursor.atEnd():
            cursor = document.find(regex, cursor)
            if cursor.isNull():
                break
            match_positions.append(cursor.position())
        match_count = len(match_positions)
        match_label.setText(f"Matches: {match_count}")
        if match_count:
            self.current_match_index = 0
            self._highlight_match(match_positions, match_label, find_input)

    def _highlight_match(self, match_positions: List[int], match_label: QLabel, find_input: QLineEdit) -> None:
        if self.current_match_index >= 0 and match_positions:
            cursor = self.code_editor.textCursor()
            search_len = len(find_input.text())
            cursor.setPosition(match_positions[self.current_match_index] - search_len)
            cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, search_len)
            self.code_editor.setTextCursor(cursor)
            match_label.setText(f"Matches: {len(match_positions)} (Current: {self.current_match_index + 1})")

    def _next_match(self, match_positions: List[int], match_label: QLabel, find_input: QLineEdit) -> None:
        if match_positions:
            self.current_match_index = (self.current_match_index + 1) % len(match_positions)
            self._highlight_match(match_positions, match_label, find_input)

    def _prev_match(self, match_positions: List[int], match_label: QLabel, find_input: QLineEdit) -> None:
        if match_positions:
            self.current_match_index = (self.current_match_index - 1) % len(match_positions)
            self._highlight_match(match_positions, match_label, find_input)

    def _replace_text(self, find_input: QLineEdit, replace_input: QLineEdit, match_positions: List[int],
                      match_label: QLabel) -> None:
        if self.current_match_index >= 0 and match_positions:
            cursor = self.code_editor.textCursor()
            search_text = find_input.text()
            if cursor.hasSelection() and cursor.selectedText() == search_text:
                replace_text = replace_input.text()
                cursor.insertText(replace_text)
                match_positions[self.current_match_index] += len(replace_text) - len(search_text)
            self._find_text(find_input, match_label, match_positions)

    def _replace_all_text(self, find_input: QLineEdit, replace_input: QLineEdit, dialog: QDialog) -> None:
        search_text = find_input.text().strip()
        replace_text = replace_input.text()
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
        dialog.accept()

    def _handle_module_error(self, module_name: str) -> None:
        if QMessageBox.question(self, "Missing Package",
                                f"Module '{module_name}' not found. Install it?") == QMessageBox.Yes:
            self.install_package(module_name)

    def show_package_installer(self) -> None:
        package_name, ok = QInputDialog.getText(self, "Install Package", "Enter package name:")
        if ok and package_name:
            self.install_package(package_name)

    def show_installed_packages(self) -> None:
        try:
            result = subprocess.run([sys.executable, "-m", "pip", "list"], capture_output=True, text=True, check=True)
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

            layout.addWidget(QPushButton("Close", clicked=dialog.accept,
                                         styleSheet="background-color: #0E639C; color: white; padding: 5px;"))
            dialog.exec_()
        except subprocess.CalledProcessError as e:
            QMessageBox.warning(self, "Error", f"Failed to list packages: {str(e)}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Unexpected error: {str(e)}")

    def install_package(self, package_name: str) -> None:
        if self.installer and self.installer.isRunning():
            self.installer.stop()
        self.console.write(f"\nInstalling {package_name}...\n")
        self.installer = PackageInstaller(package_name, self.console)
        self.installer.output_ready.connect(self.console.write)
        self.installer.finished.connect(lambda success: self._on_installation_finished(success, package_name))
        self.installer.start()

    def _on_installation_finished(self, success: bool, package_name: str) -> None:
        msg = f"Package '{package_name}' {'installed successfully' if success else 'installation failed'}"
        (QMessageBox.information if success else QMessageBox.warning)(self, "Installation", msg)
        self.console.write("\n>>> ")
        if self.installer:
            self.installer.deleteLater()
            self.installer = None

    def format_code(self) -> None:
        self.code_editor.format_code()

    def closeEvent(self, event) -> None:
        for window in self.child_windows[:]:
            window.close()
        self.child_windows.clear()

        if hasattr(self, 'auto_save_timer'):
            self.auto_save_timer.stop()
            self.auto_save_timer.deleteLater()

        if self.interpreter and self.interpreter.isRunning():
            self.interpreter.stop()
            self.interpreter = None

        if self.installer and self.installer.isRunning():
            self.installer.stop()
            self.installer = None

        if self.sidebar:
            self.sidebar.cleanup()
            self.sidebar = None

        super().closeEvent(event)


class Sidebar:
    """Sidebar class managing toggle functionality"""

    def __init__(self, parent: PythonIDE):
        self.parent = parent
        self.sidebar_visible = False
        self.toggle_button: Optional[QPushButton] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.toggle_button = QPushButton()
        self.toggle_button.setIcon(QIcon("bolt.png"))  # Bolt AI icon
        self.toggle_button.setIconSize(QSize(30, 30))
        self.toggle_button.setFixedSize(35, 35)
        self.toggle_button.setStyleSheet("""
            QPushButton {background-color: #2D2D2D; color: #CCCCCC; border: none; padding: 0px; margin: 0px;}
            QPushButton:hover {background-color: #3A3A3A;}
        """)
        self.toggle_button.clicked.connect(self._toggle_sidebar)
        self.toggle_button.setToolTip("Show Bolt AI")

    def _toggle_sidebar(self) -> None:
        self.sidebar_visible = not self.sidebar_visible
        self.parent.sidebar_content.setVisible(self.sidebar_visible)
        self.toggle_button.setToolTip("Hide Bolt AI" if self.sidebar_visible else "Show Bolt AI")

        # Adjust splitter sizes when toggling
        splitter = self.parent.centralWidget().layout().itemAt(1).widget()
        if self.sidebar_visible:
            splitter.setSizes([250, splitter.sizes()[1]])  # Show sidebar with initial width
        else:
            splitter.setSizes([0, splitter.sizes()[1]])  # Hide sidebar

    def cleanup(self) -> None:
        if self.toggle_button:
            self.toggle_button.deleteLater()
            self.toggle_button = None


if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        ide = PythonIDE()
        ide.show()
        sys.exit(app.exec_())
    except Exception as e:
        print(f"Failed to start application: {str(e)}")
        sys.exit(1)