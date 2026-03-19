import pytest
from pydantic import ValidationError
from fireform.schema import CasualtyRecord, IncidentReport, IncidentType

def test_minimal_valid_report():
    r = IncidentReport(incident_type='structure_fire', address='14 Maple Street', narrative='Residential structure fire. Two occupants rescued.')
    assert r.incident_type == 'structure_fire'
    assert r.address == '14 Maple Street'
    assert r.occupants_rescued == 0

def test_full_report_construction():
    r = IncidentReport(incident_type='medical', address='55 Oak Ave', narrative='Cardiac arrest, CPR administered.', city='Springfield', state='IL', occupants_rescued=1, casualties=CasualtyRecord(civilian_injuries=1, treated_on_scene=True))
    assert r.casualties.civilian_injuries == 1
    assert r.casualties.treated_on_scene is True
    assert r.casualties.total_casualties == 1

def test_invalid_incident_type_raises():
    with pytest.raises(ValidationError):
        IncidentReport(incident_type='explosion', address='1 Main St', narrative='Test.')

def test_all_incident_types_valid():
    for it in IncidentType:
        r = IncidentReport(incident_type=it.value, address='Test Address', narrative='Test narrative for type validation.')
        assert r.incident_type == it.value

def test_short_address_raises():
    with pytest.raises(ValidationError):
        IncidentReport(incident_type='rescue', address='AB', narrative='Test.')

def test_short_narrative_raises():
    with pytest.raises(ValidationError):
        IncidentReport(incident_type='rescue', address='123 Main St', narrative='Short')

def test_negative_occupants_rescued_raises():
    with pytest.raises(ValidationError):
        IncidentReport(incident_type='rescue', address='123 Main St', narrative='Test narrative text.', occupants_rescued=-1)

def test_model_json_schema_contains_required_fields():
    schema = IncidentReport.model_json_schema()
    required = schema.get('required', [])
    assert 'incident_type' in required
    assert 'address' in required
    assert 'narrative' in required

def test_model_json_schema_is_embeddable():
    import json
    schema = IncidentReport.model_json_schema()
    dumped = json.dumps(schema)
    assert len(dumped) > 100

def test_casualty_total_casualties():
    c = CasualtyRecord(civilian_injuries=2, civilian_fatalities=1, responder_injuries=1, responder_fatalities=0)
    assert c.total_casualties == 4

def test_casualty_negative_values_raise():
    with pytest.raises(ValidationError):
        CasualtyRecord(civilian_injuries=-1)