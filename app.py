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
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QRegExp, QSize, QTimer, QRect, QSettings, QPropertyAnimation
from PyQt5.QtGui import (
    QColor, QTextCharFormat, QFont, QPalette, QSyntaxHighlighter,
    QTextCursor, QIcon, QPainter, QTextFormat
)
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QSplitter, QTextEdit, QPlainTextEdit, QFileDialog, QDialog,
    QLineEdit, QPushButton, QLabel, QMessageBox, QInputDialog,
    QAction, QToolBar, QToolButton, QMenu, QCompleter, QListWidget, QListWidgetItem, QSizePolicy
)

from bolt_ai import BoltAI

class Config:
    """Centralized configuration constants"""
    EDITOR_FONT = "Consolas"
    FONT_SIZE = 12
    BACKGROUND_COLOR = "#1E1F22"
    SECONDARY_BG = "#353535"
    TEXT_COLOR = "#D4D4D4"
    ACCENT_COLOR = "#ECDC51"
    SECONDARY_ACCENT = "#FFC61A"
    LINE_NUMBER_BG = "#2A2B2E"
    LINE_NUMBER_FG = "#8A8A8A"
    ERROR_COLOR = "#FF5555"
    WARNING_COLOR = "#FFC107"
    # New colors for syntax highlighting
    KEYWORD_COLOR = "#569CD6"  # Blue
    STRING_COLOR = "#CE9178"  # Peach
    COMMENT_COLOR = "#6A9955"  # Green
    NUMBER_COLOR = "#B5CEA8"  # Light green
    FUNCTION_COLOR = "#DCDCAA"  # Light yellow
    OPERATOR_COLOR = "#D4D4D4"  # White
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
            transition: all 0.2s;
        }
        QToolButton:hover {
            background-color: #FFC61A;
            color: #1E1F22;
            border-color: #ECDC51;
            box-shadow: 0 0 8px rgba(236, 220, 81, 0.5);
        }
        QToolButton:pressed {
            background-color: #ECDC51;
            color: #1E1F22;
            border-color: #FFC61A;
            box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.2);
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
                transition: all 0.2s;
            }
            QToolButton:hover {
                background-color: #FF5555;
                color: #1E1F22;
                box-shadow: 0 0 8px rgba(255, 85, 85, 0.5);
            }
            QToolButton:pressed {
                background-color: #CC4444;
                color: #1E1F22;
                box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.2);
            }
        """
    BOLT_BUTTON_STYLE = """
        QPushButton {
            background-color: #353535;
            color: #ECDC51;
            border: 1px solid #FFC61A;
            padding: 8px;  /* Increased padding for larger appearance */
            border-radius: 8px;  /* Slightly larger radius */
            transition: all 0.3s;  /* Slightly longer transition for smoothness */
        }
        QPushButton:hover {
            background-color: #FFC61A;
            color: #1E1F22;
            border-color: #ECDC51;
            box-shadow: 0 0 12px rgba(236, 220, 81, 0.7);  /* Brighter, larger glow */
            transform: scale(1.05);  /* Slight size increase on hover */
        }
        QPushButton:pressed {
            background-color: #ECDC51;
            color: #1E1F22;
            border-color: #FFC61A;
            box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.2);
        }
    """
    RUN_BUTTON_NOT_RUNNING_STYLE = """
            QToolButton {
                background-color: #353535;
                color: #00CC00;  /* Green text to match the play icon */
                border: 1px solid #00CC00;
                padding: 6px 12px;
                border-radius: 6px;
                font-family: Consolas;
                font-weight: 600;
                font-size: 18px;
                min-width: 20px;
                min-height: 20px;
                transition: all 0.2s;
            }
            QToolButton:hover {
                background-color: #00CC00;
                color: #1E1F22;
                border-color: #66FF66;
                box-shadow: 0 0 8px rgba(0, 204, 0, 0.5);
            }
            QToolButton:pressed {
                background-color: #009900;
                color: #1E1F22;
                border-color: #00CC00;
                box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.2);
            }
        """

class HighlightRules:
    """Static syntax highlighting rules with colorful formatting"""
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
        rules = []

        # Keywords
        keyword_format = cls._create_format(Config.KEYWORD_COLOR, bold=True)
        keywords = '|'.join(r'\b' + kw + r'\b' for kw in keyword.kwlist)
        rules.append((QRegExp(keywords), keyword_format))

        # Strings (single and double quotes)
        string_format = cls._create_format(Config.STRING_COLOR)
        rules.append((QRegExp(r'"[^"\\]*(\\.[^"\\]*)*"'), string_format))  # Double-quoted
        rules.append((QRegExp(r"'[^'\\]*(\\.[^'\\]*)*'"), string_format))  # Single-quoted

        # Comments
        comment_format = cls._create_format(Config.COMMENT_COLOR)
        rules.append((QRegExp(r'#[^\n]*'), comment_format))

        # Numbers (integers and floats)
        number_format = cls._create_format(Config.NUMBER_COLOR)
        rules.append((QRegExp(r'\b[0-9]+\.?[0-9]*\b'), number_format))

        # Operators
        operator_format = cls._create_format(Config.OPERATOR_COLOR)
        rules.append((QRegExp(r'[\+\-\*/=<>!&|%^]+'), operator_format))

        # Function names (after def keyword)
        function_format = cls._create_format(Config.FUNCTION_COLOR)
        rules.append((QRegExp(r'def\s+(\w+)\s*\('), function_format))

        return rules

class PythonHighlighter(QSyntaxHighlighter):
    """Efficient Python syntax highlighter with colorful formatting"""
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
        if not self._last_text.strip():
            self.errors.clear()
            return
        try:
            compile(self._last_text, '<document>', 'exec')
            self.errors.clear()  # Only clear if compilation succeeds
        except SyntaxError as e:
            if hasattr(e, 'lineno') and e.lineno is not None:
                self.errors[e.lineno - 1] = str(e)
        except IndentationError as e:
            if hasattr(e, 'lineno') and e.lineno is not None:
                self.errors[e.lineno - 1] = str(e)
        except Exception as e:
            # Catch other compilation-related errors
            self.errors[0] = f"General compilation error: {str(e)}"  # Default to line 0 if no line number

    def _check_warnings(self, text: str, line_number: int) -> None:
        self.warnings.pop(line_number, None)
        stripped = text.strip()
        if not stripped or stripped.startswith('#'):
            return
        if re.search(r'\bprint\s+[^(\n]', text) and not stripped.startswith('print('):
            self.warnings[line_number] = "Old-style print statement (use print())"
        elif re.search(r'^\s*from\s+\w+\s+import\s+\*', text):
            self.warnings[line_number] = "Wildcard import detected (avoid 'from ... import *')"
        elif re.search(r'^\s*import\s+\w+$', text) and not re.search(rf'{text.split()[-1]}\.', self._last_text):
            self.warnings[line_number] = "Potentially unused import"
        elif re.search(r'^(def|class|if|for|while)\s+\w+$', text):
            self.warnings[line_number] = "Missing colon after statement"

    def highlightBlock(self, text: str) -> None:
        # Apply syntax highlighting rules
        for pattern, fmt in self.rules:
            expression = QRegExp(pattern)
            index = expression.indexIn(text)
            while index >= 0:
                length = expression.matchedLength()
                # Special handling for function names after 'def'
                if pattern.pattern().startswith('def\\s+'):
                    func_name = expression.capturedTexts()[1]  # Capture group 1 is the function name
                    func_index = index + 4  # Skip 'def '
                    func_length = len(func_name)
                    self.setFormat(func_index, func_length, fmt)
                else:
                    self.setFormat(index, length, fmt)
                index = expression.indexIn(text, index + length)

        # Apply error/warning underlines (overlays on top of syntax coloring)
        line_number = self.currentBlock().blockNumber()
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
    """Optimized line number area with left-aligned numbers"""
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
                    QRect(5, top, self.width() - 5, self.editor.fontMetrics().height()),
                    Qt.AlignLeft, str(block_num + 1)
                )
                if block_num in self.editor.foldable_lines:
                    fold_type = self.editor.fold_types.get(block_num, "other")
                    base_color = {"def": "#52585C", "class": "#61686D"}.get(fold_type, "#71797E")
                    painter.setPen(
                        QColor(base_color if block_num != self.hovered_line else Config.SECONDARY_ACCENT))
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
    """Optimized code editor with folding and autocomplete"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ide_parent = parent if isinstance(parent, PythonIDE) else None  # Store PythonIDE reference
        self.line_number_area = LineNumberArea(self)
        self.highlighter = PythonHighlighter(self.document())
        self.foldable_lines: Set[int] = set()
        self.folded_blocks: Set[int] = set()
        self.fold_ranges: Dict[int, int] = {}
        self.fold_types: Dict[int, str] = {}
        self._setup_ui()
        self._setup_autocomplete()
        self._autocomplete_active = False

    def _setup_ui(self) -> None:
        font = QFont(Config.EDITOR_FONT, Config.FONT_SIZE)
        font.setFixedPitch(True)
        self.setFont(font)
        palette = QPalette()
        palette.setColor(QPalette.Base, QColor(Config.BACKGROUND_COLOR))
        palette.setColor(QPalette.Text, QColor(Config.TEXT_COLOR))
        self.setPalette(palette)
        self.setStyleSheet("""
            QPlainTextEdit {
                border: 1px solid #353535;
                border-radius: 6px;
                padding: 4px;
                selection-background-color: #FFC61A;
                selection-color: #1E1F22;
            }
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
            selection.format.setBackground(QColor("#2A2B2E"))
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
        self.completer.popup().setStyleSheet(f"""
            QListView {{ 
                background-color: #353535; 
                color: #D4D4D4; 
                border: 1px solid #FFC61A;
                border-radius: 4px;
                padding: 2px;
                font-family: Consolas;
            }}
            QListView::item {{ 
                padding: 4px 8px;
            }}
            QListView::item:hover {{ 
                background-color: #ECDC51; 
                color: #1E1F22; 
            }}
            QListView::item:selected {{
                background-color: #FFC61A;
                color: #1E1F22;
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
        if self.ide_parent:
            self.ide_parent.error_count_label.setText(f"{errors}")
            self.ide_parent.warning_count_label.setText(f"{warnings}")
            self.ide_parent.error_count_label.update()
            self.ide_parent.warning_count_label.update()
        else:
            print(f"Warning: No valid PythonIDE reference, cannot update error/warning counts")

    def paintEvent(self, event) -> None:
        super().paintEvent(event)

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
        palette.setColor(QPalette.Text, QColor(Config.TEXT_COLOR))
        self.setPalette(palette)
        self.setStyleSheet("""
            QTextEdit {
                border: 1px solid #353535;
                border-radius: 6px;
                padding: 4px;
                selection-background-color: #FFC61A;
                selection-color: #1E1F22;
            }
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

        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setStyleSheet("""
            QToolBar {
                background: #1E1F22;
                border-bottom: 1px solid #FFC61A;
                padding: 4px;
                spacing: 6px;
            }
        """)
        self.addToolBar(Qt.TopToolBarArea, toolbar)

        logo_label = QLabel()
        logo_label.setPixmap(QIcon("JaxPY.ico").pixmap(40, 40))
        logo_label.setStyleSheet("padding: 4px; border: none;")
        toolbar.addWidget(logo_label)

        # Toolbar buttons all as QToolButton with uniform style
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
                        background-color: #353535;
                        color: #D4D4D4;
                        border: 1px solid #FFC61A;
                        border-radius: 4px;
                        padding: 4px;
                    }}
                    QMenu::item {{
                        padding: 6px 12px;
                        background-color: transparent;
                    }}
                    QMenu::item:selected {{
                        background-color: #ECDC51;
                        color: #1E1F22;
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
        self.run_button.setStyleSheet(Config.RUN_BUTTON_NOT_RUNNING_STYLE)
        self.run_button.setToolTip("Run Code (F5)")
        toolbar.addWidget(self.run_button)

        self.stop_button = QToolButton()
        self.stop_button.setIcon(QIcon("images/stop.png"))
        self.stop_button.setIconSize(QSize(24, 24))
        self.stop_button.clicked.connect(self.stop_code)
        self.stop_button.setStyleSheet(Config.STOP_BUTTON_STYLE)
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
            background: #353535;
            padding: 4px;
            border-radius: 4px;
        """)
        self.error_icon_label.setToolTip("Errors in code")
        toggle_layout.addWidget(self.error_icon_label)

        self.error_count_label = QLabel("0")
        self.error_count_label.setStyleSheet(f"""
            color: {Config.ERROR_COLOR};
            background: #353535;
            padding: 4px 8px;
            font-family: Consolas;
        """)
        toggle_layout.addWidget(self.error_count_label)

        self.warning_icon_label = QLabel()
        self.warning_icon_label.setPixmap(QIcon("images/warning.png").pixmap(24, 24))
        self.warning_icon_label.setStyleSheet(f"""
            background: #353535;
            padding: 4px;
            border-radius: 4px;
        """)
        self.warning_icon_label.setToolTip("Warnings in code")
        toggle_layout.addWidget(self.warning_icon_label)

        self.warning_count_label = QLabel("0")
        self.warning_count_label.setStyleSheet(f"""
            color: {Config.WARNING_COLOR};
            background: #353535;
            padding: 4px 8px;
            font-family: Consolas;
        """)
        toggle_layout.addWidget(self.warning_count_label)

        toggle_container.setFixedHeight(55)
        toggle_container.setStyleSheet("""
            background: #353535;
            border-bottom: 1px solid #FFC61A;
            border-radius: 6px 6px 0 0;
        """)
        main_layout.addWidget(toggle_container)

        content_splitter = QSplitter(Qt.Horizontal)
        content_splitter.setStyleSheet("""
            QSplitter::handle {
                background: #353535;
                width: 4px;
            }
            QSplitter::handle:hover {
                background: #FFC61A;
            }
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
        editor_console_splitter.setStyleSheet("""
            QSplitter::handle {
                background: #353535;
                height: 4px;
            }
            QSplitter::handle:hover {
                background: #FFC61A;
            }
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
            color: {Config.ACCENT_COLOR};
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #353535, stop:1 #2A2B2E);
            padding: 6px 12px;
            border: 1px solid #FFC61A;
            border-radius: 6px;
            font-weight: 600;
            font-family: Consolas;
            font-size: 16px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
        """)
        terminal_label.setToolTip("Terminal Output")
        header.addWidget(terminal_label)

        header.addStretch()

        self.save_status_dot = QLabel("✗")
        self.save_status_dot.setStyleSheet(f"""
            color: #FF5555;
            background: #353535;
            padding: 4px 8px;
            border: 1px solid #353535;
            border-radius: 4px;
            font-size: 14px;
            font-family: Consolas;
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
                background: {Config.BACKGROUND_COLOR};
                color: {Config.TEXT_COLOR};
            }}
            QScrollBar:vertical, QScrollBar:horizontal {{
                border: none;
                background: #2A2B2E;
                width: 10px;
                height: 10px;
                margin: 0;
            }}
            QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
                background: #353535;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {{
                background: #FFC61A;
            }}
            QScrollBar::add-line, QScrollBar::sub-line {{
                background: none;
            }}
            QMessageBox, QDialog {{
                background: {Config.BACKGROUND_COLOR};
                color: {Config.TEXT_COLOR};
                border: 1px solid #353535;
                border-radius: 6px;
            }}
            QLineEdit {{
                background: #2A2B2E;
                color: {Config.TEXT_COLOR};
                border: 1px solid #353535;
                padding: 6px;
                border-radius: 4px;
            }}
            QLineEdit:focus {{
                border-color: #FFC61A;
                box-shadow: 0 0 4px rgba(255, 198, 26, 0.5);
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
            self.console.write("\n[Execution already in progress. Stop it first.]\n")
            return

        self.code_is_running = True
        self.run_button.setEnabled(False)
        self.run_button.setIcon(QIcon("images/run.png"))
        self.run_button.setStyleSheet(Config.RUN_BUTTON_RUNNING_STYLE)
        self.console.clear()

        self.interpreter = PythonInterpreter(self.code_editor.toPlainText(), self.console)
        self.interpreter.finished.connect(self._on_execution_finished)
        self.interpreter.error_detected.connect(self._handle_module_error)
        self.interpreter.start()

    def stop_code(self) -> None:
        if not self.code_is_running:
            self.console.write("\n[No execution to stop.]\n")
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
        self.run_button.setStyleSheet(Config.RUN_BUTTON_NOT_RUNNING_STYLE)
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
            background: #353535;
            padding: 4px 8px;
            border: 1px solid #FF5555;
            border-radius: 4px;
            box-shadow: 0 0 4px rgba(255, 85, 85, 0.3);
        """)
        self.save_status_dot.setToolTip("File has unsaved changes")

    def _mark_saved(self) -> None:
        self.save_status_dot.setPixmap(QIcon("images/saved.png").pixmap(16, 16))
        self.save_status_dot.setStyleSheet(f"""
            background: #353535;
            padding: 4px 8px;
            border: 1px solid {Config.ACCENT_COLOR};
            border-radius: 4px;
            box-shadow: 0 0 4px rgba(236, 220, 81, 0.3);
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
        dialog.setStyleSheet(f"background-color: {Config.BACKGROUND_COLOR};")
        layout = QVBoxLayout(dialog)
        layout.setSpacing(6)

        find_input = QLineEdit()
        replace_input = QLineEdit()
        find_input.setStyleSheet(f"""
            background-color: #2A2B2E;
            color: {Config.TEXT_COLOR};
            padding: 6px;
            border: 1px solid #353535;
            border-radius: 4px;
        """)
        replace_input.setStyleSheet(f"""
            background-color: #2A2B2E;
            color: {Config.TEXT_COLOR};
            padding: 6px;
            border: 1px solid #353535;
            border-radius: 4px;
        """)
        match_label = QLabel("Matches: 0")
        match_label.setStyleSheet(f"""
            color: {Config.ACCENT_COLOR};
            font-family: Consolas;
            padding: 4px;
        """)
        match_positions: List[int] = []
        self.current_match_index = -1

        layout.addWidget(QLabel("Find:", styleSheet=f"color: {Config.TEXT_COLOR}; font-family: Consolas;"))
        layout.addWidget(find_input)
        layout.addWidget(QLabel("Replace:", styleSheet=f"color: {Config.TEXT_COLOR}; font-family: Consolas;"))
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
            dialog.setStyleSheet(f"background-color: {Config.BACKGROUND_COLOR}; color: {Config.TEXT_COLOR};")
            layout = QVBoxLayout(dialog)
            layout.setSpacing(6)

            search_bar = QLineEdit()
            search_bar.setPlaceholderText("Search packages...")
            search_bar.setStyleSheet(f"""
                background-color: #2A2B2E;
                color: {Config.TEXT_COLOR};
                padding: 6px;
                border: 1px solid #353535;
                border-radius: 4px;
            """)
            layout.addWidget(search_bar)

            package_list = QListWidget()
            package_list.setStyleSheet(f"""
                QListWidget {{
                    background-color: #2A2B2E;
                    color: {Config.TEXT_COLOR};
                    border: 1px solid #353535;
                    border-radius: 4px;
                    padding: 4px;
                }}
                QListWidget::item {{
                    padding: 6px;
                }}
                QListWidget::item:hover {{
                    background-color: #353535;
                }}
                QListWidget::item:selected {{
                    background-color: #ECDC51;
                    color: #1E1F22;
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
    """Sidebar class managing toggle functionality with 1:2 split"""
    def __init__(self, parent: PythonIDE):
        self.parent = parent
        self.sidebar_visible = False
        self.toggle_button: Optional[QPushButton] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.toggle_button = QPushButton()
        self.toggle_button.setIcon(QIcon("images/bolt.png"))
        self.toggle_button.setFixedSize(45, 45)  # Increase from 35x35 to 45x45
        self.toggle_button.setIconSize(QSize(40, 40))  # Increase from 30x30 to 40x40
        self.toggle_button.setStyleSheet(Config.BOLT_BUTTON_STYLE)
        self.toggle_button.clicked.connect(self._toggle_sidebar)
        self.toggle_button.setToolTip("Show Bolt AI")

    def _toggle_sidebar(self) -> None:
        # Toggle visibility state
        self.sidebar_visible = not self.sidebar_visible

        # Get the splitter widget
        splitter = self.parent.centralWidget().layout().itemAt(1).widget()

        # Show/hide sidebar content
        self.parent.sidebar_content.setVisible(self.sidebar_visible)
        self.toggle_button.setToolTip("Hide Bolt AI" if self.sidebar_visible else "Show Bolt AI")

        # Set initial sizes when showing, but allow user resizing
        if self.sidebar_visible:
            total_width = splitter.width()
            sidebar_width = total_width // 3  # Initial width (1/3 of total)
            editor_width = (total_width * 2) // 3  # Initial editor width (2/3 of total)
            splitter.setSizes([sidebar_width, editor_width])
        else:
            splitter.setSizes([0, splitter.width()])

        # Optional: Remove or adjust animation if you want to keep it
        # Without animation, the splitter will handle resizing naturally
        # If you want to keep animation:
        animation = QPropertyAnimation(self.parent.sidebar_content, b"minimumWidth")
        animation.setDuration(300)
        animation.setStartValue(0 if self.sidebar_visible else 250)
        animation.setEndValue(250 if self.sidebar_visible else 0)
        animation.start()

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