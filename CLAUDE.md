# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python URL shortener application using Python 3.10.7 with a virtual environment configured.

## Development Setup

1. Activate the virtual environment:
   ```bash
   source venv/bin/activate
   ```

2. Install dependencies (when requirements.txt is created):
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application (command will depend on final implementation):
   ```bash
   python app.py
   # or
   python -m uvicorn main:app --reload
   # or
   flask run
   ```

## Testing

Run tests with:
```bash
python -m pytest
# or
python -m unittest discover
```

## Code Quality

- Use `black` for code formatting: `black .`
- Use `flake8` for linting: `flake8 .`
- Use `mypy` for type checking: `mypy .`

## Architecture Notes

This project is designed to be a URL shortener service. The typical architecture would include:
- URL encoding/decoding logic
- Database storage for URL mappings
- Web API endpoints for creating and resolving short URLs
- Optional analytics and rate limiting
- Production URL: https://url-shortener-api-409887059259.us-central1.run.app
- When deploying, set BASE_URL environment variable
