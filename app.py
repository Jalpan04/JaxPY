import builtins
import io
import keyword
import re
import subprocess
import sys
import traceback

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QRegExp, QSize, QTimer, QRect
from PyQt5.QtGui import (QColor, QTextCharFormat, QFont, QPalette, QSyntaxHighlighter,
                         QTextCursor, QIcon, QPainter, QTextFormat)
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout,
                             QSplitter, QTextEdit, QPlainTextEdit, QFileDialog, QDialog, QVBoxLayout, QLineEdit,
                             QListWidget, QListWidgetItem, QPushButton, QLabel
, QMessageBox, QInputDialog)


class PythonHighlighter(QSyntaxHighlighter):
    """
    Syntax highlighter for Python code with improved comment handling.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlighting_rules = []

        # Comment format - must be applied first to take precedence
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6A9955"))
        pattern = r'#[^\n]*'
        self.comment_rule = (QRegExp(pattern), comment_format)

        # Keyword format
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#569CD6"))
        keyword_format.setFontWeight(QFont.Bold)

        for word in keyword.kwlist:
            pattern = r'\b' + word + r'\b'
            self.highlighting_rules.append((QRegExp(pattern), keyword_format))

        # Function format
        function_format = QTextCharFormat()
        function_format.setForeground(QColor("#DCDCAA"))
        pattern = r'\b[A-Za-z0-9_]+(?=\()'
        self.highlighting_rules.append((QRegExp(pattern), function_format))

        # String format (single quotes)
        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#CE9178"))
        pattern = r"'[^'\\]*(\\.[^'\\]*)*'"
        self.highlighting_rules.append((QRegExp(pattern), string_format))

        # String format (double quotes)
        pattern = r'"[^"\\]*(\\.[^"\\]*)*"'
        self.highlighting_rules.append((QRegExp(pattern), string_format))

        # Class format
        class_format = QTextCharFormat()
        class_format.setForeground(QColor("#4EC9B0"))
        class_format.setFontWeight(QFont.Bold)
        pattern = r'\bclass\b\s*(\w+)'
        self.highlighting_rules.append((QRegExp(pattern), class_format))

        # Builtin functions
        builtin_format = QTextCharFormat()
        builtin_format.setForeground(QColor("#569CD6"))
        for builtin in dir(builtins):
            if not builtin.startswith('_'):
                pattern = r'\b' + builtin + r'\b'
                self.highlighting_rules.append((QRegExp(pattern), builtin_format))

    def highlightBlock(self, text):
        # First check for comments and highlight the entire line if needed
        expression = QRegExp(self.comment_rule[0])
        index = expression.indexIn(text)
        if index >= 0:
            length = len(text) - index
            self.setFormat(index, length, self.comment_rule[1])
            return  # Skip other rules for comment lines

        # Apply other rules only if not a comment line
        for pattern, format in self.highlighting_rules:
            expression = QRegExp(pattern)
            index = expression.indexIn(text)
            while index >= 0:
                length = expression.matchedLength()
                self.setFormat(index, length, format)
                index = expression.indexIn(text, index + length)


class CodeEditor(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.line_number_area = LineNumberArea(self)
        self.setup_editor()
        self.highlighter = PythonHighlighter(self.document())

        # Connect signals
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)

        self.foldable_lines = set()
        self.folded_blocks = set()
        self.fold_ranges = {}  # Map: start_line -> end_line
        self.fold_types = {}  # Map: start_line -> fold_type (e.g., "def", "class")

        self.line_number_area.setMouseTracking(True)
        self.setMouseTracking(True)
        self.textChanged.connect(self.detect_foldable_lines)
        self.hovered_line = -1

        # Initialize the foldable lines
        self.detect_foldable_lines()
        self.update_line_number_area_width()

    def setup_editor(self):
        font = QFont("Consolas", 10)
        font.setFixedPitch(True)
        self.setFont(font)
        self.setTabStopWidth(4 * self.fontMetrics().width(' '))

        palette = QPalette()
        palette.setColor(QPalette.Base, QColor("#1E1E1E"))
        palette.setColor(QPalette.Text, QColor("#D4D4D4"))
        self.setPalette(palette)

    def line_number_area_width(self):
        digits = len(str(self.blockCount()))
        # Increased width for better visibility
        extra_width = 20
        padding = 20
        return extra_width + self.fontMetrics().width('9') * digits + padding

    def update_line_number_area_width(self):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        rect = self.contentsRect()
        self.line_number_area.setGeometry(rect.left(), rect.top(), self.line_number_area_width(), rect.height())
        self.update_line_number_area(self.viewport().rect(), 0)

    def line_number_area_paint_event(self, event):
        painter = QPainter(self.line_number_area)

        # Background color for line numbers
        painter.fillRect(event.rect(), QColor("#262626"))
        painter.setPen(QColor("#8A8A8A"))  # Set text color for line numbers

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()

        # Increased right padding
        padding_right = 15

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                if block_number in self.foldable_lines:
                    # Get the fold type
                    fold_type = self.fold_types.get(block_number, "other")

                    # Set color based on fold type
                    if fold_type == "def":
                        # Darker color for function definitions
                        base_color = QColor("#52585C")  # Darker blue for def
                    elif fold_type == "class":
                        base_color = QColor("#61686D")  # Brown-orange for class
                    else:
                        base_color = QColor("#71797E")  # Gray for other folds

                    # Use the base color for normal state
                    painter.setPen(base_color)

                    # Draw the fold indicator (triangle)
                    arrow = "▼" if block_number not in self.folded_blocks else "▶"

                    # Highlight fold indicator on hover with a lighter version of the same color
                    if block_number == self.hovered_line:
                        # Create a lighter version of the same color for hover state
                        highlight_color = QColor(
                            min(base_color.red() + 40, 255),
                            min(base_color.green() + 40, 255),
                            min(base_color.blue() + 40, 255)
                        )
                        painter.setPen(highlight_color)

                    # Position the fold indicator with more space
                    fold_rect = QRect(0, int(top), self.line_number_area.width() - 5,
                                      self.fontMetrics().height())
                    painter.drawText(fold_rect, Qt.AlignRight, arrow)

                # Draw line number
                painter.setPen(QColor("#8A8A8A"))  # Reset pen color for line numbers
                number = str(block_number + 1)

                # Create a separate rect for line numbers with more left spacing
                number_rect = QRect(5, int(top), self.line_number_area.width() - padding_right - 15,
                                    self.fontMetrics().height())
                painter.drawText(number_rect, Qt.AlignRight, number)

            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1

    def update_line_number_area(self, rect, dy):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())

        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width()

    def highlight_current_line(self):
        extra_selections = []

        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(QColor("#2A2D2E"))
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)

        self.setExtraSelections(extra_selections)

    def detect_foldable_lines(self):
        """Detect lines that can be folded (function and class definitions)"""
        self.foldable_lines.clear()
        self.fold_ranges.clear()
        self.fold_types.clear()

        # Store current folded state to restore after detection
        old_folded_blocks = self.folded_blocks.copy()
        self.folded_blocks.clear()

        # Create a stack to track nested code blocks
        indent_stack = []

        block = self.document().firstBlock()
        while block.isValid():
            text = block.text()
            stripped = text.strip()
            current_line = block.blockNumber()

            # Only process non-empty lines
            if stripped:
                current_indent = len(text) - len(text.lstrip())

                # Pop any indent levels that are greater than or equal to current
                while indent_stack and indent_stack[-1][1] >= current_indent:
                    start_line, _, block_type = indent_stack.pop()

                    # If we've gone back to a less indented level and the block
                    # had content that could be folded, mark it as foldable
                    if current_line - start_line > 1:  # At least one line to fold
                        self.foldable_lines.add(start_line)
                        self.fold_ranges[start_line] = current_line - 1
                        self.fold_types[start_line] = block_type

                # Add potential fold start points with their type
                if stripped.startswith("def "):
                    indent_stack.append((current_line, current_indent, "def"))
                elif stripped.startswith("class "):
                    indent_stack.append((current_line, current_indent, "class"))
                elif stripped.startswith(("if ", "for ", "while ", "try:", "with ")):
                    indent_stack.append((current_line, current_indent, "other"))

            block = block.next()

        # Handle any remaining blocks in the stack (these go to the end of the document)
        end_line = self.document().blockCount() - 1
        for start_line, _, block_type in indent_stack:
            if end_line - start_line > 1:  # At least one line to fold
                self.foldable_lines.add(start_line)
                self.fold_ranges[start_line] = end_line
                self.fold_types[start_line] = block_type

        # Restore fold state for lines that were previously folded and are still foldable
        for line in old_folded_blocks:
            if line in self.foldable_lines:
                self.toggle_fold(line)  # This will add it back to folded_blocks

    def toggle_fold(self, line_number):
        """Toggle folding for the specified line number"""
        if line_number not in self.fold_ranges:
            return

        start_line = line_number
        end_line = self.fold_ranges[start_line]

        # Check if we're folding or unfolding
        is_folding = start_line not in self.folded_blocks

        # Update the folded blocks set
        if is_folding:
            self.folded_blocks.add(start_line)
        else:
            self.folded_blocks.discard(start_line)

        # We need to use document layout for proper folding
        document = self.document()

        # Disable screen updates and document change notifications temporarily
        self.setUpdatesEnabled(False)
        document.blockSignals(True)

        # Process blocks in the fold range
        block = document.findBlockByNumber(start_line + 1)
        while block.isValid() and block.blockNumber() <= end_line:
            block.setVisible(not is_folding)
            block = block.next()

        # Re-enable signals and updates
        document.blockSignals(False)
        self.setUpdatesEnabled(True)

        # Update the document layout
        document.markContentsDirty(document.findBlockByNumber(start_line).position(),
                                   document.findBlockByNumber(end_line).position())
        self.viewport().update()

        # Ensure the cursor is visible (in case it was in a folded section)
        cursor_block = self.textCursor().block().blockNumber()
        if not document.findBlockByNumber(cursor_block).isVisible():
            cursor = self.textCursor()
            cursor.setPosition(document.findBlockByNumber(start_line).position())
            self.setTextCursor(cursor)


class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.code_editor = editor

    def sizeHint(self):
        return QSize(self.code_editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.code_editor.line_number_area_paint_event(event)

    def mouseMoveEvent(self, event):
        """Track mouse movement to highlight foldable lines"""
        editor = self.code_editor
        block = editor.firstVisibleBlock()
        top = editor.blockBoundingGeometry(block).translated(editor.contentOffset()).top()
        line_height = editor.fontMetrics().height()

        # Calculate which line the mouse is hovering over
        y_pos = event.y()
        line = block.blockNumber()

        while block.isValid():
            block_top = editor.blockBoundingGeometry(block).translated(editor.contentOffset()).top()
            if y_pos < block_top + editor.blockBoundingRect(block).height() and block.isVisible():
                line = block.blockNumber()
                break
            block = block.next()
            if not block.isValid():
                break

        # Update the hovered line and cursor
        if line != editor.hovered_line:
            editor.hovered_line = line
            self.update()

        # Change cursor if hovering over a foldable line
        if line in editor.foldable_lines:
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

    def leaveEvent(self, event):
        """Handle mouse leaving the line number area"""
        self.code_editor.hovered_line = -1
        self.setCursor(Qt.ArrowCursor)
        self.update()

    def mousePressEvent(self, event):
        """Handle clicking on fold indicators"""
        editor = self.code_editor
        block = editor.firstVisibleBlock()
        top = editor.blockBoundingGeometry(block).translated(editor.contentOffset()).top()

        # Calculate which line was clicked
        y_pos = event.y()
        line = block.blockNumber()

        while block.isValid():
            block_top = editor.blockBoundingGeometry(block).translated(editor.contentOffset()).top()
            if y_pos < block_top + editor.blockBoundingRect(block).height() and block.isVisible():
                line = block.blockNumber()
                break
            block = block.next()
            if not block.isValid():
                break

        # Toggle folding if a foldable line was clicked
        if line in editor.foldable_lines:
            editor.toggle_fold(line)


class ConsoleWidget(QTextEdit):
    """
    Custom console widget that emulates VS Code's integrated terminal behavior.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_console()
        self.input_buffer = ""
        self.reading_input = False
        self.input_pos = 0
        self.prompt = ">>> "

    def setup_console(self):
        # Set up appearance to match VS Code's terminal
        font = QFont("Consolas", 10)
        font.setFixedPitch(True)
        self.setFont(font)

        # Set a dark background and text color
        palette = QPalette()
        palette.setColor(QPalette.Base, QColor("#1E1E1E"))
        palette.setColor(QPalette.Text, QColor("#CCCCCC"))
        self.setPalette(palette)

        # Make read-only until input is requested
        self.setReadOnly(True)

    def write(self, text):
        """
        Write text to the console. This method is used to redirect stdout.
        """
        self.moveCursor(QTextCursor.End)
        self.insertPlainText(text)
        self.moveCursor(QTextCursor.End)
        QApplication.processEvents()  # Update the UI immediately

    def start_input(self):
        """
        Prepare console for receiving input.
        """
        self.reading_input = True
        self.setReadOnly(False)
        self.moveCursor(QTextCursor.End)
        self.input_pos = self.textCursor().position()

    def readline(self):
        """
        Read a line of input from the console. This method is called by input().
        """
        self.start_input()

        # Wait for input to complete
        while self.reading_input:
            QApplication.processEvents()

        # Return the input plus a newline
        return self.input_buffer + '\n'

    def keyPressEvent(self, event):
        """
        Handle key press events in the console.
        """
        if not self.reading_input:
            # If not reading input, only allow shortcuts
            if event.key() == Qt.Key_C and event.modifiers() & Qt.ControlModifier:
                QApplication.clipboard().setText(self.textCursor().selectedText())
            return

        cursor = self.textCursor()

        # Handle backspace to prevent deleting past input position
        if event.key() == Qt.Key_Backspace:
            if cursor.position() <= self.input_pos:
                return

        # Handle Enter key to finish input
        elif event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            # Extract the input text
            cursor.setPosition(self.input_pos, QTextCursor.MoveAnchor)
            cursor.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
            self.input_buffer = cursor.selectedText()

            # Add a newline to the display
            self.moveCursor(QTextCursor.End)
            self.insertPlainText('\n')

            # Finish the input operation
            self.reading_input = False
            self.setReadOnly(True)
            return

        # Handle Left key to prevent moving cursor before input position
        elif event.key() == Qt.Key_Left:
            if cursor.position() <= self.input_pos:
                return

        # Handle Home key to move to input start position instead of line start
        elif event.key() == Qt.Key_Home:
            cursor.setPosition(self.input_pos)
            self.setTextCursor(cursor)
            return

        # For all other keys, proceed with default behavior
        super().keyPressEvent(event)


