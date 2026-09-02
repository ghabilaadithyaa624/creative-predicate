.PHONY: install init test run simulate backtest dashboard api clean

install:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt

init:
	python main.py init

test:
	pytest tests/ -v

run:
	python main.py run --name AlphaBot --mode aggressive --rounds 10

simulate:
	python main.py simulate-all --rounds 5

backtest:
	python main.py backtest --monte-carlo

dashboard:
	streamlit run dashboard/app.py

api:
	python main.py api --port 8000

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .coverage htmlcov
