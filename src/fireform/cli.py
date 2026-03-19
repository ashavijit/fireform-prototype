from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from . import __version__
from .config import FireFormConfig
from .extractor import LLMExtractor
from .ingestion import IncidentInput
from .pdf_filler import PDFFiller
from .schema import IncidentReport
from .validation import ReportValidator

console = Console()
err_console = Console(stderr=True, style='red')

@click.group(context_settings={'help_option_names': ['-h', '--help']})
@click.version_option(__version__, '-V', '--version', prog_name='fireform')
def cli() -> None:
    pass

@cli.command()
@click.argument('input_source')
@click.option('-t', '--template', 'templates', multiple=True, help='Template ID(s) to fill. Repeatable. Defaults to pyproject.toml setting.')
@click.option('-o', '--output-dir', default=None, help='Directory for output PDFs. Defaults to ./output')
@click.option('-m', '--model', default=None, help='Ollama model (overrides pyproject.toml).')
@click.option('--dry-run', is_flag=True, help='Extract and validate but do not write PDFs.')
@click.option('--json-out', is_flag=True, help='Print extracted JSON to stdout.')
@click.option('-v', '--verbose', is_flag=True, help='Show detailed progress.')
def report(input_source: str, templates: tuple[str, ...], output_dir: str | None, model: str | None, dry_run: bool, json_out: bool, verbose: bool) -> None:
    cfg = FireFormConfig.load()
    model = model or cfg.default_model
    output_dir = output_dir or cfg.output_dir
    templates = templates or tuple(cfg.default_templates)
    console.rule('[bold blue]FireForm[/bold blue]')
    with _spinner('Ingesting input…', verbose):
        try:
            text = IncidentInput(whisper_model=cfg.whisper_model).ingest(input_source)
        except (FileNotFoundError, ValueError) as exc:
            err_console.print(f'[bold]Ingestion error:[/bold] {exc}')
            sys.exit(1)
    console.print(f'  [green]✓[/green] Input ingested ({len(text)} chars)')
    if verbose:
        console.print(Panel(text[:500] + ('…' if len(text) > 500 else ''), title='Input text', border_style='dim'))
    with _spinner(f'Extracting structured data using [bold]{model}[/bold]…', verbose):
        try:
            extractor = LLMExtractor(model=model, ollama_url=cfg.ollama_url, max_retries=cfg.max_retries)
            extracted: IncidentReport = extractor.extract(text)
        except RuntimeError as exc:
            err_console.print(f'[bold]Extraction error:[/bold] {exc}')
            sys.exit(1)
    console.print(f'  [green]✓[/green] Extracted: [cyan]{extracted.incident_type}[/cyan] at [cyan]{extracted.address}[/cyan]')
    if json_out:
        rprint(json.loads(extracted.model_dump_json(indent=2)))
    result = ReportValidator().validate(extracted)
    for err in result.errors:
        console.print(f'  [bold red]✗ ERROR:[/bold red] {err}')
    for warn in result.warnings:
        console.print(f'  [yellow]⚠ WARNING:[/yellow] {warn}')
    bar = _completeness_bar(result.completeness_score)
    console.print(f'  [green]✓[/green] Completeness: {bar} {result.completeness_score:.0%}')
    if not result.is_valid:
        err_console.print('\nValidation failed — PDF generation aborted.')
        sys.exit(1)
    if dry_run:
        console.print('\n[dim]--dry-run: skipping PDF generation.[/dim]')
        console.rule()
        return
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []
    for tpl_id in templates:
        tpl_path = Path(cfg.templates_dir) / f'{tpl_id}.yaml'
        if not tpl_path.exists():
            console.print(f'  [yellow]⚠[/yellow] Template not found: {tpl_path} — skipping.')
            continue
        with _spinner(f'Filling [bold]{tpl_id}[/bold]…', verbose):
            try:
                filler = PDFFiller(tpl_path)
                out_file = out_dir / f'{tpl_id}_filled.pdf'
                filler.fill(result.report, out_file)
                generated.append(out_file)
                console.print(f'  [green]✓[/green] Saved: [cyan]{out_file}[/cyan]')
            except FileNotFoundError as exc:
                console.print(f'  [yellow]⚠[/yellow] {exc}')
    console.rule()
    console.print(f'[bold green]Done.[/bold green] {len(generated)} form(s) generated.\n')

