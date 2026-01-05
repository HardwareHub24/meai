setup:
	python -m venv .venv
	. .venv/bin/activate && pip install -r requirements.txt

web:
	. .venv/bin/activate && python meai_web/app.py

ask:
	. .venv/bin/activate && python ask_03_rag_cli.py

deps-docs:
	@command -v pandoc >/dev/null 2>&1 || (echo "pandoc not found"; echo "Install: https://pandoc.org/installing.html"; exit 1)

system-pdfs: deps-docs
	@mkdir -p docs/system_pdfs
	pandoc docs/system/01_project_overview.md -o docs/system_pdfs/01_Project_Overview.pdf
	pandoc docs/system/02_system_architecture.md -o docs/system_pdfs/02_System_Architecture.pdf
	pandoc docs/system/03_tech_stack.md -o docs/system_pdfs/03_Tech_Stack.pdf
	pandoc docs/system/04_env_and_secrets.md -o docs/system_pdfs/04_Env_and_Secrets.pdf
	pandoc docs/system/05_database_schema.md -o docs/system_pdfs/05_Database_Schema.pdf
	pandoc docs/system/06_ingestion_pipeline.md -o docs/system_pdfs/06_Ingestion_Pipeline.pdf
	pandoc docs/system/07_known_issues.md -o docs/system_pdfs/07_Known_Issues.pdf
	pandoc docs/system/08_runbook.md -o docs/system_pdfs/08_Runbook.pdf
	pandoc docs/system/09_future_roadmap.md -o docs/system_pdfs/09_Future_Roadmap.pdf
	pandoc docs/system/10_glossary.md -o docs/system_pdfs/10_Glossary.pdf
