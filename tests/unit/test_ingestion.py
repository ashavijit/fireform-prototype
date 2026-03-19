from unittest.mock import MagicMock, patch

import pytest

from fireform.ingestion import IncidentInput


@pytest.fixture
def ingestion():
    return IncidentInput(whisper_model='base')

def test_from_text_strips_whitespace(ingestion):
    result = ingestion.from_text('  Called to 14 Maple St.  ')
    assert result == 'Called to 14 Maple St.'

def test_from_text_empty_raises(ingestion):
    with pytest.raises(ValueError, match='empty'):
        ingestion.from_text('')

def test_ingest_plain_string(ingestion):
    result = ingestion.ingest('Structure fire at 14 Maple St.')
    assert result == 'Structure fire at 14 Maple St.'

def test_from_text_file(ingestion, tmp_path):
    f = tmp_path / 'incident.txt'
    f.write_text('Called to 55 Oak Ave, cardiac arrest.')
    result = ingestion.from_text_file(f)
    assert 'cardiac' in result

def test_from_text_file_not_found(ingestion):
    with pytest.raises(FileNotFoundError):
        ingestion.from_text_file('/nonexistent/path/file.txt')

def test_ingest_txt_file_auto_detected(ingestion, tmp_path):
    f = tmp_path / 'desc.txt'
    f.write_text('Hazmat spill at industrial facility.')
    result = ingestion.ingest(f)
    assert 'Hazmat' in result

def test_from_audio_calls_whisper(ingestion, tmp_path):
    audio = tmp_path / 'incident.wav'
    audio.write_bytes(b'fake wav data')
    mock_model = MagicMock()
    mock_model.transcribe.return_value = {'text': '  Structure fire on Elm Street.  '}
    with patch.object(ingestion, '_load_whisper', return_value=mock_model):
        result = ingestion.from_audio(audio)
    assert result == 'Structure fire on Elm Street.'
    mock_model.transcribe.assert_called_once_with(str(audio))

def test_from_audio_not_found(ingestion):
    with pytest.raises(FileNotFoundError):
        ingestion.from_audio('/no/such/file.wav')

def test_ingest_detects_audio_extension(ingestion, tmp_path):
    for ext in ['.wav', '.mp3', '.m4a', '.ogg', '.flac']:
        audio = tmp_path / f'incident{ext}'
        audio.write_bytes(b'fake')
        mock_model = MagicMock()
        mock_model.transcribe.return_value = {'text': f'Test {ext}'}
        with patch.object(ingestion, '_load_whisper', return_value=mock_model):
            result = ingestion.ingest(audio)
        assert f'Test {ext}' == result

def test_whisper_not_loaded_for_text_input(ingestion):
    ingestion.ingest('Plain text description.')
    assert ingestion._whisper is None

def test_whisper_import_error_gives_clear_message(ingestion, tmp_path):
    audio = tmp_path / 'incident.wav'
    audio.write_bytes(b'fake')
    with patch('builtins.__import__', side_effect=ImportError('no module')):
        pass
    with patch.object(ingestion, '_whisper', None):
        with patch('fireform.ingestion.IncidentInput._load_whisper', side_effect=ImportError('Whisper is required')):
            with pytest.raises(ImportError, match='Whisper'):
                ingestion.from_audio(audio)