@cli.command()
@click.argument('json_file')
def validate(json_file: str) -> None:
    path = Path(json_file)
    if not path.exists():
        err_console.print(f'File not found: {path}')
        sys.exit(1)
    try:
        data = json.loads(path.read_text())
        report_obj = IncidentReport(**data)
        result = ReportValidator().validate(report_obj)
    except Exception as exc:
        err_console.print(f'Failed to parse/validate: {exc}')
        sys.exit(1)
    console.print(str(result))
    sys.exit(0 if result.is_valid else 1)

@cli.command('list-templates')
def list_templates() -> None:
    cfg = FireFormConfig.load()
    tpl_dir = Path(cfg.templates_dir)
    yamls = sorted(tpl_dir.glob('*.yaml')) if tpl_dir.exists() else []
    if not yamls:
        console.print(f'[yellow]No templates found in {tpl_dir}[/yellow]')
        return
    import yaml
    table = Table(title='Available templates', border_style='blue')
    table.add_column('ID', style='cyan', no_wrap=True)
    table.add_column('Name', style='white')
    table.add_column('PDF', style='dim')
    for yf in yamls:
        cfg_data = yaml.safe_load(yf.read_text())
        table.add_row(cfg_data.get('template_id', yf.stem), cfg_data.get('template_name', '—'), cfg_data.get('pdf_path', '—'))
    console.print(table)

@cli.command()
def doctor() -> None:
    cfg = FireFormConfig.load()
    ok = True
    console.rule('[bold blue]FireForm doctor[/bold blue]')
    import httpx
    try:
        r = httpx.get(f'{cfg.ollama_url}/api/tags', timeout=3)
        models = [m['name'] for m in r.json().get('models', [])]
        console.print(f'  [green]✓[/green] Ollama reachable at {cfg.ollama_url}')
        console.print(f"    Available models: {', '.join(models) or '(none pulled yet)'}")
        if cfg.default_model not in ' '.join(models):
            console.print(f"    [yellow]⚠[/yellow] Default model '{cfg.default_model}' not found. Pull it with: ollama pull {cfg.default_model}")
    except Exception:
        console.print(f'  [red]✗[/red] Cannot reach Ollama at {cfg.ollama_url}')
        console.print('    Start it with: ollama serve')
        ok = False
    import importlib.util
    if importlib.util.find_spec('whisper') is not None:
        console.print('  [green]✓[/green] openai-whisper installed')
    else:
        console.print('  [yellow]⚠[/yellow] openai-whisper not installed (needed for voice input)')
    if importlib.util.find_spec('fitz') is not None:
        console.print('  [green]✓[/green] PyMuPDF (fitz) installed')
    else:
        console.print('  [red]✗[/red] PyMuPDF not installed: pip install PyMuPDF')
        ok = False
    tpl_dir = Path(cfg.templates_dir)
    yamls = list(tpl_dir.glob('*.yaml')) if tpl_dir.exists() else []
    console.print(f'  [green]✓[/green] {len(yamls)} template(s) found in {tpl_dir}')
    console.rule()
    if ok:
        console.print('[bold green]All checks passed.[/bold green]')
    else:
        console.print('[bold red]Some checks failed — see above.[/bold red]')
        sys.exit(1)

def _spinner(message: str, verbose: bool):
    if verbose:
        return Progress(SpinnerColumn(), TextColumn(message), transient=True)
    from contextlib import nullcontext
    return nullcontext()

def _completeness_bar(score: float, width: int=20) -> str:
    filled = int(score * width)
    bar = '█' * filled + '░' * (width - filled)
    color = 'green' if score >= 0.7 else 'yellow' if score >= 0.4 else 'red'
    return f'[{color}]{bar}[/{color}]'