import pytest
from fireform.schema import CasualtyRecord, IncidentReport, IncidentType
from fireform.validation import ReportValidator

@pytest.fixture
def validator():
    return ReportValidator()

def _make_report(**kwargs) -> IncidentReport:
    defaults = dict(incident_type='structure_fire', address='14 Maple Street', narrative='Residential structure fire. Two occupants rescued.')
    defaults.update(kwargs)
    return IncidentReport(**defaults)

def test_valid_minimal_report_passes(validator):
    r = _make_report()
    result = validator.validate(r)
    assert result.is_valid
    assert result.errors == []

def test_completeness_score_is_between_0_and_1(validator):
    r = _make_report()
    result = validator.validate(r)
    assert 0.0 <= result.completeness_score <= 1.0

def test_fully_populated_report_has_high_completeness(validator):
    from datetime import datetime
    r = _make_report(incident_number='2025-001', date_time=datetime(2025, 3, 15, 2, 0, 0), city='Springfield', state='IL', zip_code='62701', property_use='residential_1family', alarm_source='phone_911', occupants_rescued=2, area_of_origin='Kitchen', cause_of_ignition='Unattended cooking', contributing_factors=['unattended stove'], estimated_loss_usd=45000, casualties=CasualtyRecord(civilian_injuries=1), resources=[])
    result = validator.validate(r)
    assert result.completeness_score >= 0.7

def test_missing_address_produces_error(validator):
    r = _make_report()
    r.__dict__['address'] = ''
    result = validator.validate(r)
    assert not result.is_valid
    assert any(('address' in e for e in result.errors))

def test_missing_narrative_produces_error(validator):
    r = _make_report()
    r.__dict__['narrative'] = ''
    result = validator.validate(r)
    assert not result.is_valid
    assert any(('narrative' in e for e in result.errors))

def test_casualty_exceeds_rescued_produces_warning(validator):
    r = _make_report(occupants_rescued=1, casualties=CasualtyRecord(civilian_injuries=10, civilian_fatalities=5))
    result = validator.validate(r)
    assert result.is_valid
    assert any(('casualty' in w.lower() or 'exceed' in w.lower() for w in result.warnings))

def test_financial_loss_on_medical_call_produces_warning(validator):
    r = _make_report(incident_type='medical', estimated_loss_usd=50000)
    result = validator.validate(r)
    assert any(('estimated_loss' in w or 'loss' in w.lower() for w in result.warnings))

def test_structure_fire_without_property_use_warns(validator):
    r = _make_report(incident_type='structure_fire', property_use=None)
    result = validator.validate(r)
    assert any(('property use' in w.lower() for w in result.warnings))

def test_result_str_valid(validator):
    r = _make_report()
    result = validator.validate(r)
    text = str(result)
    assert 'VALID' in text

def test_result_str_invalid(validator):
    r = _make_report()
    r.__dict__['address'] = ''
    result = validator.validate(r)
    text = str(result)
    assert 'INVALID' in text
    assert 'ERROR' in text