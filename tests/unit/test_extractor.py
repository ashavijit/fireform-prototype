import json
from unittest.mock import MagicMock, patch

import pytest

from fireform.extractor import LLMExtractor
from fireform.schema import IncidentReport, IncidentType

STRUCTURE_FIRE_RESPONSE = json.dumps({'incident_type': 'structure_fire', 'address': '14 Maple Street', 'city': 'Springfield', 'narrative': 'Residential structure fire. Two occupants rescued from second floor.', 'occupants_rescued': 2, 'casualties': {'civilian_injuries': 1, 'civilian_fatalities': 0, 'responder_injuries': 0, 'responder_fatalities': 0, 'treated_on_scene': True}})
MEDICAL_RESPONSE = json.dumps({'incident_type': 'medical', 'address': '55 Oak Avenue', 'narrative': 'Cardiac arrest. CPR administered. Patient transported.', 'occupants_rescued': 1})

def _mock_post(response_text: str):
    mock = MagicMock()
    mock.return_value.json.return_value = {'response': response_text}
    mock.return_value.raise_for_status.return_value = None
    return mock

@pytest.fixture
def extractor():
    return LLMExtractor(model='llama3', max_retries=2)

def test_extract_structure_fire(extractor):
    with patch('httpx.post', _mock_post(STRUCTURE_FIRE_RESPONSE)):
        r = extractor.extract('Called to 14 Maple St, structure fire, 2 rescued.')
    assert r.incident_type == IncidentType.STRUCTURE_FIRE.value
    assert r.address == '14 Maple Street'
    assert r.occupants_rescued == 2
    assert r.casualties.civilian_injuries == 1

def test_extract_medical(extractor):
    with patch('httpx.post', _mock_post(MEDICAL_RESPONSE)):
        r = extractor.extract('55 Oak Ave, cardiac arrest.')
    assert r.incident_type == IncidentType.MEDICAL.value
    assert r.occupants_rescued == 1

def test_strip_markdown_fences(extractor):
    fenced = f'```json\n{STRUCTURE_FIRE_RESPONSE}\n```'
    with patch('httpx.post', _mock_post(fenced)):
        r = extractor.extract('Test incident.')
    assert isinstance(r, IncidentReport)

def test_strip_preamble_before_brace(extractor):
    with_preamble = 'Here is the JSON:\n' + STRUCTURE_FIRE_RESPONSE
    with patch('httpx.post', _mock_post(with_preamble)):
        r = extractor.extract('Test incident.')
    assert r.incident_type == 'structure_fire'

def test_retries_on_json_error(extractor):
    responses = ['this is not json', STRUCTURE_FIRE_RESPONSE]
    side_effects = [MagicMock(**{'json.return_value': {'response': r}, 'raise_for_status.return_value': None}) for r in responses]
    with patch('httpx.post', side_effect=side_effects) as mock_post:
        r = extractor.extract('Test incident.')
    assert r.incident_type == 'structure_fire'
    assert mock_post.call_count == 2

def test_retries_on_validation_error(extractor):
    invalid = json.dumps({'address': '14 Maple St'})
    responses = [invalid, STRUCTURE_FIRE_RESPONSE]
    side_effects = [MagicMock(**{'json.return_value': {'response': r}, 'raise_for_status.return_value': None}) for r in responses]
    with patch('httpx.post', side_effect=side_effects):
        r = extractor.extract('Test incident.')
    assert r.incident_type == 'structure_fire'

def test_raises_after_all_retries_exhausted(extractor):
    mock = MagicMock(**{'return_value.json.return_value': {'response': 'bad json'}, 'return_value.raise_for_status.return_value': None})
    with patch('httpx.post', mock), pytest.raises(RuntimeError, match='extraction failed'):
        extractor.extract('Test incident.')
    assert mock.call_count == 3

def test_correction_prompt_contains_error(extractor):
    invalid = 'not json'
    calls_made = []

    def capture_post(url, **kwargs):
        calls_made.append(kwargs.get('json', {}).get('prompt', ''))
        if len(calls_made) == 1:
            return MagicMock(**{'json.return_value': {'response': invalid}, 'raise_for_status.return_value': None})
        return MagicMock(**{'json.return_value': {'response': STRUCTURE_FIRE_RESPONSE}, 'raise_for_status.return_value': None})
    with patch('httpx.post', side_effect=capture_post):
        extractor.extract('Original incident description here.')
    assert len(calls_made) == 2
    assert 'error' in calls_made[1].lower() or 'fix' in calls_made[1].lower()

def test_raises_on_ollama_connection_error(extractor):
    import httpx as _httpx
    with patch('httpx.post', side_effect=_httpx.ConnectError('refused')):
        with pytest.raises(RuntimeError, match='Cannot connect to Ollama'):
            extractor.extract('Test incident.')

def test_schema_embedded_in_system_prompt(extractor):
    captured_system = []

    def capture(url, **kwargs):
        captured_system.append(kwargs.get('json', {}).get('system', ''))
        return MagicMock(**{'json.return_value': {'response': STRUCTURE_FIRE_RESPONSE}, 'raise_for_status.return_value': None})
    with patch('httpx.post', side_effect=capture):
        extractor.extract('Test.')
    assert 'incident_type' in captured_system[0]
    assert 'IncidentReport' in captured_system[0] or 'properties' in captured_system[0]