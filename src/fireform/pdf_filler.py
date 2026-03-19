from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import fitz
import yaml

from .schema import IncidentReport

logger = logging.getLogger(__name__)

class PDFFiller:

    def __init__(self, template_config_path: str | Path) -> None:
        self.config_path = Path(template_config_path)
        if not self.config_path.exists():
            raise FileNotFoundError(f'Template config not found: {self.config_path}')
        with self.config_path.open() as f:
            self.config: dict = yaml.safe_load(f)
        self.template_id = self.config.get('template_id', 'unknown')
        self.template_name = self.config.get('template_name', 'Unknown Template')
        self.pdf_path = Path(self.config.get('pdf_path', ''))
        self.field_mappings: list[dict] = self.config.get('field_mappings', [])

    def fill(self, report: IncidentReport, output_path: str | Path) -> Path:
        if not self.pdf_path.exists():
            raise FileNotFoundError(f'PDF template not found: {self.pdf_path}. Place the agency PDF at this path.')
        doc = fitz.open(str(self.pdf_path))
        filled_count = 0
        for page in doc:
            for widget in page.widgets():
                if not widget.field_name:
                    continue
                mapping = self._find_mapping(widget.field_name)
                if not mapping:
                    continue
                raw_value = self._get_value(report, mapping['source'])
                if raw_value is None:
                    continue
                value = self._apply_transform(raw_value, mapping.get('transform', ''), mapping)
                widget.field_value = value
                widget.update()
                filled_count += 1
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(out))
        doc.close()
        logger.info('Filled %d/%d fields → %s', filled_count, len(self.field_mappings), out)
        return out

    def list_pdf_fields(self) -> list[str]:
        doc = fitz.open(str(self.pdf_path))
        names = []
        for page in doc:
            for widget in page.widgets():
                if widget.field_name:
                    names.append(widget.field_name)
        doc.close()
        return names

    def _find_mapping(self, pdf_field_name: str) -> dict | None:
        return next((m for m in self.field_mappings if m.get('pdf_field') == pdf_field_name), None)

    @staticmethod
    def _get_value(report: IncidentReport, source: str) -> Any | None:
        parts = source.split('.')
        obj: Any = report
        for part in parts:
            obj = getattr(obj, part, None)
            if obj is None:
                return None
        return obj

    @staticmethod
    def _apply_transform(value: Any, transform: str, mapping: dict) -> str:
        if not transform:
            return str(value) if value is not None else ''
        if transform.startswith('date_format:'):
            fmt = transform.split(':', 1)[1]
            try:
                if isinstance(value, datetime):
                    return value.strftime(fmt)
                return datetime.fromisoformat(str(value)).strftime(fmt)
            except (ValueError, TypeError):
                return str(value)
        if transform == 'enum_map':
            enum_map: dict = mapping.get('enum_map', {})
            return enum_map.get(str(value), str(value))
        if transform == 'to_string':
            return str(value)
        if transform.startswith('max_chars:'):
            n = int(transform.split(':', 1)[1])
            return str(value)[:n]
        if transform.startswith('concat:'):
            sep = transform.split(':', 1)[1]
            if isinstance(value, list):
                return sep.join(str(v) for v in value)
            return str(value)
        if transform == 'bool_yn':
            return 'Yes' if value else 'No'
        if transform == 'upper':
            return str(value).upper()
        return str(value)