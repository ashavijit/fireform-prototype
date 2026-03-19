from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from fireform.extractor import LLMExtractor
from fireform.ingestion import IncidentInput
from fireform.schema import IncidentReport
from fireform.validation import ReportValidator

STRUCTURE_FIRE_JSON = json.dumps({'incident_type': 'structure_fire', 'address': '14 Maple Street', 'city': 'Springfield', 'state': 'IL', 'narrative': 'Residential structure fire. Two occupants rescued from second floor.', 'occupants_rescued': 2, 'property_use': 'residential_1family', 'alarm_source': 'phone_911', 'casualties': {'civilian_injuries': 1, 'civilian_fatalities': 0, 'responder_injuries': 0, 'responder_fatalities': 0, 'treated_on_scene': True}, 'area_of_origin': 'Kitchen', 'cause_of_ignition': 'Unattended cooking', 'contributing_factors': ['unattended stove'], 'estimated_loss_usd': 45000})
MEDICAL_JSON = json.dumps({'incident_type': 'medical', 'address': '55 Oak Avenue', 'city': 'Springfield', 'narrative': 'Cardiac arrest on scene. CPR administered. Patient transported to hospital.', 'occupants_rescued': 1, 'casualties': {'civilian_injuries': 1, 'civilian_fatalities': 0, 'responder_injuries': 0, 'responder_fatalities': 0, 'treated_on_scene': False}})
HAZMAT_JSON = json.dumps({'incident_type': 'hazmat', 'address': 'Industrial Park, Unit 7', 'city': 'Riverdale', 'narrative': 'Chemical spill at industrial storage facility. Area evacuated.', 'property_use': 'industrial', 'occupants_rescued': 0, 'contributing_factors': ['improper storage', 'container failure']})

def _mock_ollama(response_json: str):
    m = MagicMock()
    m.return_value.json.return_value = {'response': response_json}
    m.return_value.raise_for_status.return_value = None
    return m

class TestTextToValidation:

    def test_structure_fire_full_pipeline(self):
        description = 'Unit 3 called to 14 Maple Street at 0200. Residential structure fire, second floor involvement. Two occupants rescued via ground ladder. One treated for smoke inhalation on scene.'
        with patch('httpx.post', _mock_ollama(STRUCTURE_FIRE_JSON)):
            text = IncidentInput().ingest(description)
            report = LLMExtractor(model='llama3').extract(text)
            result = ReportValidator().validate(report)
        assert result.is_valid
        assert report.incident_type == 'structure_fire'
        assert report.address == '14 Maple Street'
        assert report.occupants_rescued == 2
        assert result.completeness_score > 0.5

    def test_medical_call_pipeline(self):
        description = '55 Oak Avenue — cardiac arrest, CPR given, transported.'
        with patch('httpx.post', _mock_ollama(MEDICAL_JSON)):
            text = IncidentInput().ingest(description)
            report = LLMExtractor(model='llama3').extract(text)
            result = ReportValidator().validate(report)
        assert result.is_valid
        assert report.incident_type == 'medical'
        assert result.errors == []

    def test_hazmat_pipeline(self):
        description = 'Hazmat incident at Industrial Park Unit 7, chemical spill, area evacuated.'
        with patch('httpx.post', _mock_ollama(HAZMAT_JSON)):
            report = LLMExtractor().extract(IncidentInput().ingest(description))
            result = ReportValidator().validate(report)
        assert result.is_valid
        assert report.incident_type == 'hazmat'

    def test_validation_warnings_do_not_block(self):
        medical_with_loss = json.dumps({'incident_type': 'medical', 'address': '55 Oak Ave', 'narrative': 'Cardiac arrest. CPR administered. Patient transported.', 'estimated_loss_usd': 50000})
        with patch('httpx.post', _mock_ollama(medical_with_loss)):
            report = LLMExtractor().extract('55 Oak Ave, cardiac arrest.')
            result = ReportValidator().validate(report)
        assert result.is_valid
        assert len(result.warnings) > 0

class TestVoiceToValidation:

    def test_audio_transcription_feeds_into_extraction(self, tmp_path):
        audio = tmp_path / 'incident.wav'
        audio.write_bytes(b'fake wav data')
        transcribed = 'Called to 14 Maple Street at 0200 hours. Residential structure fire on the second floor.'
        mock_whisper = MagicMock()
        mock_whisper.transcribe.return_value = {'text': transcribed}
        IngestionWithMockedWhisper = IncidentInput.__new__(IncidentInput)
        IngestionWithMockedWhisper._whisper_model_name = 'base'
        IngestionWithMockedWhisper._whisper = mock_whisper
        with patch('httpx.post', _mock_ollama(STRUCTURE_FIRE_JSON)):
            text = IngestionWithMockedWhisper.ingest(audio)
            report = LLMExtractor().extract(text)
            result = ReportValidator().validate(report)
        assert result.is_valid
        mock_whisper.transcribe.assert_called_once()

class TestRetryInPipeline:

    def test_pipeline_succeeds_after_one_bad_response(self):
        responses = ['definitely not json', STRUCTURE_FIRE_JSON]
        side_effects = [MagicMock(**{'json.return_value': {'response': r}, 'raise_for_status.return_value': None}) for r in responses]
        with patch('httpx.post', side_effect=side_effects):
            report = LLMExtractor(max_retries=2).extract('Test incident at 14 Maple St.')
            result = ReportValidator().validate(report)
        assert result.is_valid

    def test_pipeline_raises_after_all_retries(self):
        bad = MagicMock(**{'return_value.json.return_value': {'response': 'not json'}, 'return_value.raise_for_status.return_value': None})
        with patch('httpx.post', bad), pytest.raises(RuntimeError):
            LLMExtractor(max_retries=1).extract('Test incident.')

class TestJsonRoundTrip:

    def test_report_serialises_and_deserialises(self):
        with patch('httpx.post', _mock_ollama(STRUCTURE_FIRE_JSON)):
            original = LLMExtractor().extract('14 Maple St, structure fire.')
        dumped = original.model_dump_json()
        reloaded = IncidentReport.model_validate_json(dumped)
        assert reloaded.incident_type == original.incident_type
        assert reloaded.address == original.address
        assert reloaded.occupants_rescued == original.occupants_rescued

    def test_multiple_incident_types_all_validate(self):
        from fireform.schema import IncidentType
        for it in IncidentType:
            r = IncidentReport(incident_type=it.value, address='100 Test Street', narrative=f'Test incident of type {it.value} for validation smoke test.')
            result = ReportValidator().validate(r)
            assert result.is_valid, f'Failed for incident type: {it.value}'