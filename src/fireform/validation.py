from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Optional
from .schema import IncidentReport, IncidentType
logger = logging.getLogger(__name__)

@dataclass
class ValidationResult:
    is_valid: bool
    report: Optional[IncidentReport] = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    completeness_score: float = 0.0

    def __str__(self) -> str:
        status = 'VALID' if self.is_valid else 'INVALID'
        lines = [f'[{status}] completeness={self.completeness_score:.0%}']
        for e in self.errors:
            lines.append(f'  ERROR:   {e}')
        for w in self.warnings:
            lines.append(f'  WARNING: {w}')
        return '\n'.join(lines)
_NFIRS_REQUIRED = ['incident_type', 'address', 'narrative']
_SCORED_FIELDS = ['incident_number', 'date_time', 'city', 'state', 'zip_code', 'property_use', 'alarm_source', 'occupants_rescued', 'area_of_origin', 'cause_of_ignition', 'contributing_factors', 'estimated_loss_usd', 'casualties', 'resources']
_NO_LOSS_TYPES = {IncidentType.MEDICAL, IncidentType.FALSE_ALARM, IncidentType.SERVICE_CALL}

class ReportValidator:

    def validate(self, report: IncidentReport) -> ValidationResult:
        errors: list[str] = []
        warnings: list[str] = []
        for f in _NFIRS_REQUIRED:
            val = getattr(report, f, None)
            if val is None or val == '' or val == []:
                errors.append(f"NFIRS required field missing: '{f}'")
        if report.casualties and report.occupants_rescued is not None:
            total_cas = report.casualties.total_casualties
            if total_cas > report.occupants_rescued + 5:
                warnings.append(f'Casualty count ({total_cas}) greatly exceeds rescued occupants ({report.occupants_rescued}) — please verify.')
        if report.estimated_loss_usd is not None and report.incident_type in {t.value for t in _NO_LOSS_TYPES}:
            warnings.append(f"'estimated_loss_usd' is unusual for incident type '{report.incident_type}' — verify this is intentional.")
        fire_types = {IncidentType.STRUCTURE_FIRE.value, IncidentType.VEHICLE_FIRE.value}
        if report.incident_type in fire_types and report.property_use is None:
            warnings.append('Property use is recommended for structure/vehicle fires (NFIRS field).')
        if report.occupants_rescued > 2 and (not report.resources):
            warnings.append('Multiple occupants rescued but no resources listed — consider adding responding units.')
        scored = sum((1 for f in _SCORED_FIELDS if _is_populated(getattr(report, f, None))))
        score = scored / len(_SCORED_FIELDS)
        if score < 0.4:
            warnings.append(f'Report completeness is low ({score:.0%}). Consider adding more details for a stronger record.')
        is_valid = len(errors) == 0
        logger.info('Validation complete — valid=%s errors=%d warnings=%d score=%.0f%%', is_valid, len(errors), len(warnings), score * 100)
        return ValidationResult(is_valid=is_valid, report=report if is_valid else None, errors=errors, warnings=warnings, completeness_score=score)

def _is_populated(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, (list, dict)):
        return len(value) > 0
    if isinstance(value, str):
        return value.strip() != ''
    if isinstance(value, (int, float)):
        return value != 0
    return True