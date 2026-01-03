setup:
	python -m venv .venv
	. .venv/bin/activate && pip install -r requirements.txt

web:
	. .venv/bin/activate && python meai_web/app.py

ask:
	. .venv/bin/activate && python ask_03_rag_cli.py
