from pathlib import Path

import pytest

from fireform.schema import CasualtyRecord, IncidentReport, IncidentType


@pytest.fixture
def sample_structure_fire() -> IncidentReport:
    from datetime import datetime
    return IncidentReport(incident_number='2025-001', incident_type=IncidentType.STRUCTURE_FIRE.value, date_time=datetime(2025, 3, 15, 2, 0, 0), address='14 Maple Street', city='Springfield', state='IL', zip_code='62701', narrative='Engine 3 responded to a residential structure fire at 14 Maple Street. Flames visible from second floor on arrival. Two occupants located and rescued via ground ladder. One occupant treated for smoke inhalation.', property_use='residential_1family', alarm_source='phone_911', occupants_rescued=2, area_of_origin='Kitchen', cause_of_ignition='Unattended cooking', contributing_factors=['unattended stove', 'no smoke alarm'], estimated_loss_usd=45000.0, casualties=CasualtyRecord(civilian_injuries=1, civilian_fatalities=0, treated_on_scene=True))

@pytest.fixture
def sample_medical() -> IncidentReport:
    return IncidentReport(incident_type=IncidentType.MEDICAL.value, address='55 Oak Avenue', city='Springfield', narrative='Cardiac arrest. CPR administered on scene. AED used. Patient transported.', occupants_rescued=1, casualties=CasualtyRecord(civilian_injuries=1, treated_on_scene=False))

@pytest.fixture
def minimal_report() -> IncidentReport:
    return IncidentReport(incident_type='false_alarm', address='100 Test Street', narrative='Automatic alarm activation, no fire found on inspection.')

@pytest.fixture
def nfirs_template_path(tmp_path) -> Path:
    src = Path('config/templates/nfirs_basic.yaml')
    dst = tmp_path / 'nfirs_basic.yaml'
    if src.exists():
        dst.write_text(src.read_text())
    else:
        dst.write_text('template_id: nfirs_basic\ntemplate_name: NFIRS Basic Module\npdf_path: config/pdfs/nfirs_basic.pdf\nfield_mappings:\n  - pdf_field: StreetAddress\n    source: address\n')
    return dst