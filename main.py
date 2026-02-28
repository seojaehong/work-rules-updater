"""
취업규칙 자동 변경 시스템 - CLI
"""

import os

import click
from rich.console import Console

console = Console()


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """취업규칙 자동 변경 시스템

    법령 개정사항을 자동 추적하여 취업규칙 수정안과 신구조문 대조표를 생성합니다.
    """
    pass


@cli.command("check-updates")
@click.option("--laws", "-l", default=None, help="확인할 법령 (쉼표 구분, 미지정 시 전체)")
@click.option("--since", "-s", default=None, help="기준일 (YYYY-MM-DD, 미지정 시 올해 1월 1일)")
@click.option("--output", "-o", default=None, help="결과 저장 경로 (.json)")
def check_updates(laws, since, output):
    """법령 개정사항 확인

    예시:
        python main.py check-updates
        python main.py check-updates --laws 근로기준법,최저임금법
        python main.py check-updates --since 2025-01-01 -o updates.json
    """
    from src.ingestion.law_client import LawAPIClient
    from src.outputs.json_output import JsonOutputWriter

    console.print("\n[bold blue]📋 법령 개정사항 확인[/bold blue]\n")

    client = LawAPIClient()

    law_list = laws.split(",") if laws else None
    results = client.check_amendments(law_names=law_list, since=since)

    if not results:
        console.print("[yellow]변경된 법령이 없습니다.[/yellow]")
        return

    for result in results:
        console.print(f"  [green]📌 {result['law_name']}[/green]")
        console.print(f"     시행일: {result.get('effective_date', '-')}")
        console.print(f"     변경 조문: {', '.join(result.get('changed_articles', []))}")
        console.print()

    if output:
        saved_path = JsonOutputWriter().write(results, output)
        console.print(f"[green]✅ 저장 완료: {saved_path}[/green]")


@cli.command("parse-rules")
@click.argument("input_file")
@click.option("--output", "-o", default=None, help="파싱 결과 저장 경로 (.json)")
def parse_rules(input_file, output):
    """취업규칙 파싱 (.docx)

    예시:
        python main.py parse-rules data/company_rules/취업규칙.docx
        python main.py parse-rules data/company_rules/취업규칙.docx -o parsed.json
    """
    from src.ingestion.rules_parser import WorkRulesParser
    from src.outputs.json_output import JsonOutputWriter

    console.print(f"\n[bold blue]📄 취업규칙 파싱: {input_file}[/bold blue]\n")

    parser = WorkRulesParser()
    articles = parser.parse(input_file)

    console.print(f"[green]✅ {len(articles)}개 조문 파싱 완료[/green]\n")

    for art in articles[:10]:
        console.print(f"  제{art['number']}조 ({art.get('title', '-')})")

    if len(articles) > 10:
        console.print(f"  ... 외 {len(articles) - 10}개 조문")

    if output:
        saved_path = JsonOutputWriter().write(articles, output)
        console.print(f"\n[green]✅ 저장 완료: {saved_path}[/green]")


@cli.command("match")
@click.argument("rules_file")
@click.option("--since", "-s", default=None, help="법령 변경 기준일")
def match_changes(rules_file, since):
    """법령 변경사항 ↔ 취업규칙 매칭 분석

    예시:
        python main.py match data/company_rules/취업규칙.docx
        python main.py match data/company_rules/취업규칙.docx --since 2025-01-01
    """
    from src.ingestion.rules_parser import WorkRulesParser
    from src.matching.matcher import RulesMatcher

    console.print(f"\n[bold blue]🔍 매칭 분석: {rules_file}[/bold blue]\n")

    # 1. 취업규칙 파싱
    console.print("[dim]1. 취업규칙 파싱 중...[/dim]")
    parser = WorkRulesParser()
    articles = parser.parse(rules_file)
    console.print(f"   → {len(articles)}개 조문\n")

    # 2. 매칭
    console.print("[dim]2. 법령 변경사항과 매칭 중...[/dim]")
    matcher = RulesMatcher()
    matches = matcher.find_matches(articles, since=since)

    if not matches:
        console.print("[yellow]영향받는 조문이 없습니다.[/yellow]")
        return

    console.print(f"   → [red]{len(matches)}개 조문 변경 필요[/red]\n")

    for m in matches:
        console.print(f"  [red]⚠ 제{m['rule_article']}조[/red] ← {m['law_name']} {m['law_article']} 개정")
        console.print(f"    사유: {m.get('reason', '-')}")
        console.print()


@cli.command("generate-table")
@click.argument("rules_file")
@click.option("--output", "-o", default="output/", help="출력 디렉토리")
@click.option("--since", "-s", default=None, help="법령 변경 기준일")
@click.option("--company-name", "-c", default="", help="회사명 (문서 헤더용)")
@click.option("--hwpx-template", default=None, help="HWPX 템플릿 경로 (선택)")
def generate_table(rules_file, output, since, company_name, hwpx_template):
    """신구조문 대조표 생성

    예시:
        python main.py generate-table data/company_rules/취업규칙.docx
        python main.py generate-table data/company_rules/취업규칙.docx -o output/ --since 2025-01-01
    """
    from src.ingestion.rules_parser import WorkRulesParser
    from src.matching.matcher import RulesMatcher
    from src.outputs.pipeline import OutputPipeline

    console.print(f"\n[bold blue]📊 신구조문 대조표 생성[/bold blue]\n")

    console.print("[dim]1. 취업규칙 파싱 중...[/dim]")
    parser = WorkRulesParser()
    articles = parser.parse(rules_file)
    console.print(f"   → {len(articles)}개 조문\n")

    console.print("[dim]2. 매칭 분석 중...[/dim]")
    matcher = RulesMatcher()
    matches = matcher.find_matches(articles, since=since)
    console.print(f"   → {len(matches)}개 매칭\n")

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
        console.print(f"[green]✅ {key.upper()} 생성: {path}[/green]")

    if not template_path:
        console.print("[yellow]ℹ HWPX 템플릿 미지정으로 JSON/XLSX만 생성했습니다.[/yellow]")
    elif files.get("hwpx_error"):
        console.print(f"[yellow]⚠ HWPX 생성 실패: {files['hwpx_error']}[/yellow]")


if __name__ == "__main__":
    cli()