class PythonInterpreter(QThread):
    """
    Thread for running Python code without freezing the GUI.
    """
    output_ready = pyqtSignal(str)
    error_detected = pyqtSignal(str)  # New signal for module not found errors
    finished = pyqtSignal()

    def __init__(self, code, console):
        super().__init__()
        self.code = code
        self.console = console

    def run(self):
        # Redirect stdout and stderr to our console
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        original_stdin = sys.stdin

        captured_output = io.StringIO()
        sys.stdout = self.console
        sys.stderr = captured_output
        sys.stdin = self.console

        try:
            # Create a fresh namespace for executing the code
            namespace = {'__name__': '__main__'}

            # Execute the code
            exec(compile(self.code, '<ide>', 'exec'), namespace)

        except ModuleNotFoundError as e:
            # Capture the module name from the error
            module_name = str(e).split("'")[1] if "'" in str(e) else None
            if module_name:
                self.error_detected.emit(module_name)

            # Print the traceback for the error
            self.console.write(f"{str(e)}\n")
            traceback.print_exc(file=self.console)

        except Exception as e:
            # Print the traceback for any other exceptions
            traceback.print_exc(file=self.console)

        finally:
            # Get any error output
            error_output = captured_output.getvalue()
            if error_output:
                self.console.write(error_output)

            # Restore original stdout, stderr, and stdin
            sys.stdout = original_stdout
            sys.stderr = original_stderr
            sys.stdin = original_stdin

            self.finished.emit()


