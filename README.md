# FireForm — Prototype

> **Report once, file everywhere.**
> AI-powered incident report automation for first responders.

[![CI](https://github.com/ashavijit/fireform-prototype/actions/workflows/ci.yml/badge.svg)](https://github.com/ashavijit/fireform-prototype/actions)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

This is a working prototype of the [FireForm](https://github.com/juanalvv/FireForm) pipeline,
built as part of my Google Summer of Code 2025 proposal.

FireForm converts a single voice memo or text description into filled agency-specific PDF forms —
running entirely on-device, with no data leaving the organisation's network.

---

## Quick start

```bash
git clone https://github.com/ashavijit/fireform-prototype
cd fireform-prototype
pip install -e ".[dev]"

make demo

make test
```

## Demo output

```
════════════════════════════════════════════════════════════
  FireForm Prototype — Pipeline Demo
  Mode: MOCK (offline)
════════════════════════════════════════════════════════════

  Case demo_001: Classic residential structure fire with rescue

  Input (498 chars):
  Engine 3 and Ladder 7 responded to a reported residential structure
  fire at 14 Maple Street at approximately 0200 hours...

  Extracted (0.0s):
    incident_type     : structure_fire
    address           : 14 Maple Street
    city              : Springfield
    occupants_rescued : 2
    narrative         : Residential structure fire. Two occupants rescued…

  Validation: ✓ VALID  |  completeness=79%
  Field checks: 5/5 passed ✓

  [... 4 more cases ...]

════════════════════════════════════════════════════════════
  Summary: 5/5 cases valid
  Average completeness score: 71%
  Average extraction time:   0.0s
════════════════════════════════════════════════════════════
```

## Architecture

```
Voice/Text input
      │
      ▼
┌─────────────────┐
│  IncidentInput  │  ← Whisper ASR (local, offline)
└────────┬────────┘
         │ raw text
         ▼
┌─────────────────┐
│  LLMExtractor   │  ← Ollama (Llama 3 / Mistral, local)
│  + retry loop   │    schema-guided JSON extraction
└────────┬────────┘
         │ IncidentReport (Pydantic)
         ▼
┌─────────────────┐
│ ReportValidator │  ← NFIRS rules + completeness score
└────────┬────────┘
         │ validated JSON
         ▼
┌─────────────────┐
│   PDFFiller     │  ← YAML template mapping + PyMuPDF
└────────┬────────┘
         │
         ▼
  Filled PDFs (NFIRS Basic, Local FD form, any agency)
```

All processing is **on-device** — no incident data ever leaves the machine.

## Project structure

```
src/fireform/
  __init__.py       — version info
  schema.py         — IncidentReport Pydantic model
  ingestion.py      — text + voice (Whisper) input
  extractor.py      — Ollama LLM extraction with retry
  validation.py     — NFIRS rules + completeness scoring
  pdf_filler.py     — YAML-driven PDF AcroForm auto-fill
  config.py         — pyproject.toml config loader
  cli.py            — Click CLI (fireform report, validate, doctor…)

config/templates/
  nfirs_basic.yaml        — NFIRS Basic Module (~40 fields)
  local_fd_form.yaml      — Generic local FD form (example)

tests/
  unit/                   — fully mocked, no Ollama needed
  integration/            — full pipeline, Ollama mocked at HTTP level

demo/cases/               — 5 labelled incident descriptions + expected fields
scripts/run_demo.py       — standalone demo runner
```

## CLI usage

```bash
fireform report "Called to 14 Maple St, structure fire, 2 rescued" \
  --template nfirs_basic

fireform report incident.wav \
  --template nfirs_basic --template local_fd_form

fireform report description.txt --dry-run --json-out

fireform doctor

fireform list-templates
```

## Adding a new agency form

1. Place the agency's blank PDF in `config/pdfs/your_form.pdf`
2. Create `config/templates/your_form.yaml`:

```yaml
template_id:   your_form
template_name: "Your Department Incident Report"
pdf_path:      "config/pdfs/your_form.pdf"
field_mappings:
  - pdf_field: "DateOfCall"
    source:    "date_time"
    transform: "date_format:%m/%d/%Y"
  - pdf_field: "Location"
    source:    "address"
  - pdf_field: "IncidentSummary"
    source:    "narrative"
    transform: "max_chars:500"
```

3. Run: `fireform report description.txt --template your_form`

No Python required to add a new form — just YAML.

## Running with real Ollama

```bash
brew install ollama        
ollama serve               
ollama pull llama3         

make demo-live

fireform report "14 Maple St structure fire, 2 rescued" --model llama3
```

## Test coverage

```bash
make test          
make test-unit     
make lint          
make typecheck     
```

## About this prototype

Built by **Avijit Sen** as part of a GSoC 2025 proposal for the
[FireForm](https://github.com/juanalvv/FireForm) project.

- GitHub: [github.com/ashavijit](https://github.com/ashavijit)
- pyxios (published Python library): [github.com/ashavijit/pyxios](https://github.com/ashavijit/pyxios)
- pymgr (Python env manager in Rust): [github.com/ashavijit/pymgr](https://github.com/ashavijit/pymgr)

## License

MIT
