import ast
import os
import sys
from datetime import datetime


def get_docstring(node):
    """Get the docstring from an AST node."""
    return ast.get_docstring(node) or ""


def process_node(node, depth=0):
    """Process an AST node and return markdown documentation."""
    docs = []

    if isinstance(node, ast.ClassDef):
        # Document class
        docs.append(f"## {node.name}\n")
        class_doc = get_docstring(node)
        if class_doc:
            docs.append(f"{class_doc}\n")

        # Process class methods
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                docs.extend(process_node(item, depth + 1))

    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        # Document function/method
        method_name = node.name
        if not method_name.startswith("_") or method_name == "__init__":
            docs.append(f"### {method_name}\n")
            func_doc = get_docstring(node)
            if func_doc:
                # Format docstring for parameters and examples
                lines = func_doc.split("\n")
                formatted_lines = []
                in_parameters = False
                in_example = False

                for line in lines:
                    if line.strip().startswith("Parameters"):
                        in_parameters = True
                        formatted_lines.append("\n**Parameters**\n")
                    elif line.strip().startswith("Example"):
                        in_example = True
                        formatted_lines.append("\n**Example**\n")
                        formatted_lines.append("```python")
                    elif in_example and line.strip() == "":
                        formatted_lines.append("```\n")
                        in_example = False
                    elif in_parameters and line.strip() == "":
                        in_parameters = False
                        formatted_lines.append("")
                    elif in_parameters:
                        # Format parameter lines
                        parts = line.strip().split(":")
                        if len(parts) > 1:
                            param = parts[0].strip()
                            desc = ":".join(parts[1:]).strip()
                            formatted_lines.append(f"- `{param}`: {desc}")
                        else:
                            formatted_lines.append(line)
                    else:
                        formatted_lines.append(line)

                if in_example:
                    formatted_lines.append("```\n")

                docs.append("\n".join(formatted_lines) + "\n")

    return docs


def generate_markdown(file_path):
    """Generate Mintlify-compatible MDX documentation for a Python file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Parse the Python file
        tree = ast.parse(content)

        # Get module docstring
        module_doc = get_docstring(tree) or ""

        # Create frontmatter
        filename = os.path.basename(file_path)
        title = filename.replace(".py", "").replace("_", " ").title()

        frontmatter = [
            "---",
            f'title: "{title}"',
            f'description: "Documentation for {filename}"',
            "api: false",
            "---\n",
        ]

        # Start with module docstring
        docs = []
        if module_doc:
            docs.append(f"# Overview\n")
            docs.append(f"{module_doc}\n")

        # Process all nodes
        for node in tree.body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                docs.extend(process_node(node))

        return "\n".join(frontmatter + docs)

    except Exception as e:
        return f"Error processing {file_path}: {str(e)}"


def create_mintjson():
    """Create mint.json configuration file."""
    config = {
        "name": "Interpreter 1",
        "logo": {"dark": "/logo/dark.png", "light": "/logo/light.png"},
        "favicon": "/favicon.png",
        "colors": {
            "primary": "#0D9373",
            "light": "#07C983",
            "dark": "#0D9373",
            "anchors": {"from": "#0D9373", "to": "#07C983"},
        },
        "topbarLinks": [
            {
                "name": "GitHub",
                "url": "https://github.com/KillianLucas/open-interpreter",
            }
        ],
        "topbarCtaButton": {
            "name": "Get Started",
            "url": "https://docs.openinterpreter.com/introduction",
        },
        "navigation": [
            {"group": "Getting Started", "pages": ["introduction", "quickstart"]},
            {
                "group": "Core Components",
                "pages": ["interpreter", "cli", "profiles", "server"],
            },
            {
                "group": "Tools",
                "pages": [
                    "tools/base",
                    "tools/bash",
                    "tools/computer",
                    "tools/edit",
                    "tools/run",
                ],
            },
            {"group": "UI Components", "pages": ["ui/markdown", "ui/tool"]},
        ],
    }

    import json

    with open("docs/mint.json", "w") as f:
        json.dump(config, f, indent=2)


def main():
    # Create docs directory
    os.makedirs("docs", exist_ok=True)

    # Create introduction and quickstart
    intro_content = """---
title: "Introduction"
description: "Welcome to the Open Interpreter documentation"
---

# Introduction

Open Interpreter is a natural language interface for your computer. It provides an intuitive way to interact with your system using natural language commands.

## Features

- Natural language processing of commands
- Secure execution environment
- Multiple language model support
- Extensible tool system
"""

    quickstart_content = """---
title: "Quickstart"
description: "Get started with Open Interpreter"
---

# Quickstart

Get started with Open Interpreter in minutes.

## Installation

```bash
pip install open-interpreter
```

## Basic Usage

```python
from interpreter import Interpreter

interpreter = Interpreter()
interpreter.chat("Hello, what can you help me with?")
```
"""

    with open("docs/introduction.md", "w") as f:
        f.write(intro_content)

    with open("docs/quickstart.md", "w") as f:
        f.write(quickstart_content)

    # Get all Python files in interpreter_1
    base_path = "interpreter_1"
    for root, _, files in os.walk(base_path):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                # Generate markdown
                markdown = generate_markdown(file_path)
                # Create relative output path
                rel_path = os.path.relpath(file_path, base_path)
                output_path = os.path.join("docs", rel_path.replace(".py", ".mdx"))
                # Ensure output directory exists
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                # Write MDX file
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(markdown)
                print(f"Generated docs for {file_path}")

    # Convert introduction and quickstart to .mdx
    os.rename("docs/introduction.md", "docs/introduction.mdx")
    os.rename("docs/quickstart.md", "docs/quickstart.mdx")

    # Create mint.json
    create_mintjson()
    print("Generated mint.json configuration")


if __name__ == "__main__":
    main()
