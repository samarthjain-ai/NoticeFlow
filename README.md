NOTICEFLOW
NOTICEFLOW turns messy student notices into a clear next action.

The current MVP runs in credential-free demo mode and supports:

pasted notice text and uploads for text, PDF, and image files
validated notice, deadline, requirement, action, risk, and source-evidence models
explicit uncertainty for relative or ambiguous deadlines
explainable priority and deadline-risk rules
SQLite persistence for notices and action completion
a dashboard, analysis flow, action plan, and source evidence view
Run locally
python -m pip install -r requirements.txt
streamlit run app.py
Open http://localhost:8501 in a browser. No API key is required for demo mode.

The Analyze view includes four fictional Demo Mode scenarios: Hackathon, Scholarship, Assignment, and Internship. Each goes through the same extraction, action, priority, risk, persistence, and result flow as pasted or uploaded content.

AI provider configuration
Copy .env.example to .env when enabling a live provider:

AI_PROVIDER=auto
OPENAI_MODEL=gpt-4o-mini
OPENAI_API_KEY=your-key-here
auto uses OpenAI when OPENAI_API_KEY is present and otherwise uses Demo Mode. Set AI_PROVIDER=demo to force local analysis or AI_PROVIDER=openai to require the configured OpenAI provider. The key is read only from the environment and is never stored in SQLite.

Text PDFs use pypdf. Scanned PDFs and images use PyMuPDF/Pillow plus the Tesseract executable; if Tesseract is unavailable, Noticeflow reports that OCR is unavailable instead of analyzing empty text.

Structure
app.py: Streamlit composition and user flow
noticeflow/core: Pydantic models, demo provider, and deterministic business rules
noticeflow/services: document extraction and SQLite persistence
noticeflow/tests: deterministic unit tests without live LLM calls
The AI provider boundary is AIService.analyze_notice(). OpenAIService returns only the strict ExtractionResult Pydantic contract; Python then validates source evidence and owns action generation, priority, risk, and storage. Provider failures never expose raw SDK details to students.

Test
python -m unittest discover -s noticeflow\tests -p "test_*.py" -v
Final demo command
.\.venv\Scripts\streamlit.exe run app.py
