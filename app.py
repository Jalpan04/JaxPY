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
from PyQt5.QtGui import QColor, QTextCharFormat, QFont, QPalette, QSyntaxHighlighter, QTextCursor, QIcon, QPainter, \
    QTextFormat
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QSplitter, QTextEdit, QPlainTextEdit, QFileDialog, QDialog,
    QLineEdit, QPushButton, QLabel, QMessageBox, QInputDialog,
    QAction, QToolBar, QToolButton, QMenu, QCompleter, QListWidget, QListWidgetItem, QSizePolicy
)

from bolt_ai import BoltAI  # Assuming this is an external dependency


class Config:
    """Centralized configuration constants"""
    COLORS = {
        "background": "#1E1F22",
        "secondary_bg": "#353535",
        "text": "#D4D4D4",
        "accent": "#ECDC51",
        "secondary_accent": "#FFC61A",
        "line_number_bg": "#2A2B2E",
        "line_number_fg": "#8A8A8A",
        "error": "#FF5555",
        "warning": "#FFC107",
        "keyword": "#569CD6",
        "string": "#CE9178",
        "comment": "#6A9955",
        "number": "#B5CEA8",
        "function": "#DCDCAA",
        "operator": "#D4D4D4"
    }
    EDITOR_FONT = "Consolas"
    FONT_SIZE = 12
    AUTO_SAVE_INTERVAL = 30000
    PYTHON_BUILTINS = dir(builtins)
    COMMON_IMPORTS = [
        "os", "sys", "math", "random", "datetime", "time", "json",
        "re", "subprocess", "threading", "multiprocessing", "socket",
        "requests", "numpy", "pandas", "matplotlib", "tkinter"
    ]
    AUTOCOMPLETE_TRIGGERS = [".", "im"]
    DEFAULT_PROJECT_DIR = os.getcwd()

    BUTTON_STYLE = """
        QToolButton {
            background-color: #353535;
            color: #ECDC51;
            border: 1px solid #FFC61A;
            padding: 6px 12px;
            border-radius: 6px;
            font-family: Consolas;
            font-weight: 600;
            font-size: 18px;
            min-width: 80px;
            min-height: 20px;
        }
        QToolButton:hover {
            background-color: #FFC61A;
            color: #1E1F22;
            border-color: #ECDC51;
        }
        QToolButton:pressed {
            background-color: #ECDC51;
            color: #1E1F22;
            border-color: #FFC61A;
        }
    """

    RUN_BUTTON_RUNNING_STYLE = """
        QToolButton {
            background-color: #75FB4C;
            color: #1E1F22;
            border: 1px solid #75FB4C;
            padding: 6px 12px;
            border-radius: 6px;
            font-family: Consolas;
            font-weight: 600;
            min-width: 25px;
            min-height: 30px;
        }
        QToolButton:hover {
            background-color: #FFC61A;
            color: #1E1F22;
            box-shadow: 0 0 8px rgba(236, 220, 81, 0.5);
        }
    """

    RUN_BUTTON_NOT_RUNNING_STYLE = """
        QToolButton {
            background-color: #353535;
            color: #00CC00;
            border: 1px solid #00CC00;
            padding: 6px 12px;
            border-radius: 6px;
            font-family: Consolas;
            font-weight: 600;
            font-size: 18px;
            min-width: 20px;
            min-height: 20px;
        }
        QToolButton:hover {
            background-color: #00CC00;
            color: #1E1F22;
            border-color: #66FF66;
        }
        QToolButton:pressed {
            background-color: #009900;
            color: #1E1F22;
            border-color: #00CC00;
        }
    """

    STOP_BUTTON_STYLE = """
        QToolButton {
            background-color: #353535;
            color: #FF5555;
            border: 1px solid #FF5555;
            padding: 6px 12px;
            border-radius: 6px;
            font-family: Consolas;
            font-weight: 600;
            min-width: 20px;
            min-height: 20px;
        }
        QToolButton:hover {
            background-color: #FF5555;
            color: #1E1F22;
        }
        QToolButton:pressed {
            background-color: #CC4444;
            color: #1E1F22;
        }
    """

    BOLT_BUTTON_STYLE = """
        QPushButton {
            background-color: #353535;
            color: #ECDC51;
            border: 1px solid #FFC61A;
            padding: 8px;
            border-radius: 8px;
        }
        QPushButton:hover {
            background-color: #FFC61A;
            color: #1E1F22;
            border-color: #ECDC51;
        }
        QPushButton:pressed {
            background-color: #ECDC51;
            color: #1E1F22;
            border-color: #FFC61A;
        }
    """

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
            (QRegExp('|'.join(r'\b' + kw + r'\b' for kw in keyword.kwlist)),
             cls._create_format(Config.COLORS["keyword"], True)),
            (QRegExp(r'"[^"\\]*(\\.[^"\\]*)*"'), cls._create_format(Config.COLORS["string"])),
            (QRegExp(r"'[^'\\]*(\\.[^'\\]*)*'"), cls._create_format(Config.COLORS["string"])),
            (QRegExp(r'#[^\n]*'), cls._create_format(Config.COLORS["comment"])),
            (QRegExp(r'\b[0-9]+\.?[0-9]*\b'), cls._create_format(Config.COLORS["number"])),
            (QRegExp(r'[\+\-\*/=<>!&|%^]+'), cls._create_format(Config.COLORS["operator"])),
            (QRegExp(r'def\s+(\w+)\s*\('), cls._create_format(Config.COLORS["function"]))
        ]

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
        except (SyntaxError, IndentationError) as e:
            if hasattr(e, 'lineno') and e.lineno is not None:
                self.errors[e.lineno - 1] = str(e)
        except Exception as e:
            self.errors[0] = f"General error: {str(e)}"

    def _check_warnings(self, text: str, line_number: int) -> None:
        self.warnings.pop(line_number, None)
        stripped = text.strip()
        if not stripped or stripped.startswith('#'):
            return
        warning_patterns = [
            (r'\bprint\s+[^(\n]', "Old-style print statement"),
            (r'^\s*from\s+\w+\s+import\s+\*', "Wildcard import detected"),
            (r'^(def|class|if|for|while)\s+\w+$', "Missing colon")
        ]
        for pattern, msg in warning_patterns:
            if re.search(pattern, text):
                self.warnings[line_number] = msg
                break

    def highlightBlock(self, text: str) -> None:
        for pattern, fmt in self.rules:
            index = pattern.indexIn(text)
            while index >= 0:
                length = pattern.matchedLength()
                if pattern.pattern().startswith('def\\s+'):
                    func_index = index + 4
                    func_length = len(pattern.capturedTexts()[1])
                    self.setFormat(func_index, func_length, fmt)
                else:
                    self.setFormat(index, length, fmt)
                index = pattern.indexIn(text, index + length)

        line_number = self.currentBlock().blockNumber()
        self._check_warnings(text, line_number)
        if line_number in self.errors:
            fmt = HighlightRules._create_format(Config.COLORS["error"])
            fmt.setUnderlineStyle(QTextCharFormat.WaveUnderline)
            self.setFormat(0, len(text), fmt)
        elif line_number in self.warnings:
            fmt = HighlightRules._create_format(Config.COLORS["warning"])
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
        painter.fillRect(event.rect(), QColor(Config.COLORS["line_number_bg"]))
        block = self.editor.firstVisibleBlock()
        top = int(self.editor.blockBoundingGeometry(block).translated(self.editor.contentOffset()).top())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible():
                block_num = block.blockNumber()
                painter.setPen(QColor(Config.COLORS["line_number_fg"]))
                painter.drawText(
                    QRect(5, top, self.width() - 5, self.editor.fontMetrics().height()),
                    Qt.AlignLeft, str(block_num + 1)
                )
                if block_num in self.editor.foldable_lines:
                    fold_type = self.editor.fold_types.get(block_num, "other")
                    base_color = {"def": "#52585C", "class": "#61686D"}.get(fold_type, "#71797E")
                    painter.setPen(
                        QColor(base_color if block_num != self.hovered_line else Config.COLORS["secondary_accent"]))
                    arrow = "▼" if block_num not in self.editor.folded_blocks else "▶"
                    painter.drawText(
                        QRect(self.width() - 20, top, 15, self.editor.fontMetrics().height()),
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
    """Optimized code editor"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ide_parent = parent if isinstance(parent, PythonIDE) else None
        self.line_number_area = LineNumberArea(self)
        self.highlighter = PythonHighlighter(self.document())
        self.foldable_lines: Set[int] = set()
        self.folded_blocks: Set[int] = set()
        self.fold_ranges: Dict[int, int] = {}
        self.fold_types: Dict[int, str] = {}
        self.completer = None
        self._autocomplete_active = False
        self._setup_ui()
        self._setup_autocomplete()

    def _setup_ui(self) -> None:
        font = QFont(Config.EDITOR_FONT, Config.FONT_SIZE)
        font.setFixedPitch(True)
        self.setFont(font)
        palette = QPalette()
        palette.setColor(QPalette.Base, QColor(Config.COLORS["background"]))
        palette.setColor(QPalette.Text, QColor(Config.COLORS["text"]))
        self.setPalette(palette)
        self.setStyleSheet(f"""
            QPlainTextEdit {{
                border: 1px solid {Config.COLORS["secondary_bg"]};
                border-radius: 6px;
                padding: 4px;
                selection-background-color: {Config.COLORS["secondary_accent"]};
                selection-color: {Config.COLORS["background"]};
            }}
        """)
        self.setTabStopWidth(self.fontMetrics().width(' ') * 4)
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)
        self.textChanged.connect(self._on_text_changed)
        self.setAcceptDrops(True)

    def _on_text_changed(self) -> None:
        self.highlighter.update_full_code(self.toPlainText())
        self.detect_foldable_lines()
        if self.ide_parent:
            self.ide_parent.update_error_warning_count()

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
            selection.format.setBackground(QColor(Config.COLORS["line_number_bg"]))
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
                current_indent = len(text) - len(text.lstrip())
                current_line = block.blockNumber()
                while indent_stack and indent_stack[-1][1] >= current_indent:
                    start_line, _, block_type = indent_stack.pop()
                    if current_line - start_line > 1:
                        self._add_foldable(start_line, current_line - 1, block_type)
                if re.match(r'^(def|class|if|for|while|try:|with\s+)', text):
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
        self.completer.popup().setStyleSheet(f"""
            QListView {{ 
                background-color: {Config.COLORS["secondary_bg"]}; 
                color: {Config.COLORS["text"]}; 
                border: 1px solid {Config.COLORS["secondary_accent"]};
                border-radius: 4px;
                padding: 2px;
                font-family: {Config.EDITOR_FONT};
            }}
            QListView::item {{ padding: 4px 8px; }}
            QListView::item:hover {{ 
                background-color: {Config.COLORS["accent"]}; 
                color: {Config.COLORS["background"]}; 
            }}
            QListView::item:selected {{
                background-color: {Config.COLORS["secondary_accent"]};
                color: {Config.COLORS["background"]};
            }}
        """)

    def insert_completion(self, completion: str) -> None:
        cursor = self.textCursor()
        extra = len(completion) - len(self.completer.completionPrefix())
        cursor.movePosition(QTextCursor.Left)
        cursor.movePosition(QTextCursor.EndOfWord)
        cursor.insertText(completion[-extra:] if extra > 0 else completion)
        self.setTextCursor(cursor)

    def show_autocomplete(self) -> None:
        if self._autocomplete_active or not self.completer:
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
        if self.completer and self.completer.popup().isVisible():
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
            if self.ide_parent:
                self.ide_parent.console.write("Black formatter not installed\n")
        except Exception as e:
            if self.ide_parent:
                self.ide_parent.console.write(f"Error formatting code: {str(e)}\n")

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        if not self.ide_parent:
            return
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path.endswith('.py'):
                try:
                    with open(file_path, 'r', encoding="utf-8") as f:
                        self.setPlainText(f.read())
                    self.ide_parent.current_file = file_path
                    self.ide_parent._mark_saved()
                    self.ide_parent.console.write(f"\n[Opened] {file_path}\n")
                except Exception as e:
                    self.ide_parent.console.write(f"Error opening file: {str(e)}\n")
        event.acceptProposedAction()

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
        palette.setColor(QPalette.Base, QColor(Config.COLORS["background"]))
        palette.setColor(QPalette.Text, QColor(Config.COLORS["text"]))
        self.setPalette(palette)
        self.setStyleSheet(f"""
            QTextEdit {{
                border: 1px solid {Config.COLORS["secondary_bg"]};
                border-radius: 6px;
                padding: 4px;
                selection-background-color: {Config.COLORS["secondary_accent"]};
                selection-color: {Config.COLORS["background"]};
            }}
        """)
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

class PythonIDE(QMainWindow):
    """Main IDE window"""
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

        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setStyleSheet(f"""
            QToolBar {{
                background: {Config.COLORS["background"]};
                border-bottom: 1px solid {Config.COLORS["secondary_accent"]};
                padding: 4px;
                spacing: 6px;
            }}
        """)
        self.addToolBar(Qt.TopToolBarArea, toolbar)

        logo_label = QLabel()
        logo_label.setPixmap(QIcon("JaxPY.ico").pixmap(40, 40))
        logo_label.setStyleSheet("padding: 4px; border: none;")
        toolbar.addWidget(logo_label)

        button_specs = [
            ("File", None, None, True, [
                ("New", self.new_file),
                ("New Window", self.new_window),
                ("Set Project Directory", self.set_project_directory)
            ]),
            ("Open", "Ctrl+O", self.open_file, False, None),
            ("Save", "Ctrl+S", self.save_file, False, None),
            ("Find / Replace", "Ctrl+F", self.find_and_replace, False, None),
            ("Packages", None, None, True, [
                ("Install Packages", self.show_package_installer),
                ("Installed Packages", self.show_installed_packages)
            ]),
            ("Format", "Ctrl+Shift+F", self.format_code, False, None)
        ]

        for name, shortcut, callback, has_menu, menu_items in button_specs:
            btn = QToolButton()
            btn.setText(name)
            btn.setStyleSheet(Config.BUTTON_STYLE)
            if shortcut:
                btn.setShortcut(shortcut)
            if has_menu and menu_items:
                btn.setPopupMode(QToolButton.InstantPopup)
                menu = QMenu(self)
                menu.setStyleSheet(f"""
                    QMenu {{
                        background-color: {Config.COLORS["secondary_bg"]};
                        color: {Config.COLORS["text"]};
                        border: 1px solid {Config.COLORS["secondary_accent"]};
                        border-radius: 4px;
                        padding: 4px;
                    }}
                    QMenu::item {{
                        padding: 6px 12px;
                    }}
                    QMenu::item:selected {{
                        background-color: {Config.COLORS["accent"]};
                        color: {Config.COLORS["background"]};
                    }}
                """)
                for menu_text, menu_callback in menu_items:
                    menu.addAction(menu_text, menu_callback)
                btn.setMenu(menu)
            elif callback:
                btn.clicked.connect(callback)
            toolbar.addWidget(btn)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(spacer)

        self.run_button = QToolButton()
        self.run_button.setIcon(QIcon("images/play_green.png"))
        self.run_button.setIconSize(QSize(24, 24))
        self.run_button.setShortcut("F5")
        self.run_button.clicked.connect(self.run_code)
        self.run_button.setStyleSheet(Config.RUN_BUTTON_NOT_RUNNING_STYLE)  # Fixed reference
        self.run_button.setToolTip("Run Code (F5)")
        toolbar.addWidget(self.run_button)

        self.stop_button = QToolButton()
        self.stop_button.setIcon(QIcon("images/stop.png"))
        self.stop_button.setIconSize(QSize(24, 24))
        self.stop_button.clicked.connect(self.stop_code)
        self.stop_button.setStyleSheet(Config.STOP_BUTTON_STYLE)  # Fixed reference
        self.stop_button.setToolTip("Stop Code")
        toolbar.addWidget(self.stop_button)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(4)

        toggle_container = QWidget()
        toggle_layout = QHBoxLayout(toggle_container)
        toggle_layout.setContentsMargins(4, 0, 4, 0)
        toggle_layout.setSpacing(6)

        self.sidebar = Sidebar(self)
        toggle_layout.addWidget(self.sidebar.toggle_button)
        toggle_layout.addStretch()

        self.error_icon_label = QLabel()
        self.error_icon_label.setPixmap(QIcon("images/error.png").pixmap(24, 24))
        self.error_icon_label.setStyleSheet(f"""
            background: {Config.COLORS["secondary_bg"]};
            padding: 4px;
            border-radius: 4px;
        """)
        self.error_icon_label.setToolTip("Errors in code")
        toggle_layout.addWidget(self.error_icon_label)

        self.error_count_label = QLabel("0")
        self.error_count_label.setStyleSheet(f"""
            color: {Config.COLORS["error"]};
            background: {Config.COLORS["secondary_bg"]};
            padding: 4px 8px;
            font-family: {Config.EDITOR_FONT};
        """)
        toggle_layout.addWidget(self.error_count_label)

        self.warning_icon_label = QLabel()
        self.warning_icon_label.setPixmap(QIcon("images/warning.png").pixmap(24, 24))
        self.warning_icon_label.setStyleSheet(f"""
            background: {Config.COLORS["secondary_bg"]};
            padding: 4px;
            border-radius: 4px;
        """)
        self.warning_icon_label.setToolTip("Warnings in code")
        toggle_layout.addWidget(self.warning_icon_label)

        self.warning_count_label = QLabel("0")
        self.warning_count_label.setStyleSheet(f"""
            color: {Config.COLORS["warning"]};
            background: {Config.COLORS["secondary_bg"]};
            padding: 4px 8px;
            font-family: {Config.EDITOR_FONT};
        """)
        toggle_layout.addWidget(self.warning_count_label)

        toggle_container.setFixedHeight(55)
        toggle_container.setStyleSheet(f"""
            background: {Config.COLORS["secondary_bg"]};
            border-bottom: 1px solid {Config.COLORS["secondary_accent"]};
            border-radius: 6px 6px 0 0;
        """)
        main_layout.addWidget(toggle_container)

        content_splitter = QSplitter(Qt.Horizontal)
        content_splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background: {Config.COLORS["secondary_bg"]};
                width: 4px;
            }}
            QSplitter::多元handle:hover {{
                background: {Config.COLORS["secondary_accent"]};
            }}
        """)
        self.sidebar_content = QWidget()
        sidebar_layout = QVBoxLayout(self.sidebar_content)
        sidebar_layout.setContentsMargins(4, 4, 4, 4)
        self.bolt_ai = BoltAI(self)
        sidebar_layout.addWidget(self.bolt_ai)
        self.sidebar_content.setMinimumWidth(250)
        self.sidebar_content.setVisible(False)
        content_splitter.addWidget(self.sidebar_content)

        editor_console_splitter = QSplitter(Qt.Vertical)
        editor_console_splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background: {Config.COLORS["secondary_bg"]};
                height: 4px;
            }}
            QSplitter::handle:hover {{
                background: {Config.COLORS["secondary_accent"]};
            }}
        """)
        self.code_editor = CodeEditor(self)
        self.code_editor.textChanged.connect(self._mark_unsaved)
        editor_console_splitter.addWidget(self.code_editor)

        console_container = QWidget()
        console_layout = QVBoxLayout(console_container)
        console_layout.setContentsMargins(0, 0, 0, 0)
        console_layout.setSpacing(2)
        header = QHBoxLayout()

        terminal_label = QLabel(" Terminal")
        terminal_label.setStyleSheet(f"""
            color: {Config.COLORS["accent"]};
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {Config.COLORS["secondary_bg"]}, stop:1 {Config.COLORS["line_number_bg"]});
            padding: 6px 12px;
            border: 1px solid {Config.COLORS["secondary_accent"]};
            border-radius: 6px;
            font-weight: 600;
            font-family: {Config.EDITOR_FONT};
            font-size: 16px;
        """)
        terminal_label.setToolTip("Terminal Output")
        header.addWidget(terminal_label)

        header.addStretch()

        self.save_status_dot = QLabel("✗")
        self.save_status_dot.setStyleSheet(f"""
            color: {Config.COLORS["error"]};
            background: {Config.COLORS["secondary_bg"]};
            padding: 4px 8px;
            border: 1px solid {Config.COLORS["secondary_bg"]};
            border-radius: 4px;
            font-size: 14px;
            font-family: {Config.EDITOR_FONT};
        """)
        self.save_status_dot.setToolTip("File has unsaved changes")
        header.addWidget(self.save_status_dot)

        console_layout.addLayout(header)
        self.console = ConsoleWidget()
        console_layout.addWidget(self.console)
        editor_console_splitter.addWidget(console_container)
        editor_console_splitter.setSizes([600, 200])

        content_splitter.addWidget(editor_console_splitter)
        content_splitter.setSizes([0, 1000])
        main_layout.addWidget(content_splitter)

        self._setup_auto_save()
        self.code_editor.setPlainText(
            '# Welcome to JaxPY\n\nprint("Hello, World!")\nname = input("Enter your name: ")\nprint(f"Hello, {name}!")')
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{
                background: {Config.COLORS["background"]};
                color: {Config.COLORS["text"]};
            }}
            QScrollBar:vertical, QScrollBar:horizontal {{
                border: none;
                background: {Config.COLORS["line_number_bg"]};
                width: 10px;
                height: 10px;
                margin: 0;
            }}
            QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
                background: {Config.COLORS["secondary_bg"]};
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {{
                background: {Config.COLORS["secondary_accent"]};
            }}
            QScrollBar::add-line, QScrollBar::sub-line {{
                background: none;
            }}
            QMessageBox, QDialog {{
                background: {Config.COLORS["background"]};
                color: {Config.COLORS["text"]};
                border: 1px solid {Config.COLORS["secondary_bg"]};
                border-radius: 6px;
            }}
            QLineEdit {{
                background: {Config.COLORS["line_number_bg"]};
                color: {Config.COLORS["text"]};
                border: 1px solid {Config.COLORS["secondary_bg"]};
                padding: 6px;
                border-radius: 4px;
            }}
            QLineEdit:focus {{
                border-color: {Config.COLORS["secondary_accent"]};
            }}
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
            self.console.write("\n[Execution already in progress]\n")
            return

        self.code_is_running = True
        self.run_button.setEnabled(False)
        self.run_button.setIcon(QIcon("images/run.png"))
        self.run_button.setStyleSheet(Config.RUN_BUTTON_RUNNING_STYLE)  # Fixed reference
        self.console.clear()

        self.interpreter = PythonInterpreter(self.code_editor.toPlainText(), self.console)
        self.interpreter.finished.connect(self._on_execution_finished)
        self.interpreter.error_detected.connect(self._handle_module_error)
        self.interpreter.start()

    def stop_code(self) -> None:
        if not self.code_is_running:
            self.console.write("\n[No execution to stop]\n")
            return

        if self.interpreter and self.interpreter.isRunning():
            self.interpreter.stop()
        self._reset_execution_state()
        self.console.clear()

    def _on_execution_finished(self) -> None:
        self.console.write("\n[Execution finished]\n>>> ")
        self._reset_execution_state()

    def _reset_execution_state(self) -> None:
        self.code_is_running = False
        self.run_button.setEnabled(True)
        self.run_button.setIcon(QIcon("images/play_green.png"))
        self.run_button.setStyleSheet(Config.RUN_BUTTON_NOT_RUNNING_STYLE)  # Fixed reference
        if self.interpreter:
            self.interpreter.deleteLater()
            self.interpreter = None

    def _handle_module_error(self, module_name: str) -> None:
        self.console.write(f"\n[Module Error] {module_name} not found.\n")
        if QMessageBox.question(self, "Missing Package",
                                f"Module '{module_name}' not found. Install it?") == QMessageBox.Yes:
            self.install_package(module_name)
        self._reset_execution_state()

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
        self.save_status_dot.setPixmap(QIcon("images/unsaved.png").pixmap(16, 16))
        self.save_status_dot.setStyleSheet(f"""
            color: {Config.COLORS["error"]};
            background: {Config.COLORS["secondary_bg"]};
            padding: 4px 8px;
            border: 1px solid {Config.COLORS["error"]};
            border-radius: 4px;
        """)
        self.save_status_dot.setToolTip("File has unsaved changes")

    def _mark_saved(self) -> None:
        self.save_status_dot.setPixmap(QIcon("images/saved.png").pixmap(16, 16))
        self.save_status_dot.setStyleSheet(f"""
            color: {Config.COLORS["accent"]};
            background: {Config.COLORS["secondary_bg"]};
            padding: 4px 8px;
            border: 1px solid {Config.COLORS["accent"]};
            border-radius: 4px;
        """)
        self.save_status_dot.setToolTip("File is saved")

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
        layout.setSpacing(6)

        find_input = QLineEdit()
        replace_input = QLineEdit()
        find_input.setStyleSheet(f"""
            background-color: {Config.COLORS["line_number_bg"]};
            color: {Config.COLORS["text"]};
            padding: 6px;
            border: 1px solid {Config.COLORS["secondary_bg"]};
            border-radius: 4px;
        """)
        replace_input.setStyleSheet(f"""
            background-color: {Config.COLORS["line_number_bg"]};
            color: {Config.COLORS["text"]};
            padding: 6px;
            border: 1px solid {Config.COLORS["secondary_bg"]};
            border-radius: 4px;
        """)
        match_label = QLabel("Matches: 0")
        match_label.setStyleSheet(f"""
            color: {Config.COLORS["accent"]};
            font-family: {Config.EDITOR_FONT};
            padding: 4px;
        """)
        match_positions: List[int] = []
        self.current_match_index = -1

        layout.addWidget(QLabel("Find:", styleSheet=f"color: {Config.COLORS["text"]}; font-family: {Config.EDITOR_FONT};"))
        layout.addWidget(find_input)
        layout.addWidget(QLabel("Replace:", styleSheet=f"color: {Config.COLORS["text"]}; font-family: {Config.EDITOR_FONT};"))
        layout.addWidget(replace_input)

        match_layout = QHBoxLayout()
        match_layout.addWidget(match_label)
        for text, callback in [("◀", lambda: self._prev_match(match_positions, match_label, find_input)),
                               ("▶", lambda: self._next_match(match_positions, match_label, find_input))]:
            btn = QPushButton(text)
            btn.setFixedSize(30, 30)
            btn.setStyleSheet(Config.BUTTON_STYLE)
            btn.clicked.connect(callback)
            match_layout.addWidget(btn)
        layout.addLayout(match_layout)

        for text, callback in [
            ("Find", lambda: self._find_text(find_input, match_label, match_positions)),
            ("Replace", lambda: self._replace_text(find_input, replace_input, match_positions, match_label)),
            ("Replace All", lambda: self._replace_all_text(find_input, replace_input, dialog))
        ]:
            btn = QPushButton(text)
            btn.setStyleSheet(Config.BUTTON_STYLE)
            btn.clicked.connect(callback)
            layout.addWidget(btn)

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
            layout = QVBoxLayout(dialog)
            layout.setSpacing(6)

            search_bar = QLineEdit()
            search_bar.setPlaceholderText("Search packages...")
            search_bar.setStyleSheet(f"""
                background-color: {Config.COLORS["line_number_bg"]};
                color: {Config.COLORS["text"]};
                padding: 6px;
                border: 1px solid {Config.COLORS["secondary_bg"]};
                border-radius: 4px;
            """)
            layout.addWidget(search_bar)

            package_list = QListWidget()
            package_list.setStyleSheet(f"""
                QListWidget {{
                    background-color: {Config.COLORS["line_number_bg"]};
                    color: {Config.COLORS["text"]};
                    border: 1px solid {Config.COLORS["secondary_bg"]};
                    border-radius: 4px;
                    padding: 4px;
                }}
                QListWidget::item {{
                    padding: 6px;
                }}
                QListWidget::item:hover {{
                    background-color: {Config.COLORS["secondary_bg"]};
                }}
                QListWidget::item:selected {{
                    background-color: {Config.COLORS["accent"]};
                    color: {Config.COLORS["background"]};
                }}
            """)
            for pkg in packages:
                if pkg.strip():
                    QListWidgetItem(pkg.strip(), package_list)
            layout.addWidget(package_list)

            search_bar.textChanged.connect(
                lambda text: [package_list.item(i).setHidden(text.lower() not in package_list.item(i).text().lower())
                              for i in range(package_list.count())]
            )

            close_btn = QPushButton("Close")
            close_btn.setStyleSheet(Config.BUTTON_STYLE)
            close_btn.clicked.connect(dialog.accept)
            layout.addWidget(close_btn)

            dialog.exec_()
        except subprocess.CalledProcessError as e:
            QMessageBox.warning(self, "Error", f"Failed to list packages: {str(e)}")

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

    def update_error_warning_count(self) -> None:
        errors, warnings = len(self.code_editor.highlighter.errors), len(self.code_editor.highlighter.warnings)
        self.error_count_label.setText(f"{errors}")
        self.warning_count_label.setText(f"{warnings}")

    def closeEvent(self, event) -> None:
        for window in self.child_windows[:]:
            window.close()
        self.child_windows.clear()

        if hasattr(self, 'auto_save_timer'):
            self.auto_save_timer.stop()
            self.auto_save_timer.deleteLater()

        if self.interpreter and self.interpreter.isRunning():
            self.interpreter.stop()

        if self.installer and self.installer.isRunning():
            self.installer.stop()

        if self.sidebar:
            self.sidebar.cleanup()

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
        self.toggle_button.setIcon(QIcon("images/bolt.png"))
        self.toggle_button.setFixedSize(45, 45)
        self.toggle_button.setIconSize(QSize(40, 40))
        self.toggle_button.setStyleSheet(Config.BOLT_BUTTON_STYLE)
        self.toggle_button.clicked.connect(self._toggle_sidebar)
        self.toggle_button.setToolTip("Show Bolt AI")

    def _toggle_sidebar(self) -> None:
        self.sidebar_visible = not self.sidebar_visible
        splitter = self.parent.centralWidget().layout().itemAt(1).widget()
        self.parent.sidebar_content.setVisible(self.sidebar_visible)
        self.toggle_button.setToolTip("Hide Bolt AI" if self.sidebar_visible else "Show Bolt AI")
        splitter.setSizes([250 if self.sidebar_visible else 0, splitter.width()])

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