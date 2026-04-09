# Contract Reviewer — AI-Powered Clause Analysis

An AI-powered contract review tool built with Streamlit and Claude. Upload a contract (PDF, DOCX, or TXT), answer a few context questions, and get a clause-by-clause risk analysis tailored to your situation.

## Features

- **Intake flow** — Asks contract type, jurisdiction, your role, and priorities before analysis
- **PDF parsing** — Extracts text from PDFs using `pdfplumber`, with OCR fallback for scanned documents
- **DOCX support** — Reads Word documents via `python-docx`
- **Clause-by-clause analysis** — Each clause gets a risk rating, plain-English summary, and suggested edits
- **Missing clause detection** — Flags standard provisions that are absent
- **Jurisdiction-aware** — Tailors analysis to the applicable legal framework
- **Role-aware** — Risk scoring is relative to which party you are

## Local Setup

```bash
# 1. Clone and enter the directory
cd contract-reviewer

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. For OCR support on scanned PDFs (optional):
#    - Install Tesseract: https://github.com/tesseract-ocr/tesseract
#    - Install Poppler: https://poppler.freedesktop.org/
#    macOS: brew install tesseract poppler
#    Ubuntu: sudo apt-get install tesseract-ocr poppler-utils

# 5. Add your API key
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edit .streamlit/secrets.toml and add your Anthropic API key

# 6. Run
streamlit run app.py
```

## Deploy to Streamlit Community Cloud

1. Push this project to a GitHub repo
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repo and select `app.py` as the main file
4. Add your `ANTHROPIC_API_KEY` in the Secrets section (Settings → Secrets):
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."
   ```
5. For OCR support, create a `packages.txt` in the repo root with:
   ```
   tesseract-ocr
   poppler-utils
   ```
6. Deploy

## Project Structure

```
contract-reviewer/
├── app.py                          # Main Streamlit application
├── requirements.txt                # Python dependencies
├── .streamlit/
│   ├── config.toml                 # Theme and server config
│   └── secrets.toml.example        # API key template
└── README.md
```

## Notes

- This tool provides informational analysis only and does not constitute legal advice.
- Contract text is sent to the Claude API for analysis — do not upload highly sensitive documents without understanding the data handling implications.
- The OCR fallback requires Tesseract and Poppler to be installed on the system.
