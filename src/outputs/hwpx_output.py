"""HWPX output writer based on template replacement."""

from __future__ import annotations

import xml.etree.ElementTree as et
import zipfile
from pathlib import Path

REQUIRED_ENTRIES = ("mimetype", "Contents/content.hpf")
DEFAULT_SECTION_FILE = "Contents/section0.xml"
PREVIEW_TEXT_FILE = "Preview/PrvText.txt"


def _local_name(tag: str) -> str:
    if tag.startswith("{") and "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _section_files(names: list[str]) -> list[str]:
    return sorted(
        name
        for name in names
        if name.startswith("Contents/section") and name.endswith(".xml")
    )


class HwpxComparisonWriter:
    """Generate `.hwpx` output from an existing template package."""

    def generate(
        self,
        changes: list[dict],
        output_path: str,
        template_path: str,
        company_name: str = "",
        section_file: str = DEFAULT_SECTION_FILE,
        replace_all: bool = True,
    ) -> str:
        template = Path(template_path)
        output = Path(output_path)

        report = self.validate(template)
        if not report["ok"]:
            raise ValueError(f"Invalid HWPX template: {template} ({report['error']})")

        text = self._render_changes_text(changes, company_name)

        with zipfile.ZipFile(template, "r") as source_zip:
            infos = source_zip.infolist()
            data_by_name = {info.filename: source_zip.read(info.filename) for info in infos}

        if section_file not in data_by_name:
            available = ", ".join(_section_files(list(data_by_name.keys())))
            raise ValueError(f"Section file not found: {section_file}. Available: {available}")

        updated_section = self._update_section(data_by_name[section_file], text, replace_all)
        data_by_name[section_file] = updated_section

        if PREVIEW_TEXT_FILE in data_by_name:
            data_by_name[PREVIEW_TEXT_FILE] = (text + "\n").encode("utf-8")

        output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output, "w") as out_zip:
            for info in infos:
                out_zip.writestr(info, data_by_name[info.filename])

        output_report = self.validate(output)
        if not output_report["ok"]:
            raise ValueError(f"Generated HWPX is invalid: {output} ({output_report['error']})")

        return str(output)

    def validate(self, path: Path) -> dict:
        report = {
            "path": str(path),
            "ok": False,
            "error": "",
            "mimetype": "",
            "missing_entries": [],
            "section_files": [],
        }

        if not path.exists() or not path.is_file():
            report["error"] = "File does not exist."
            return report

        try:
            with zipfile.ZipFile(path, "r") as zf:
                names = zf.namelist()
                report["section_files"] = _section_files(names)
                report["missing_entries"] = [entry for entry in REQUIRED_ENTRIES if entry not in names]
                if "mimetype" in names:
                    report["mimetype"] = zf.read("mimetype").decode("utf-8", errors="replace").strip()
        except zipfile.BadZipFile:
            report["error"] = "Not a ZIP container."
            return report
        except Exception as exc:
            report["error"] = str(exc)
            return report

        has_required = not report["missing_entries"]
        has_sections = bool(report["section_files"])
        valid_mimetype = report["mimetype"].startswith("application/hwp")
        report["ok"] = has_required and has_sections and valid_mimetype
        if not report["ok"] and not report["error"]:
            report["error"] = "Structure check failed."
        return report

    def _update_section(self, section_xml: bytes, text: str, replace_all: bool) -> bytes:
        root = et.fromstring(section_xml)
        text_nodes = self._find_text_nodes(root)

        if text_nodes:
            targets = text_nodes if replace_all else [text_nodes[0]]
        else:
            run_node = self._find_first_run_node(root)
            if run_node is None:
                raise ValueError("No run/para node found for text insertion.")

            namespace = ""
            if run_node.tag.startswith("{") and "}" in run_node.tag:
                namespace = run_node.tag.split("}", 1)[0][1:]

            run_local = _local_name(run_node.tag)
            if run_local.strip().lower() == "para":
                text_local = "TEXT" if run_local.isupper() else "text"
            else:
                text_local = "t"
            text_tag = f"{{{namespace}}}{text_local}" if namespace else text_local

            inserted = et.Element(text_tag)
            run_node.append(inserted)
            targets = [inserted]

        for node in targets:
            node.text = text

        return et.tostring(root, encoding="utf-8", xml_declaration=True)

    @staticmethod
    def _find_text_nodes(root: et.Element) -> list[et.Element]:
        text_like = {"t", "text"}
        return [
            node
            for node in root.iter()
            if _local_name(node.tag).strip().lower() in text_like
        ]

    @staticmethod
    def _find_first_run_node(root: et.Element) -> et.Element | None:
        run_like = {"run", "para"}
        for node in root.iter():
            if _local_name(node.tag).strip().lower() in run_like:
                return node
        return None

    @staticmethod
    def _render_changes_text(changes: list[dict], company_name: str) -> str:
        header = f"{company_name} 취업규칙 변경사항" if company_name else "취업규칙 변경사항"
        lines = [header, ""]

        if not changes:
            lines.append("변경 대상 조문이 없습니다.")
            return "\n".join(lines)

        for index, change in enumerate(changes, start=1):
            number = change.get("article_number", "-")
            old_text = change.get("old_text", "")
            new_text = change.get("new_text", "")
            reason = change.get("reason", "")
            lines.extend(
                [
                    f"{index}. 제{number}조",
                    f"현행: {old_text}",
                    f"변경: {new_text}",
                    f"사유: {reason}",
                    "",
                ]
            )

        return "\n".join(lines).strip()
