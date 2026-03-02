"""
취업규칙 자동 변경 시스템 - CLI
"""

from __future__ import annotations

import json
import os
from functools import wraps
from pathlib import Path

import click
from rich.console import Console

console = Console(emoji=False)


def _is_placeholder(value: str, placeholders: set[str]) -> bool:
    cleaned = (value or "").strip()
    if not cleaned:
        return True
    return cleaned in placeholders


def _command_guard(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except click.ClickException:
            raise
        except (FileNotFoundError, ValueError) as exc:
            raise click.ClickException(str(exc)) from exc
        except Exception as exc:  # pragma: no cover - defensive guard
            raise click.ClickException(f"실행 중 오류: {exc}") from exc

    return wrapper


def _load_amendments_file(path_str: str) -> list[dict]:
    path = Path(path_str)
    if not path.exists():
        raise FileNotFoundError(f"개정 데이터 파일을 찾을 수 없습니다: {path_str}")

    with open(path, "r", encoding="utf-8") as file:
        payload = json.load(file)

    if isinstance(payload, dict):
        amendments = payload.get("amendments", [])
    elif isinstance(payload, list):
        amendments = payload
    else:
        raise ValueError("개정 데이터 형식이 올바르지 않습니다. list 또는 {'amendments': [...]} 형식을 사용하세요.")

    if not isinstance(amendments, list):
        raise ValueError("개정 데이터의 amendments 값은 list여야 합니다.")

    return amendments


def _build_file_report(amendments_file: str, amendments: list[dict]) -> dict:
    return {
        "status": "ok",
        "source": "file",
        "errors": [],
        "had_errors": False,
        "failed_laws": 0,
        "amendment_count": len(amendments),
        "amendments_file": str(amendments_file),
    }


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """취업규칙 자동 변경 시스템

    법령 개정사항을 자동 추적하여 취업규칙 수정안과 신구조문 대조표를 생성합니다.
    """
    pass


@cli.command("doctor")
@_command_guard
def doctor():
    """환경/입력 자원 사전 점검."""
    from dotenv import load_dotenv

    load_dotenv()

    warnings = 0
    ok = 0

    data_key = os.getenv("DATA_GO_KR_KEY", "")
    if _is_placeholder(data_key, {"your_service_key"}):
        console.print("[yellow]WARN[/yellow] DATA_GO_KR_KEY 미설정")
        warnings += 1
    else:
        console.print("[green]OK[/green] DATA_GO_KR_KEY 설정됨")
        ok += 1

    law_api_id = os.getenv("LAW_API_ID", "")
    if _is_placeholder(law_api_id, {"your_law_go_kr_id"}):
        console.print("[yellow]WARN[/yellow] LAW_API_ID 미설정 (조문 상세 조회 제한)")
        warnings += 1
    else:
        console.print("[green]OK[/green] LAW_API_ID 설정됨")
        ok += 1

    rules_dir = Path("data/company_rules")
    rules_files = []
    if rules_dir.exists():
        rules_files.extend(rules_dir.glob("*.docx"))
        rules_files.extend(rules_dir.glob("*.hwpx"))

    if rules_files:
        console.print(f"[green]OK[/green] 입력 취업규칙 파일 {len(rules_files)}개 발견")
        ok += 1
    else:
        console.print("[yellow]WARN[/yellow] data/company_rules/에 .docx 또는 .hwpx 파일이 없습니다")
        warnings += 1

    template_path = (os.getenv("HWPX_TEMPLATE_PATH", "") or "").strip()
    if template_path:
        if Path(template_path).exists():
            console.print(f"[green]OK[/green] HWPX 템플릿 확인: {template_path}")
            ok += 1
        else:
            console.print(f"[yellow]WARN[/yellow] HWPX 템플릿 없음: {template_path}")
            warnings += 1
    else:
        console.print("[yellow]WARN[/yellow] HWPX_TEMPLATE_PATH 미설정 (HWPX 출력 비활성)")
        warnings += 1

    console.print(f"\n점검 완료: OK {ok} / WARN {warnings}")


@cli.command("check-updates")
@click.option("--laws", "-l", default=None, help="확인할 법령 (쉼표 구분, 미지정 시 전체)")
@click.option("--since", "-s", default=None, help="기준일 (YYYY-MM-DD, 미지정 시 올해 1월 1일)")
@click.option("--output", "-o", default=None, help="결과 저장 경로 (.json)")
@_command_guard
def check_updates(laws, since, output):
    """법령 개정사항 확인

    예시:
        python main.py check-updates
        python main.py check-updates --laws 근로기준법,최저임금법
        python main.py check-updates --since 2025-01-01 -o updates.json
    """
    from src.ingestion.law_client import LawAPIClient
    from src.outputs.json_output import JsonOutputWriter

    console.print("\n[bold blue]법령 개정사항 확인[/bold blue]\n")

    client = LawAPIClient()

    law_list = laws.split(",") if laws else None
    results = client.check_amendments(law_names=law_list, since=since)

    if not results:
        report = getattr(client, "last_check_report", {})
        if report.get("had_errors"):
            console.print("[yellow]법령 조회 실패가 있어 결과가 비어 있습니다.[/yellow]")
            console.print(f"[yellow]실패 법령 수: {report.get('failed_laws', 0)}[/yellow]")
        else:
            console.print("[yellow]변경된 법령이 없습니다.[/yellow]")
        return

    for result in results:
        console.print(f"  [green]- {result['law_name']}[/green]")
        console.print(f"     시행일: {result.get('effective_date', '-')}")
        console.print(f"     변경 조문: {', '.join(result.get('changed_articles', []))}")
        console.print()

    if output:
        saved_path = JsonOutputWriter().write(results, output)
        console.print(f"[green]저장 완료: {saved_path}[/green]")


@cli.command("parse-rules")
@click.argument("input_file")
@click.option("--output", "-o", default=None, help="파싱 결과 저장 경로 (.json)")
@_command_guard
def parse_rules(input_file, output):
    """취업규칙 파싱 (.docx/.hwpx)

    예시:
        python main.py parse-rules data/company_rules/취업규칙.docx
        python main.py parse-rules data/company_rules/취업규칙.docx -o parsed.json
    """
    from src.ingestion.rules_parser import WorkRulesParser
    from src.outputs.json_output import JsonOutputWriter

    console.print(f"\n[bold blue]취업규칙 파싱: {input_file}[/bold blue]\n")

    parser = WorkRulesParser()
    articles = parser.parse(input_file)

    console.print(f"[green]{len(articles)}개 조문 파싱 완료[/green]\n")

    for art in articles[:10]:
        console.print(f"  제{art['number']}조 ({art.get('title', '-')})")

    if len(articles) > 10:
        console.print(f"  ... 외 {len(articles) - 10}개 조문")

    if output:
        saved_path = JsonOutputWriter().write(articles, output)
        console.print(f"\n[green]저장 완료: {saved_path}[/green]")


@cli.command("match")
@click.argument("rules_file")
@click.option("--since", "-s", default=None, help="법령 변경 기준일")
@click.option(
    "--amendments-file",
    default=None,
    help="오프라인 개정 데이터 JSON 경로 (list 또는 {'amendments': [...]})",
)
@click.option(
    "--override",
    default=None,
    help="회사별 매핑 override JSON 경로 (config/overrides/xxx.json)",
)
@_command_guard
def match_changes(rules_file, since, amendments_file, override):
    """법령 변경사항 ↔ 취업규칙 매칭 분석

    예시:
        python main.py match data/company_rules/취업규칙.docx
        python main.py match data/company_rules/취업규칙.docx --since 2025-01-01
    """
    from src.ingestion.rules_parser import WorkRulesParser
    from src.matching.matcher import RulesMatcher

    console.print(f"\n[bold blue]매칭 분석: {rules_file}[/bold blue]\n")

    console.print("[dim]1. 취업규칙 파싱 중...[/dim]")
    parser = WorkRulesParser()
    articles = parser.parse(rules_file)
    console.print(f"   -> {len(articles)}개 조문\n")

    console.print("[dim]2. 법령 변경사항과 매칭 중...[/dim]")
    matcher = RulesMatcher(override_path=override)
    if amendments_file:
        amendments = _load_amendments_file(amendments_file)
        api_report = _build_file_report(amendments_file, amendments)
        console.print(f"   -> 오프라인 개정 데이터 {len(amendments)}건 사용")
        matches = matcher.find_matches(
            rule_articles=articles,
            since=since,
            amendments=amendments,
            api_report=api_report,
        )
    else:
        matches = matcher.find_matches(articles, since=since)
    report = getattr(matcher, "last_report", {})

    if report.get("source") == "file":
        console.print("[green]오프라인 개정 데이터 기반 매칭입니다.[/green]")
    elif report.get("status") == "degraded" and report.get("errors"):
        console.print("[yellow]법령 API 조회 실패로 폴백 매칭 결과를 포함합니다.[/yellow]")
        console.print(f"[yellow]폴백 매칭 수: {report.get('fallback_count', 0)}[/yellow]\n")

    if not matches:
        console.print("[yellow]영향받는 조문이 없습니다.[/yellow]")
        return

    console.print(f"   -> [red]{len(matches)}개 조문 변경/검토 필요[/red]\n")

    for m in matches:
        console.print(
            f"  [red]제{m['rule_article']}조[/red] <- {m['law_name']} {m['law_article']} ({m.get('match_type', '-')})"
        )
        console.print(f"    사유: {m.get('reason', '-')}")
        console.print()


@cli.command("diagnose-match")
@click.argument("rules_file")
@click.option("--since", "-s", default=None, help="법령 변경 기준일")
@click.option(
    "--amendments-file",
    default=None,
    help="오프라인 개정 데이터 JSON 경로 (list 또는 {'amendments': [...]})",
)
@click.option(
    "--output",
    "-o",
    default="output/diagnostics/match_diagnosis.json",
    help="진단 리포트 저장 경로 (.json)",
)
@click.option(
    "--override",
    default=None,
    help="회사별 매핑 override JSON 경로 (config/overrides/xxx.json)",
)
@_command_guard
def diagnose_match(rules_file, since, amendments_file, output, override):
    """법령조회/매칭 실패 원인 진단 리포트 생성

    예시:
        python main.py diagnose-match data/company_rules/취업규칙.docx
        python main.py diagnose-match data/company_rules/취업규칙.docx -o output/diagnostics/report.json
    """
    from src.evals.diagnostics import MatchDiagnostics
    from src.ingestion.rules_parser import WorkRulesParser
    from src.matching.matcher import RulesMatcher
    from src.outputs.json_output import JsonOutputWriter

    console.print("\n[bold blue]법령조회/매칭 진단[/bold blue]\n")

    console.print("[dim]1. 취업규칙 파싱 중...[/dim]")
    parser = WorkRulesParser()
    articles = parser.parse(rules_file)
    console.print(f"   -> {len(articles)}개 조문\n")

    if amendments_file:
        console.print("[dim]2. 오프라인 개정 데이터 로드 중...[/dim]")
        amendments = _load_amendments_file(amendments_file)
        api_report = _build_file_report(amendments_file, amendments)
        console.print(f"   -> 개정 법령 {len(amendments)}건")
        console.print(f"   -> source=file ({amendments_file})")
        console.print()
    else:
        from src.ingestion.law_client import LawAPIClient

        console.print("[dim]2. 법령 개정 조회 중...[/dim]")
        client = LawAPIClient()
        amendments = client.check_amendments(since=since)
        api_report = getattr(client, "last_check_report", {})
        console.print(f"   -> 개정 법령 {len(amendments)}건")
        if api_report.get("had_errors"):
            console.print(f"   -> [yellow]조회 실패 법령 {api_report.get('failed_laws', 0)}건[/yellow]")
        console.print()

    console.print("[dim]3. 매칭 + 진단 리포트 생성 중...[/dim]")
    matcher = RulesMatcher(override_path=override)
    matches = matcher.find_matches(
        rule_articles=articles,
        amendments=amendments,
        api_report=api_report,
    )
    report = getattr(matcher, "last_report", {})

    diagnosis = MatchDiagnostics(matcher).build(
        rule_articles=articles,
        matches=matches,
        report=report,
        amendments=amendments,
        since=since,
    )

    saved_path = JsonOutputWriter().write(diagnosis, output)

    summary = diagnosis.get("summary", {})
    console.print("[green]진단 리포트 생성 완료[/green]")
    console.print(f"- 전체 조문: {summary.get('rule_article_count', 0)}")
    console.print(f"- 매칭 조문: {summary.get('matched_article_count', 0)}")
    console.print(f"- 미매칭 조문: {summary.get('unmatched_article_count', 0)}")
    console.print(f"- 조회 실패 법령: {summary.get('lookup_failed_law_count', 0)}")

    code_counts = diagnosis.get("diagnostic_code_counts", {})
    if code_counts:
        console.print("\n주요 미매칭 코드:")
        for code, count in sorted(code_counts.items(), key=lambda item: item[1], reverse=True)[:5]:
            console.print(f"  - {code}: {count}")

    console.print(f"\n[green]저장 완료: {saved_path}[/green]")


@cli.command("generate-table")
@click.argument("rules_file")
@click.option("--output", "-o", default="output/", help="출력 디렉토리")
@click.option("--since", "-s", default=None, help="법령 변경 기준일")
@click.option("--company-name", "-c", default="", help="회사명 (문서 헤더용)")
@click.option("--hwpx-template", default=None, help="HWPX 템플릿 경로 (선택)")
@click.option(
    "--amendments-file",
    default=None,
    help="오프라인 개정 데이터 JSON 경로 (list 또는 {'amendments': [...]})",
)
@click.option(
    "--override",
    default=None,
    help="회사별 매핑 override JSON 경로 (config/overrides/xxx.json)",
)
@_command_guard
def generate_table(rules_file, output, since, company_name, hwpx_template, amendments_file, override):
    """신구조문 대조표 생성

    예시:
        python main.py generate-table data/company_rules/취업규칙.docx
        python main.py generate-table data/company_rules/취업규칙.docx -o output/ --since 2025-01-01
    """
    from src.ingestion.rules_parser import WorkRulesParser
    from src.matching.matcher import RulesMatcher
    from src.matching.updater import RulesUpdater
    from src.outputs.json_output import JsonOutputWriter
    from src.outputs.pipeline import OutputPipeline

    console.print("\n[bold blue]신구조문 대조표 생성[/bold blue]\n")

    console.print("[dim]1. 취업규칙 파싱 중...[/dim]")
    parser = WorkRulesParser()
    articles = parser.parse(rules_file)
    console.print(f"   -> {len(articles)}개 조문\n")

    console.print("[dim]2. 매칭 분석 중...[/dim]")
    matcher = RulesMatcher(override_path=override)
    if amendments_file:
        amendments = _load_amendments_file(amendments_file)
        api_report = _build_file_report(amendments_file, amendments)
        console.print(f"   -> 오프라인 개정 데이터 {len(amendments)}건 사용")
        matches = matcher.find_matches(
            rule_articles=articles,
            since=since,
            amendments=amendments,
            api_report=api_report,
        )
    else:
        matches = matcher.find_matches(articles, since=since)
    report = getattr(matcher, "last_report", {})

    if report.get("source") == "file":
        console.print("[green]오프라인 개정 데이터 기반 매칭입니다.[/green]")
    elif report.get("status") == "degraded" and report.get("errors"):
        console.print("[yellow]법령 API 조회 실패로 폴백 매칭 결과를 포함합니다.[/yellow]")

    console.print(f"   -> {len(matches)}개 매칭\n")

    console.print("[dim]3. 수정안 초안 생성 중...[/dim]")
    drafts = RulesUpdater().generate_draft(matches=matches, original_articles=articles)
    draft_path = Path(output) / "draft_revisions.json"
    JsonOutputWriter().write(drafts, str(draft_path))
    console.print(f"   -> {len(drafts)}개 수정안 초안")

    template_path = hwpx_template or os.getenv("HWPX_TEMPLATE_PATH")
    pipeline = OutputPipeline()
    result = pipeline.generate_outputs(
        matches=matches,
        output_dir=output,
        company_name=company_name,
        hwpx_template=template_path,
    )

    files = result.get("files", {})
    for key, path in files.items():
        if key == "hwpx_error":
            continue
        console.print(f"[green]{key.upper()} 생성: {path}[/green]")

    console.print(f"[green]DRAFT 생성: {draft_path}[/green]")

    if not template_path:
        console.print("[yellow]HWPX 템플릿 미지정으로 JSON/XLSX만 생성했습니다.[/yellow]")
    elif files.get("hwpx_error"):
        console.print(f"[yellow]HWPX 생성 실패: {files['hwpx_error']}[/yellow]")


if __name__ == "__main__":
    cli()
