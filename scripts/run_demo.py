from __future__ import annotations
import argparse
import json
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
from fireform.extractor import LLMExtractor
from fireform.ingestion import IncidentInput
from fireform.schema import IncidentReport
from fireform.validation import ReportValidator
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich import print as rprint
    console = Console()
    USE_RICH = True
except ImportError:
    USE_RICH = False
    console = None
CASES_DIR = Path(__file__).parent.parent / 'demo' / 'cases'
MOCK_RESPONSES: dict[str, dict] = {'demo_001': {'incident_type': 'structure_fire', 'address': '14 Maple Street', 'city': 'Springfield', 'state': 'IL', 'narrative': 'Residential structure fire. Two occupants rescued from second floor via ground ladder.', 'occupants_rescued': 2, 'property_use': 'residential_1family', 'alarm_source': 'phone_911', 'area_of_origin': 'Kitchen', 'cause_of_ignition': 'Unattended cooking', 'contributing_factors': ['unattended stove'], 'estimated_loss_usd': 45000, 'casualties': {'civilian_injuries': 1, 'civilian_fatalities': 0, 'responder_injuries': 0, 'responder_fatalities': 0, 'treated_on_scene': True}}, 'demo_002': {'incident_type': 'medical', 'address': '55 Oak Avenue', 'city': 'Springfield', 'narrative': 'Cardiac arrest. CPR and AED applied. ROSC achieved. Patient transported critical.', 'occupants_rescued': 1, 'casualties': {'civilian_injuries': 1, 'civilian_fatalities': 0, 'responder_injuries': 0, 'responder_fatalities': 0, 'treated_on_scene': False}}, 'demo_003': {'incident_type': 'hazmat', 'address': 'Industrial Park, Unit 7', 'city': 'Riverdale', 'narrative': 'Toluene drum with failing seal, ~8 gallons released. Area evacuated, drum overpacked.', 'property_use': 'industrial', 'occupants_rescued': 0, 'contributing_factors': ['improper storage', 'container failure']}, 'demo_004': {'incident_type': 'vehicle_fire', 'address': 'I-90 westbound mile marker 42', 'narrative': 'Fully involved vehicle fire. Occupant self-extricated. Fire extinguished.', 'occupants_rescued': 0}, 'demo_005': {'incident_type': 'false_alarm', 'address': '220 Commerce Boulevard', 'city': 'Springfield', 'narrative': 'Automatic alarm activation. Faulty duct detector in HVAC unit. No fire found.', 'property_use': 'commercial', 'occupants_rescued': 0}}

def run_case(case_file: Path, live: bool) -> dict:
    case = json.loads(case_file.read_text())
    case_id = case['id']
    description = case['description']
    _print(f"\n{'─' * 60}")
    _print(f"  Case {case_id}: {case['notes']}")
    _print(f"{'─' * 60}")
    _print(f'  Input ({len(description)} chars):\n  {description[:140]}…')
    t0 = time.perf_counter()
    text = IncidentInput().ingest(description)
    extractor = LLMExtractor(model='llama3', max_retries=2)
    if live:
        report = extractor.extract(text)
    else:
        mock_response = json.dumps(MOCK_RESPONSES[case_id])
        mock_post = MagicMock(**{'return_value.json.return_value': {'response': mock_response}, 'return_value.raise_for_status.return_value': None})
        with patch('httpx.post', mock_post):
            report = extractor.extract(text)
    elapsed = time.perf_counter() - t0
    result = ReportValidator().validate(report)
    expected = case.get('expected_fields', {})
    passed, failed = ([], [])
    for field, expected_val in expected.items():
        actual = getattr(report, field, None)
        if actual == expected_val:
            passed.append(field)
        else:
            failed.append((field, expected_val, actual))
    _print(f'\n  Extracted ({elapsed:.1f}s):')
    _print(f'    incident_type     : {report.incident_type}')
    _print(f'    address           : {report.address}')
    _print(f"    city              : {report.city or '—'}")
    _print(f'    occupants_rescued : {report.occupants_rescued}')
    _print(f'    narrative         : {report.narrative[:80]}…')
    status = '✓ VALID' if result.is_valid else '✗ INVALID'
    _print(f'\n  Validation: {status}  |  completeness={result.completeness_score:.0%}')
    for w in result.warnings:
        _print(f'    ⚠  {w}')
    if failed:
        _print(f'\n  Field check failures:')
        for field, exp, got in failed:
            _print(f'    ✗  {field}: expected={exp!r}, got={got!r}')
    else:
        _print(f'  Field checks: {len(passed)}/{len(expected)} passed ✓')
    return {'case_id': case_id, 'valid': result.is_valid, 'completeness': result.completeness_score, 'field_checks_passed': len(passed), 'field_checks_total': len(expected), 'elapsed': elapsed}

def _print(msg: str) -> None:
    if USE_RICH:
        console.print(msg)
    else:
        print(msg)

def main() -> None:
    parser = argparse.ArgumentParser(description='FireForm prototype demo')
    parser.add_argument('--live', action='store_true', help='Use real Ollama (must be running)')
    parser.add_argument('--case', type=int, help='Run only this case number (1–5)')
    args = parser.parse_args()
    mode = 'LIVE (Ollama)' if args.live else 'MOCK (offline)'
    _print(f"\n{'═' * 60}")
    _print(f'  FireForm Prototype — Pipeline Demo')
    _print(f'  Mode: {mode}')
    _print(f"{'═' * 60}")
    case_files = sorted(CASES_DIR.glob('*.json'))
    if args.case:
        case_files = [f for f in case_files if f.name.startswith(f'0{args.case}_')]
    if not case_files:
        _print('No matching case files found.')
        sys.exit(1)
    results = []
    for cf in case_files:
        try:
            r = run_case(cf, live=args.live)
            results.append(r)
        except Exception as exc:
            _print(f'\n  ERROR in {cf.name}: {exc}')
            results.append({'case_id': cf.stem, 'valid': False, 'error': str(exc)})
    _print(f"\n{'═' * 60}")
    _print(f"  Summary: {sum((r.get('valid', False) for r in results))}/{len(results)} cases valid")
    avg_score = sum((r.get('completeness', 0) for r in results)) / len(results)
    _print(f'  Average completeness score: {avg_score:.0%}')
    avg_time = sum((r.get('elapsed', 0) for r in results)) / len(results)
    _print(f'  Average extraction time:   {avg_time:.1f}s')
    _print(f"{'═' * 60}\n")
if __name__ == '__main__':
    main()