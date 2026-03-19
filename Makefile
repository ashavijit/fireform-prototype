.PHONY: install test test-unit test-integration demo lint fmt typecheck clean

install:
	pip install -e ".[dev]"

test:
	pytest --cov=fireform --cov-report=term-missing

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v

demo:
	@echo "Running FireForm pipeline demo (mock mode — no Ollama needed)..."
	python scripts/run_demo.py

demo-live:
	@echo "Running FireForm pipeline demo (requires Ollama running)..."
	python scripts/run_demo.py --live

lint:
	ruff check src/ tests/

fmt:
	ruff format src/ tests/

typecheck:
	mypy src/fireform/

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -name "*.pyc" -delete
	rm -rf .coverage htmlcov/ dist/ build/

doctor:
	fireform doctor
