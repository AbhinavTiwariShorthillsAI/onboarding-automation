# Onboarding Automation (OCR to JSON)

AI-powered Django app that converts uploaded onboarding documents (PDF/JPG/PNG) into clean JSON using Google Gemini 2.5 Pro. The app focuses on OCR-only extraction (no regex field parsing) and gives you a copy-ready JSON on the document page.

## Key Features
- Upload PDF, JPG, or PNG up to 10MB
- OCR via Google Gemini 2.5 Pro → JSON-only output
- Per-page PDF results merged into a single JSON object
- Copy-ready JSON panel in the UI
- Processing logs and basic document metadata
- Optional legacy “Export JSON (Fields)” kept for reference (not the source of truth)

## Architecture
- Backend: Django 4.2
- OCR: Google Gemini (google-generativeai)
- PDF→Image: pdf2image (requires poppler)
- Image prep: Pillow, OpenCV (optional)
- File type detection: python-magic
- DB: SQLite (default)

## Prerequisites
- Python 3.10+
- Poppler (for pdf2image)
  - Ubuntu/Debian: `sudo apt-get install -y poppler-utils`
  - macOS (Homebrew): `brew install poppler`
- A Google AI Studio API key

## Quick Start
1) Clone and setup
```bash
git clone <repo>
cd onboarding-automation
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2) Environment
Create `.env` in project root:
```bash
GOOGLE_AI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-2.5-pro
DEBUG=True
```

3) Migrate and run
```bash
python manage.py migrate
python manage.py runserver
```

4) Use
- Open `http://127.0.0.1:8000/`
- Upload a PDF/JPG/PNG
- After processing, open the document page
  - See OCR text preview
  - See “OCR JSON (copy-ready)” → press “Copy JSON” and paste wherever needed

## How OCR Works (What to expect)
- Images and PDFs are sent page-by-page to Gemini
- The app requests JSON-only responses
- For PDFs, page JSON is merged into a single JSON object
- If Gemini ever returns non-JSON text, the app safely wraps it as `{ "text": "..." }` so the UI always shows valid JSON

## Endpoints (user-facing)
- `/` Home + recent docs
- `/upload/` Upload a document
- `/documents/<id>/` Document details
- `/gemini-info/` Gemini status and usage info

## Configuration
Adjust in `.env`:
```bash
GOOGLE_AI_API_KEY=your_api_key
GEMINI_MODEL=gemini-2.5-pro  # default used by the app
DEBUG=False                  # for production
```
Django settings already read these via `python-dotenv`.

## Troubleshooting
- API errors (quota/auth): Check `/gemini-info/` and your API key
- PDF not processed: Ensure `poppler` is installed
- Large/complex docs time out: Retry; the app falls back to safer parsing when needed
- JSON looks wrapped as `{ "text": ... }`: That means Gemini didn’t return parseable JSON; copy this and re-run later for improved results

## Security & Privacy
- Files are stored locally under `media/`
- Only your Gemini API key is used (no other external services)
- Do not commit your `.env`

## Notes
- Field extraction via regex/NLP is intentionally disabled in this build—OCR JSON is the source of truth
- Legacy “Export JSON (Fields)” remains for admin/testing but is not used in the primary flow

## License
MIT