class PackageInstaller(QThread):
    """
    Thread for installing Python packages using pip without freezing the GUI.
    """
    output_ready = pyqtSignal(str)
    finished = pyqtSignal(bool)  # True if successful, False otherwise

    def __init__(self, package_name, console):
        super().__init__()
        self.package_name = package_name
        self.console = console
        self.success = False

    def run(self):
        try:
            # Notify that installation is starting
            self.output_ready.emit(f"Installing package: {self.package_name}...\n")

            # Run pip install as a subprocess
            process = subprocess.Popen(
                [sys.executable, "-m", "pip", "install", self.package_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # Get the output
            stdout, stderr = process.communicate()

            # Check if installation was successful
            if process.returncode == 0:
                self.output_ready.emit(f"Successfully installed {self.package_name}.\n{stdout}\n")
                self.success = True
            else:
                self.output_ready.emit(f"Failed to install {self.package_name}:\n{stderr}\n")
                self.success = False

        except Exception as e:
            self.output_ready.emit(f"Error during installation: {str(e)}\n")
            self.success = False

        finally:
            self.finished.emit(self.success)


class PythonIDE(QMainWindow):
    """
    Main IDE window with code editor and integrated console.
    """

    def __init__(self):
        super().__init__()
        self.init_ui()
        self.code_is_running = False  # Track if code is currently running


    def init_ui(self):
        # Set up the main window
        self.setWindowTitle("JaxPY")
        self.setWindowIcon(QIcon("JaxPY.ico"))  # Set the window icon

        self.setGeometry(100, 100, 1000, 800)

        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Create a splitter for editor and console
        splitter = QSplitter(Qt.Vertical)

        # Create code editor
        self.code_editor = CodeEditor()
        self.code_editor.textChanged.connect(self.mark_unsaved)

        splitter.addWidget(self.code_editor)

        # Create console widget
        console_container = QWidget()
        console_layout = QVBoxLayout(console_container)
        console_layout.setContentsMargins(0, 0, 0, 0)

        console_header = QHBoxLayout()
        console_label = QLabel("Terminal")
        console_label.setStyleSheet("color: #CCCCCC; background-color: #2D2D2D; padding: 3px;")
        # Save Status Dot
        self.save_status_dot = QLabel("●")  # Small dot
        self.save_status_dot.setStyleSheet(
            "color: red; background-color: #2D2D2D; padding: 3px;")  # Default red (unsaved)

        console_header.addWidget(console_label)
        console_header.addStretch()
        console_layout.addLayout(console_header)
        console_header.addWidget(self.save_status_dot)  # Add dot to terminal header

        self.current_file = None  # Track the currently opened file

        # Auto-save timer setup
        self.auto_save_timer = QTimer(self)
        self.auto_save_timer.timeout.connect(self.auto_save)
        self.auto_save_timer.start(30000)  # Auto-save every 30 seconds


        self.console = ConsoleWidget()
        console_layout.addWidget(self.console)

        splitter.addWidget(console_container)

        # Set initial sizes for splitter
        splitter.setSizes([600, 200])

        # Add splitter to main layout
        main_layout.addWidget(splitter)

        from PyQt5.QtWidgets import QAction, QToolBar, QToolButton, QMenu
        from PyQt5.QtGui import QKeySequence

        # Create toolbar
        toolbar = QToolBar()
        self.addToolBar(toolbar)

        # Define button style
        button_style = """
            QToolButton, QAction {
                background-color: #1e1e1e; 
                color: white;
                padding: 5px 10px;
                border-radius: 5px;
            }
            QToolButton:hover, QAction:hover {
                background-color: #3A3A3A;
            }
        """

        # Function to create styled action
        def create_action(name, shortcut=None, callback=None):
            action = QAction(name, self)
            if shortcut:
                action.setShortcut(QKeySequence(shortcut))
            if callback:
                action.triggered.connect(callback)
            return action

        # Add actions to toolbar with the same style
        self.run_button = QToolButton(self)
        self.run_button.setText("RUN")
        self.run_button.setShortcut("F5")
        self.run_button.clicked.connect(self.run_code)
        self.run_button.setStyleSheet("background-color: green; color: white; padding: 5px 10px; border-radius: 5px;")


        open_action = create_action("Open", None, self.open_file)
        save_action = create_action("Save", None, self.save_file)
        find_replace_action = create_action("Find / Replace", "Ctrl+F", self.find_and_replace)
        new_window_action = create_action("New Window", None, self.new_window)

        # Add actions to toolbar
        toolbar.addWidget(self.run_button)


        # Create File button (for dropdown menu)
        file_button = QToolButton(self)
        file_button.setText("File")
        file_button.setPopupMode(QToolButton.InstantPopup)  # Open menu on button click
        file_button.setStyleSheet(button_style)

        # Create dropdown menu
        file_menu = QMenu(self)
        file_button.setMenu(file_menu)  # Attach menu to the button

        # Add actions to the file menu
        new_action = create_action("New", None, self.new_file)
        new_window_action = create_action("New Window", None, self.new_window)

        # Add menu actions
        file_menu.addAction(new_action)
        file_menu.addAction(new_window_action)

        # Add the button to the toolbar
        toolbar.addWidget(file_button)

        toolbar.addAction(open_action)
        toolbar.addAction(save_action)
        toolbar.addAction(find_replace_action)


        # Create Packages button
        packages_button = QToolButton(self)
        packages_button.setText("Packages")
        packages_button.setPopupMode(QToolButton.InstantPopup)  # Open menu on button click
        packages_button.setStyleSheet(button_style)

        # Create dropdown menu
        packages_menu = QMenu(self)
        packages_button.setMenu(packages_menu)  # Attach menu to the button

        # Install Packages Action
        install_action = create_action("Install Packages", None, self.show_package_installer)
        installed_action = create_action("Installed Packages", None, self.show_installed_packages)

        # Add menu actions
        packages_menu.addAction(install_action)
        packages_menu.addAction(installed_action)

        # Add the button to the toolbar
        toolbar.addWidget(packages_button)



        # Apply the style to the toolbar actions
        toolbar.setStyleSheet(button_style)

        # Set default content
        self.code_editor.setPlainText(
            '# Welcome to Python IDE\n\nprint("Hello, World!")\nname = input("Enter your name: ")\nprint(f"Hello, {name}!")')

        # Set the style for the whole application
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #1E1E1E;
                color: #CCCCCC;
            }
            QToolBar {
                background-color: #2D2D2D;
                border: none;
            }
            QToolBar QAction {
                color: #CCCCCC;
            }
            QSplitter::handle {
                background-color: #2D2D2D;
            }
            QPushButton {
                background-color: #0E639C;
                color: white;
                border: none;
                padding: 5px 10px;
            }
            QPushButton:hover {
                background-color: #1177BB;
            }
        """)

        self.show()

    def run_code(self):
        """
        Run the code from the editor in the console, stopping previous if running.
        """
        if self.code_is_running:
            # Stop previous execution
            self.console.write("\n[Stopping previous execution...]\n")
            self.interpreter.terminate()
            self.interpreter.wait()
            self.code_is_running = False
            self.set_run_button_color("green")
            self.run_code()  # Restart
            return

        self.code_is_running = True
        self.set_run_button_color("red")
        self.console.clear()

        code = self.code_editor.toPlainText()
        self.interpreter = PythonInterpreter(code, self.console)
        self.interpreter.finished.connect(self.on_execution_finished)
        self.interpreter.error_detected.connect(self.handle_module_error)
        self.interpreter.start()

    def set_run_button_color(self, color):
        if color == "green":
            self.run_button.setStyleSheet(
                "background-color: green; color: white; padding: 5px 10px; border-radius: 5px;")
        elif color == "red":
            self.run_button.setStyleSheet("background-color: red; color: white; padding: 5px 10px; border-radius: 5px;")

    def on_execution_finished(self):
        """
        Called when code execution is complete.
        """
        self.console.write("\n>>> ")
        self.set_run_button_color("green")
        self.code_is_running = False

    def new_file(self):
        """
        Create a new file.
        """
        self.code_editor.clear()

    def open_file(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Open Python File", "", "Python Files (*.py);;All Files (*)")

        if filename:
            try:
                with open(filename, 'r', encoding="utf-8") as file:
                    self.code_editor.setPlainText(file.read())
                self.current_file = filename  # Track the opened file
            except Exception as e:
                self.console.write(f"Error opening file: {str(e)}\n")

    def save_file(self):
        if not self.current_file:
            self.current_file, _ = QFileDialog.getSaveFileName(self, "Save Python File", "",
                                                               "Python Files (*.py);;All Files (*)")

        if self.current_file:
            try:
                with open(self.current_file, 'w', encoding="utf-8") as file:
                    file.write(self.code_editor.toPlainText())
                self.console.write(f"\n[Saved] {self.current_file}\n")
            except Exception as e:
                self.console.write(f"\n[Save Failed] {str(e)}\n")

    def mark_unsaved(self):
        """
        Marks the file as unsaved (red dot) when text is changed.
        """
        self.save_status_dot.setStyleSheet("color: red; background-color: #2D2D2D; padding: 3px;")

    def auto_save(self):
        """
        Automatically saves the file every 30 seconds.
        If a file is opened, it saves to that file.
        Otherwise, it saves to a temporary file.
        """
        save_path = self.current_file if self.current_file else "autosave.py"

        try:
            with open(save_path, "w", encoding="utf-8") as file:
                file.write(self.code_editor.toPlainText())

            # Update the save status to green (saved)
            self.save_status_dot.setStyleSheet("color: green; background-color: #2D2D2D; padding: 3px;")

        except Exception as e:
            self.console.write(f"\n[Auto-Save Failed] {str(e)}\n")

    def new_window(self):
        """
        Opens a new instance of the IDE in a separate window.
        Ensures proper reference handling and error management.
        """
        try:
            new_ide = PythonIDE()
            new_ide.show()

            # Store reference to prevent garbage collection
            if not hasattr(self, "child_windows"):
                self.child_windows = []
            self.child_windows.append(new_ide)
        except Exception as e:
            print(f"Failed to open a new window: {e}")


    def find_and_replace(self):
        """
        Opens a Find and Replace dialog with match count and navigation buttons beside it.
        """
        self.match_positions = []
        self.current_match_index = -1  # No match initially

        self.find_replace_dialog = QDialog(self)  # Store dialog reference
        self.find_replace_dialog.setWindowTitle("Find and Replace")
        self.find_replace_dialog.setGeometry(300, 300, 350, 150)
        layout = QVBoxLayout(self.find_replace_dialog)

        # Find input layout
        find_label = QLabel("Find:")
        self.find_input = QLineEdit()

        # Replace input layout
        replace_label = QLabel("Replace:")
        self.replace_input = QLineEdit()

        # Match count + navigation layout
        match_layout = QHBoxLayout()
        self.match_label = QLabel("Matches: 0")  # Label to show match count

        prev_button = QPushButton("◀")  # Previous match button
        next_button = QPushButton("▶")  # Next match button

        prev_button.setFixedSize(30, 30)
        next_button.setFixedSize(30, 30)

        match_layout.addWidget(self.match_label)
        match_layout.addWidget(prev_button)
        match_layout.addWidget(next_button)

        # Buttons layout
        find_button = QPushButton("Find")
        replace_button = QPushButton("Replace")
        replace_all_button = QPushButton("Replace All")

        find_button.clicked.connect(self.find_text)
        next_button.clicked.connect(self.next_match)
        prev_button.clicked.connect(self.prev_match)
        replace_button.clicked.connect(self.replace_text)
        replace_all_button.clicked.connect(self.replace_all_text)

        # Add widgets to layout
        layout.addWidget(find_label)
        layout.addWidget(self.find_input)
        layout.addWidget(replace_label)
        layout.addWidget(self.replace_input)
        layout.addLayout(match_layout)  # Matches count + buttons
        layout.addWidget(find_button)
        layout.addWidget(replace_button)
        layout.addWidget(replace_all_button)

        self.find_replace_dialog.setLayout(layout)
        self.find_replace_dialog.exec_()  # Show dialog

    def find_text(self):
        """
        Finds all occurrences of the search term, highlights the first match, and auto-closes if no matches are found.
        """
        search_text = self.find_input.text().strip()
        if not search_text:
            return

        document = self.code_editor.document()
        cursor = QTextCursor(document)

        self.match_positions = []
        self.current_match_index = -1

        regex = QRegExp(r'\b' + re.escape(search_text) + r'\b')

        # Find all matches
        while not cursor.isNull() and not cursor.atEnd():
            cursor = document.find(regex, cursor)
            if cursor.isNull():
                break
            self.match_positions.append(cursor.position())

        # Update match count
        match_count = len(self.match_positions)
        self.match_label.setText(f"Matches: {match_count}")

        if match_count > 0:
            self.current_match_index = 0
            self.highlight_match()
        else:
            # Close the Find & Replace window if no matches are found
            if hasattr(self, "find_replace_dialog") and self.find_replace_dialog.isVisible():
                self.find_replace_dialog.accept()  # Close the dialog

    def highlight_match(self):
        """
        Highlights the current match.
        """
        if self.current_match_index == -1 or not self.match_positions:
            return

        cursor = self.code_editor.textCursor()
        cursor.setPosition(self.match_positions[self.current_match_index] - len(self.find_input.text()))
        cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, len(self.find_input.text()))
        self.code_editor.setTextCursor(cursor)

        self.match_label.setText(f"Matches: {len(self.match_positions)} (Current: {self.current_match_index + 1})")

    def next_match(self):
        """
        Moves to the next match.
        """
        if not self.match_positions:
            return

        self.current_match_index = (self.current_match_index + 1) % len(self.match_positions)
        self.highlight_match()

    def prev_match(self):
        """
        Moves to the previous match.
        """
        if not self.match_positions:
            return

        self.current_match_index = (self.current_match_index - 1) % len(self.match_positions)
        self.highlight_match()

    def replace_text(self):
        """
        Replaces the currently highlighted match.
        """
        if self.current_match_index == -1 or not self.match_positions:
            return

        search_text = self.find_input.text()
        replace_text = self.replace_input.text()

        cursor = self.code_editor.textCursor()
        if cursor.hasSelection() and cursor.selectedText() == search_text:
            cursor.insertText(replace_text)
            self.match_positions[self.current_match_index] += len(replace_text) - len(search_text)

        self.find_text()  # Refresh matches after replacing

    def replace_all_text(self):
        """
        Replaces all occurrences of the searched text in the document and closes the Find & Replace window.
        """
        search_text = self.find_input.text().strip()
        replace_text = self.replace_input.text().strip()

        if not search_text:
            return

        document = self.code_editor.document()
        cursor = QTextCursor(document)

        cursor.beginEditBlock()

        pattern = r'\b' + re.escape(search_text) + r'\b'  # Match whole words
        regex = QRegExp(pattern)

        count = 0
        cursor.movePosition(QTextCursor.Start)  # Start from the beginning of the document

        while True:
            cursor = document.find(regex, cursor)  # Find next occurrence
            if cursor.isNull():
                break  # Stop if no more matches
            cursor.insertText(replace_text)  # Replace text
            count += 1

        cursor.endEditBlock()

        # Close the Find & Replace window after replacing
        if hasattr(self, "find_replace_dialog") and self.find_replace_dialog.isVisible():
            self.find_replace_dialog.accept()  # Closes the dialog

    def handle_module_error(self, module_name):
        """
        Handle a ModuleNotFoundError by offering to install the missing package.
        """
        response = QMessageBox.question(
            self,
            "Missing Package",
            f"The module '{module_name}' was not found. Would you like to install it now?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )

        if response == QMessageBox.Yes:
            self.install_package(module_name)

    def show_package_installer(self):
        """
        Show dialog to install a Python package.
        """
        package_name, ok = QInputDialog.getText(
            self,
            "Install Package",
            "Enter the name of the package to install:"
        )

        if ok and package_name:
            self.install_package(package_name)

    def show_installed_packages(self):
        """
        Display installed packages in a square dialog with scrolling and search functionality.
        """
        try:
            # Get installed packages using pip
            result = subprocess.run([sys.executable, "-m", "pip", "list"], capture_output=True, text=True)
            installed_packages = result.stdout.split("\n")[2:]  # Skip headers

            # Create dialog window
            dialog = QDialog(self)
            dialog.setWindowTitle("Installed Packages")
            dialog.setGeometry(200, 200, 400, 400)  # Square size
            dialog.setStyleSheet("background-color: #1E1E1E; color: #CCCCCC;")

            layout = QVBoxLayout(dialog)

            # Search Bar
            search_bar = QLineEdit()
            search_bar.setPlaceholderText("Search for a package...")
            search_bar.setStyleSheet("background-color: #2D2D2D; color: white; padding: 5px;")
            layout.addWidget(search_bar)

            # List Widget for Installed Packages
            package_list = QListWidget()
            package_list.setStyleSheet("background-color: #262626; color: white; border: none;")
            layout.addWidget(package_list)

            # Populate List
            for package in installed_packages:
                if package.strip():
                    QListWidgetItem(package.strip(), package_list)

            # Search Functionality
            def filter_packages():
                search_text = search_bar.text().lower()
                for i in range(package_list.count()):
                    item = package_list.item(i)
                    item.setHidden(search_text not in item.text().lower())

            search_bar.textChanged.connect(filter_packages)

            # Close Button
            close_button = QPushButton("Close")
            close_button.setStyleSheet("background-color: #0E639C; color: white; padding: 5px; border-radius: 5px;")
            close_button.clicked.connect(dialog.accept)
            layout.addWidget(close_button)

            dialog.exec_()

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to fetch installed packages:\n{str(e)}")

    def install_package(self, package_name):
        """
        Install a Python package using pip.
        """
        self.console.write(f"\nPreparing to install {package_name}...\n")

        # Create and start the package installer thread
        self.installer = PackageInstaller(package_name, self.console)
        self.installer.output_ready.connect(self.console.write)
        self.installer.finished.connect(lambda success: self.on_installation_finished(success, package_name))
        self.installer.start()

    def on_installation_finished(self, success, package_name):
        """
        Called when package installation is complete.
        """
        if success:
            QMessageBox.information(
                self,
                "Installation Complete",
                f"Package '{package_name}' was successfully installed."
            )
            self.console.write("\n>>> ")
        else:
            QMessageBox.warning(
                self,
                "Installation Failed",
                f"Failed to install package '{package_name}'. See console for details."
            )
            self.console.write("\n>>> ")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ide = PythonIDE()
    sys.exit(app.exec_())