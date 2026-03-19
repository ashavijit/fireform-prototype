from __future__ import annotations

import json
import logging
import re
import time

import httpx
from pydantic import ValidationError

from .schema import IncidentReport

logger = logging.getLogger(__name__)
_SYSTEM_PROMPT = 'You are a structured data extractor for fire department incident reports.\n\nGiven a free-form incident description, extract all available information\nand return it as a single valid JSON object that matches this exact schema:\n\n{schema}\n\nStrict rules:\n1. Return ONLY valid JSON. No preamble, no explanation, no markdown code fences.\n2. If a field cannot be determined from the text, omit it or use null.\n3. For incident_type, choose the closest matching enum value from the schema.\n4. For date_time, use ISO 8601 format: YYYY-MM-DDTHH:MM:SS\n5. The narrative field must be a concise factual summary (not a copy of the input).\n6. Do not invent information that is not present or implied by the description.\n'
_CORRECTION_PROMPT = 'Your previous response caused this error:\n{error}\n\nOriginal incident description:\n{description}\n\nPlease provide a corrected JSON response that strictly matches the schema.\nReturn ONLY the JSON object, no other text.\n'

class LLMExtractor:

    def __init__(self, model: str='llama3', ollama_url: str='http://localhost:11434', max_retries: int=2, timeout: float=120.0) -> None:
        self.model = model
        self.ollama_url = ollama_url.rstrip('/')
        self.max_retries = max_retries
        self.timeout = timeout
        self._schema_str = json.dumps(IncidentReport.model_json_schema(), indent=2)

    def extract(self, description: str) -> IncidentReport:
        system = _SYSTEM_PROMPT.format(schema=self._schema_str)
        prompt = description
        last_err: Exception | None = None
        for attempt in range(self.max_retries + 1):
            t0 = time.perf_counter()
            try:
                raw = self._call_ollama(prompt, system)
                cleaned = self._strip_fences(raw)
                data = json.loads(cleaned)
                report = IncidentReport(**data)
                elapsed = time.perf_counter() - t0
                logger.info('Extraction succeeded on attempt %d/%d (%.1fs).', attempt + 1, self.max_retries + 1, elapsed)
                return report
            except (json.JSONDecodeError, ValidationError, KeyError) as exc:
                last_err = exc
                logger.warning('Attempt %d/%d failed: %s', attempt + 1, self.max_retries + 1, exc)
                if attempt < self.max_retries:
                    prompt = _CORRECTION_PROMPT.format(error=exc, description=description)
        raise RuntimeError(f'LLM extraction failed after {self.max_retries + 1} attempts. Last error: {last_err}')

    def _call_ollama(self, prompt: str, system: str) -> str:
        payload = {'model': self.model, 'prompt': prompt, 'system': system, 'stream': False, 'options': {'temperature': 0.1, 'num_predict': 1024}}
        try:
            resp = httpx.post(f'{self.ollama_url}/api/generate', json=payload, timeout=self.timeout)
            resp.raise_for_status()
        except httpx.ConnectError as exc:
            raise RuntimeError(f'Cannot connect to Ollama at {self.ollama_url}. Is Ollama running? Try: ollama serve') from exc
        return resp.json()['response']

    @staticmethod
    def _strip_fences(raw: str) -> str:
        text = raw.strip()
        text = re.sub('^```(?:json)?\\s*', '', text, flags=re.MULTILINE)
        text = re.sub('```\\s*$', '', text, flags=re.MULTILINE)
        brace = text.find('{')
        if brace > 0:
            text = text[brace:]
        return text.strip()