from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None

@dataclass
class FireFormConfig:
    default_model: str = 'llama3'
    ollama_url: str = 'http://localhost:11434'
    default_templates: list[str] = field(default_factory=lambda: ['nfirs_basic'])
    output_dir: str = './output'
    whisper_model: str = 'base'
    templates_dir: str = 'config/templates'
    max_retries: int = 2

    @classmethod
    def load(cls, start_path: Path | None=None) -> FireFormConfig:
        pyproject = cls._find_pyproject(start_path or Path.cwd())
        if pyproject is None or tomllib is None:
            logger.debug('No pyproject.toml found or tomllib unavailable — using defaults.')
            return cls()
        try:
            with pyproject.open('rb') as f:
                data = tomllib.load(f)
        except Exception as exc:
            logger.warning('Failed to parse pyproject.toml: %s — using defaults.', exc)
            return cls()
        ff_config = data.get('tool', {}).get('fireform', {})
        if not ff_config:
            return cls()
        return cls(default_model=ff_config.get('default_model', cls.default_model), ollama_url=ff_config.get('ollama_url', cls.ollama_url), default_templates=ff_config.get('default_templates', cls.default_templates), output_dir=ff_config.get('output_dir', cls.output_dir), whisper_model=ff_config.get('whisper_model', cls.whisper_model), templates_dir=ff_config.get('templates_dir', cls.templates_dir), max_retries=ff_config.get('max_retries', cls.max_retries))

    @staticmethod
    def _find_pyproject(start: Path) -> Path | None:
        for directory in [start, *start.parents]:
            candidate = directory / 'pyproject.toml'
            if candidate.exists():
                return candidate
        return None