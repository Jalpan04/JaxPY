# JaxPY - Python IDE for Innovators

![GitHub top language](https://img.shields.io/github/languages/top/Jalpan04/JaxPY) ![GitHub repo size](https://img.shields.io/github/repo-size/Jalpan04/JaxPY) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

JaxPY is a modern, lightweight Python Integrated Development Environment (IDE) built using Python and PyQt5. Designed to streamline coding workflows, it combines essential editing capabilities, a built-in terminal, package management, and sidecar AI assistance to deliver a premium developer experience.

## Features

- **Advanced Syntax Highlighting**: Custom, fast syntax highlighting highlighting keywords, strings, comments, numbers, operators, and functions. Includes active error and warning line styling.
- **Code Folding**: Fold/unfold blocks for functions (`def`) and classes (`class`) to manage complex, multi-line file navigation easily.
- **Auto-Indentation & Autocomplete**: Intelligent auto-indentation on newlines (like matching spaces/colons) and built-in autocomplete suggestions for Python keywords and common imports.
- **Built-in Console**: Execute code in a separate runtime thread inside the editor. Supports active user input loops via stdin mapping directly into the console.
- **Pip Package Manager**: Search and install Python packages using an integrated installer panel that runs subprocess installations in the background.
- **Bolt AI Integration**: Sidecar coding companion panel that queries a local Ollama server running coding models (such as `qwen2.5-coder`) to assist with questions and code snippets with inline copy buttons.
- **Showcase Webpage**: Includes a beautiful built-in landing page showcase (`showcase_website.html`) detailing the project's vision, features, unique selling proposition, and future roadmaps.

## UI Styling

Featuring a customized dark-theme aesthetic:
- **Editor**: Deep grey/black canvas with distinct syntax coloring.
- **Sidebar**: High-contrast, clean panel navigation with dedicated icons.
- **Interactive Controls**: Modern console buttons with active status states.

## File Structure

```
├── app.py                # Core application setup, window classes, and IDE layout
├── bolt_ai.py            # AI assistant widget querying local Ollama
├── JaxPY.ico             # Application shortcut icon
├── bolt.png              # AI sidebar graphic
├── showcase_website.html # Landing page website
├── images/               # Showcase UI graphics
├── .gitignore            # Git exclusion guidelines
└── LICENSE               # MIT License
```

## Getting Started

### Prerequisites

- Python 3.8 or higher.
- `PyQt5` library.
- `requests` library (for Ollama API connectivity).
- (Optional) Local Ollama server running with `qwen2.5-coder:3b` model for AI help.

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/Jalpan04/JaxPY.git
   ```
2. Navigate to the project folder:
   ```bash
   cd JaxPY
   ```
3. Install the dependencies:
   ```bash
   pip install PyQt5 requests
   ```

### Execution

Run the main editor application:
```bash
python app.py
```

To view the landing page showcase:
Open `showcase_website.html` in any web browser.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
