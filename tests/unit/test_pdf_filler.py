from datetime import datetime

import pytest

from fireform.pdf_filler import PDFFiller
from fireform.schema import CasualtyRecord, IncidentReport


class TestTransforms:

    def test_to_string(self):
        assert PDFFiller._apply_transform(42, 'to_string', {}) == '42'

    def test_upper(self):
        assert PDFFiller._apply_transform('il', 'upper', {}) == 'IL'

    def test_max_chars_truncates(self):
        result = PDFFiller._apply_transform('Hello World', 'max_chars:5', {})
        assert result == 'Hello'

    def test_max_chars_no_truncation_when_short(self):
        result = PDFFiller._apply_transform('Hi', 'max_chars:100', {})
        assert result == 'Hi'

    def test_date_format_from_datetime(self):
        dt = datetime(2025, 3, 15, 14, 30, 0)
        assert PDFFiller._apply_transform(dt, 'date_format:%m/%d/%Y', {}) == '03/15/2025'
        assert PDFFiller._apply_transform(dt, 'date_format:%H%M', {}) == '1430'

    def test_date_format_from_iso_string(self):
        result = PDFFiller._apply_transform('2025-03-15T14:30:00', 'date_format:%Y-%m-%d', {})
        assert result == '2025-03-15'

    def test_enum_map_known_value(self):
        mapping = {'enum_map': {'structure_fire': '111', 'medical': '300'}}
        assert PDFFiller._apply_transform('structure_fire', 'enum_map', mapping) == '111'

    def test_enum_map_unknown_value_passthrough(self):
        mapping = {'enum_map': {'structure_fire': '111'}}
        assert PDFFiller._apply_transform('other', 'enum_map', mapping) == 'other'

    def test_concat_list(self):
        result = PDFFiller._apply_transform(['unattended stove', 'no sprinkler'], 'concat:; ', {})
        assert result == 'unattended stove; no sprinkler'

    def test_concat_non_list(self):
        result = PDFFiller._apply_transform('single item', 'concat:; ', {})
        assert result == 'single item'

    def test_bool_yn_true(self):
        assert PDFFiller._apply_transform(True, 'bool_yn', {}) == 'Yes'

    def test_bool_yn_false(self):
        assert PDFFiller._apply_transform(False, 'bool_yn', {}) == 'No'

    def test_no_transform_returns_string(self):
        assert PDFFiller._apply_transform(123, '', {}) == '123'

    def test_unknown_transform_returns_string(self):
        assert PDFFiller._apply_transform('hello', 'unknown_op', {}) == 'hello'

class TestGetValue:

    def _report(self):
        return IncidentReport(incident_type='structure_fire', address='14 Maple St', narrative='Test narrative text here.', occupants_rescued=2, casualties=CasualtyRecord(civilian_injuries=1))

    def test_top_level_field(self):
        r = self._report()
        assert PDFFiller._get_value(r, 'address') == '14 Maple St'

    def test_nested_field(self):
        r = self._report()
        assert PDFFiller._get_value(r, 'casualties.civilian_injuries') == 1

    def test_missing_nested_returns_none(self):
        r = IncidentReport(incident_type='medical', address='55 Oak Ave', narrative='Test narrative text here.', casualties=None)
        assert PDFFiller._get_value(r, 'casualties.civilian_injuries') is None

    def test_nonexistent_field_returns_none(self):
        r = self._report()
        assert PDFFiller._get_value(r, 'nonexistent_field') is None

def test_filler_raises_on_missing_config():
    with pytest.raises(FileNotFoundError, match='Template config not found'):
        PDFFiller('/nonexistent/template.yaml')

def test_filler_loads_valid_config(tmp_path):
    tpl = tmp_path / 'test.yaml'
    tpl.write_text('template_id: test\ntemplate_name: Test Template\npdf_path: test.pdf\nfield_mappings: []\n')
    filler = PDFFiller(tpl)
    assert filler.template_id == 'test'
    assert filler.field_mappings == []