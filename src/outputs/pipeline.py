"""Output pipeline orchestrating json/xlsx/hwpx generation."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from src.outputs.hwpx_output import HwpxComparisonWriter
from src.outputs.json_output import JsonOutputWriter
from src.outputs.xlsx_output import XlsxComparisonWriter


class OutputPipeline:
    """Generate multiple output formats from match results."""

    def __init__(self):
        self.json_writer = JsonOutputWriter()
        self.xlsx_writer = XlsxComparisonWriter()
        self.hwpx_writer = HwpxComparisonWriter()

    def generate_outputs(
        self,
        matches: list[dict],
        output_dir: str,
        company_name: str = "",
        hwpx_template: Optional[str] = None,
    ) -> dict:
        path = Path(output_dir)
        path.mkdir(parents=True, exist_ok=True)

        changes = self._build_changes(matches)
        created: dict[str, str] = {}

        created["json"] = self.json_writer.write(matches, str(path / "match_results.json"))
        created["xlsx"] = self.xlsx_writer.generate(
            changes=changes,
            output_path=str(path / "comparison_table.xlsx"),
            company_name=company_name,
        )

        if hwpx_template:
            try:
                created["hwpx"] = self.hwpx_writer.generate(
                    changes=changes,
                    output_path=str(path / "comparison_table.hwpx"),
                    template_path=hwpx_template,
                    company_name=company_name,
                )
            except Exception as exc:  # pragma: no cover - surfaced to CLI output
                created["hwpx_error"] = str(exc)

        return {"changes": changes, "files": created}

    @staticmethod
    def _build_changes(matches: list[dict]) -> list[dict]:
        changes = []
        for match in matches:
            article_number = match.get("rule_article", "")
            old_text = match.get("rule_content", "")
            law_name = match.get("law_name", "")
            law_article = match.get("law_article", "")

            changes.append(
                {
                    "article_number": article_number,
                    "old_text": old_text,
                    "new_text": f"[개정 반영 필요] {law_name} {law_article}",
                    "reason": match.get("reason", ""),
                }
            )
        return changes
