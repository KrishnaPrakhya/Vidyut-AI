from __future__ import annotations

import argparse
import json
from pathlib import Path

MARKER = "# %%"
MARKDOWN_MARKER = "# %% [markdown]"


def split_cells(source: str) -> list[tuple[str, str]]:
    cells: list[tuple[str, str]] = []
    kind = "code"
    buffer: list[str] = []

    for line in source.splitlines():
        if line.startswith(MARKER):
            if buffer:
                cells.append((kind, "\n".join(buffer).strip("\n")))
                buffer = []
            kind = "markdown" if line.startswith(MARKDOWN_MARKER) else "code"
            continue
        buffer.append(line)

    if buffer:
        cells.append((kind, "\n".join(buffer).strip("\n")))
    return [(kind, body) for kind, body in cells if body.strip()]


def strip_comment_prefix(body: str) -> str:
    lines = []
    for line in body.splitlines():
        if line.startswith("# "):
            lines.append(line[2:])
        elif line.strip() == "#":
            lines.append("")
        else:
            lines.append(line)
    return "\n".join(lines).strip("\n")


def to_notebook(source: str) -> dict:
    cells = []
    for kind, body in split_cells(source):
        text = strip_comment_prefix(body) if kind == "markdown" else body
        cell = {
            "cell_type": kind,
            "metadata": {},
            "source": [f"{line}\n" for line in text.splitlines()],
        }
        if cell["source"]:
            cell["source"][-1] = cell["source"][-1].rstrip("\n")
        if kind == "code":
            cell["execution_count"] = None
            cell["outputs"] = []
        cells.append(cell)

    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python", "version": "3.11"},
            "accelerator": "GPU",
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def main() -> None:
    parser = argparse.ArgumentParser(prog="ml.kaggle.to_notebook")
    parser.add_argument("scripts", nargs="*", default=None)
    args = parser.parse_args()

    here = Path(__file__).resolve().parent
    paths = [Path(p) for p in args.scripts] if args.scripts else sorted(here.glob("train_*.py"))

    for path in paths:
        notebook = to_notebook(path.read_text(encoding="utf-8"))
        destination = path.with_suffix(".ipynb")
        with destination.open("w", encoding="utf-8") as handle:
            json.dump(notebook, handle, indent=1)
        code = sum(1 for c in notebook["cells"] if c["cell_type"] == "code")
        markdown = len(notebook["cells"]) - code
        print(f"{destination.name}: {code} code cells, {markdown} markdown cells")


if __name__ == "__main__":
    main()
