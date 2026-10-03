# ALGOMINDS — Patient Case-Taking Software

SIH 2026 MVP for **SIH26047**. This is a demonstration and decision-support prototype, **not a clinical diagnostic system**.

## Live Demo

**Patient Case-Taking System:** https://patient-case-taking-system-8zlk.onrender.com

The Render deployment is configured for automatic deployment from the `main` branch.

## Workflow

```text
Patient Registration + Consent
          │
          ▼
Text / Browser Voice / OCR Input
          │
          ▼
Case Extraction & Completeness Checks
          │
          ├── Red-flag detection
          ├── AYUSH Dashavidha Pariksha
          └── Structured case data
          │
          ▼
SQLite + Audit Log
          │
          └── FHIR-style JSON interoperability endpoint
```

## Included

- Patient registration and consent
- Multilingual text and browser voice input
- AI-assisted case extraction using the deterministic demo workflow
- Red-flag detection and completeness score
- OCR upload endpoint with optional Tesseract
- AYUSH Dashavidha Pariksha fields
- SQLite storage and audit log
- FHIR-style interoperability JSON endpoint

## Run on Windows

1. Install Python 3.10+.
2. Open Command Prompt in this folder.
3. Run `run_windows.bat`.
4. Open `http://127.0.0.1:8000`.

## Important

This repository is a prototype for academic/demo use. Do not use it for real clinical decisions or real patient data without appropriate validation, security, privacy controls, clinical review, and production infrastructure.
