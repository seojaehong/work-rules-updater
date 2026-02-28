"""JSON output writer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class JsonOutputWriter:
    """Structured JSON file writer."""

    def write(self, payload: Any, output_path: str) -> str:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
        return str(path)
