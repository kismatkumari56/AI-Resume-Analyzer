# AI Resume Analyzer

A small Flask web app that reads a PDF or DOCX resume, detects the skills in it, gives a
section-wise resume score and suggests what could be improved.

Built for beginners to read, run and contribute to. Part of
**Winter of Code Social (WOCS) 2026**.

## What it does

- Upload a resume as a PDF or DOCX file (max 10 MB)
- Extracts PDF text with `pypdf` and DOCX text with `python-docx`
- Detects skills such as Python, SQL, Flask, React, Git and more
- Gives a resume score with a breakdown (contact info, summary, skills,
  education, experience, projects, ...)
- Shows suggestions based on the skills that were found
- The uploaded file is deleted right after the analysis

## Tech stack

- Python 3.9 or newer
- [Flask](https://flask.palletsprojects.com/) for the web app
- [pypdf](https://pypdf.readthedocs.io/) for reading PDFs
- [python-docx](https://python-docx.readthedocs.io/) for reading DOCX files
- HTML, CSS and JavaScript for the pages (`templates/`, `static/`)

## Project structure

```
app.py                      Flask app: routes for upload and results
analyzer/
  resume_extractor.py       Extracts text from PDF and DOCX files
  pdf_reader.py             Backward-compatible PDF extraction wrapper
  docx_reader.py            Extracts text from a DOCX
  skills_extractor.py       Finds skills in the text and gives suggestions
  resume_scorer.py          Calculates the resume score and breakdown
  job_matcher.py            Extracts job skills and matches them to resumes
  section_detector.py       Organizes resume text into named sections
  ats_checker.py             Performs ATS-readiness analysis
  suggestions.py            Suggestion helpers
templates/                  index.html (upload page), result.html (results page)
static/                     style.css, script.js
```

## Run it locally

```bash
# 1. Clone your fork
git clone https://github.com/<your-username>/AI-Resume-Analyzer.git
cd AI-Resume-Analyzer

# 2. (Recommended) create a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Start the app
python app.py
```

The app opens at http://127.0.0.1:5000. Upload a PDF or DOCX resume and check the result.

Please test with your own resume or a sample one. Do not upload other people's
resumes to the repository.

## Evaluation & Accuracy Benchmarking

The project includes an automated benchmark suite to evaluate skill extraction precision, recall, and F1-score against synthetic test resumes containing zero real-world personal information:

```bash
# Run the evaluation benchmark summary
python -m benchmarks.run_benchmark

# Show detailed per-sample accuracy breakdown
python -m benchmarks.run_benchmark --verbose

# Save evaluation results as JSON
python -m benchmarks.run_benchmark --output benchmarks/baseline.json

# Compare accuracy against a saved baseline to verify improvements or prevent regressions
python -m benchmarks.run_benchmark --compare benchmarks/baseline.json
```

## How to contribute

1. Read [CONTRIBUTING.md](CONTRIBUTING.md).
2. Pick an issue labeled `wocs` and a `level` (`level 1` is the easiest) and
   ask to be assigned.
3. Open a pull request when your work is ready.

Join the discussion in our project forum on the Code Social Discord server
(`#find-a-project`). Questions are welcome, especially from first-time
contributors.

## Ideas to work on

- Add more skills and better matching to the skill list
- Improve the score and the suggestions
- Better error pages instead of plain text messages
- Tests for the analyzer functions
- Improve the look of the pages (mobile friendly layout)

## AI policy

AI tools (ChatGPT, Claude, Copilot, etc.) are **allowed**, with these rules:

- Mention in your PR description that you used AI and for what.
- You must understand your code and be able to explain every line.
- Test your changes locally. Untested AI output will not be merged.

PRs that go against this can be closed, and misuse can be reported to
Team Code Social.

## License

Add a license file (for example MIT) so others know how they may use the code.