.PHONY: help install install-all init test lint fmt run simulate backtest montecarlo dashboard api clean

help:
	@echo "Creative Predicate -- paper-trading research sandbox"
	@echo ""
	@echo "  make install      Core runtime + dev tools (enough for tests & CLI)"
	@echo "  make install-all  Every optional extra (torch, streamlit, vision, ...)"
	@echo "  make test         Run the test suite"
	@echo "  make lint         Ruff check"
	@echo "  make fmt          Ruff autofix"
	@echo "  make run          Single-agent simulation"
	@echo "  make simulate     Multi-agent tournament"
	@echo "  make backtest     Deterministic walk-forward backtest"
	@echo "  make montecarlo   Bootstrap Monte Carlo backtest"
	@echo "  make dashboard    Streamlit monitor (needs [dashboard] extra)"
	@echo "  make api          FastAPI server (needs [api] extra)"

install:
	pip install -e ".[dev]"

install-all:
	pip install -e ".[api,dashboard,ml,vision,memory,dev]"

init:
	python main.py init

test:
	pytest tests/ -v

lint:
	ruff check .

fmt:
	ruff check . --fix

run:
	python main.py run --name AlphaBot --mode aggressive --rounds 10

simulate:
	python main.py simulate-all --rounds 5

backtest:
	python main.py backtest

montecarlo:
	python main.py backtest --monte-carlo

dashboard:
	streamlit run dashboard/app.py

api:
	python main.py api --port 8000

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .ruff_cache .coverage htmlcov *.egg-info
