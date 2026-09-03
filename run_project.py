"""Run the capstone notebook workflow from a local Python terminal.

The project is authored as a notebook, but local environments do not always
have Jupyter installed. This runner executes the Python workflow cells in order
and adapts the single top-level await cell for normal Python.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


NOTEBOOK = Path("agentic_ai_capstone_colab.ipynb")
WORKFLOW_CELLS = (7, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30)


def cell_source(cell: dict) -> str:
    source = cell.get("source", "")
    if isinstance(source, list):
        return "".join(source)
    return source


def main() -> None:
    namespace = sys.modules["__main__"].__dict__
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))

    for index in WORKFLOW_CELLS:
        code = cell_source(notebook["cells"][index])
        code = code.replace(
            "final_output = await app.ainvoke(inputs)",
            "final_output = asyncio.run(app.ainvoke(inputs))",
        )

        print(f"\n=== Running notebook cell {index} ===")
        exec(compile(code, f"{NOTEBOOK}:cell-{index}", "exec"), namespace)


if __name__ == "__main__":
    main()
