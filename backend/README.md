# SATYA AI – Smart Legal Assistance for Every Citizen

## 1. Project Overview

SATYA AI is an AI-powered legal assistance platform designed to help Indian consumers understand their rights and access consumer grievance guidance.

It provides simple explanations of consumer laws, helps users understand possible legal remedies, guides them through case filing, and generates complaint documents.

## 2. Problem Statement

Many consumers in India are unaware of their legal rights and find consumer grievance procedures difficult to understand. Accessing legal information can be time-consuming and confusing.

SATYA AI aims to make consumer-law information easier to understand and more accessible.

## 3. Key Features

- **AI Legal Assistant:** Answers consumer-law questions in simple language.
- **Case Filing Guide:** Provides step-by-step guidance for consumer complaints.
- **Legal Document Generation:** Generates downloadable complaint documents in PDF format.
- **Document Library:** Provides access to important consumer-law documents.
- **Case History:** Stores previous queries in the browser.
- **User Profile:** Allows users to save their profile details.
- **Legal Knowledge Base:** Uses Indian consumer-law documents to support answers.

## 4. Technology Stack

- Frontend: HTML, CSS, JavaScript
- Backend: Python, FastAPI
- Legal document processing: PyMuPDF
- Search and retrieval: FAISS and embeddings
- Data storage: Browser LocalStorage and local vector index
- API communication: REST API

## 5. Legal Knowledge Base

The project uses the following legal documents:

1. Consumer Protection Act, 2019
2. Consumer Protection (General) Rules, 2020
3. Consumer Protection (E-Commerce) Rules, 2020
4. Consumer Protection (E-Commerce) Amendment Rules, 2021

## 6. Project Structure

```text
satya/
├── main.py
├── ingest.py
├── embedding_store.py
├── documents/
│   └── consumer_law/
├── tests/
├── .venv/
└── README.md
```

Additional frontend files are maintained separately.

## 7. How to Run the Project

### Start the Backend

```powershell
cd "C:\Users\preeti pattar\.gemini\antigravity\scratch\satya"
.\.venv\Scripts\Activate.ps1
python -m uvicorn main:app --reload
```

Backend URL: http://127.0.0.1:8000

API documentation: http://127.0.0.1:8000/docs

### Start the Frontend

Open another PowerShell window:

```powershell
& "C:\Users\preeti pattar\.gemini\antigravity\scratch\satya\.venv\Scripts\python.exe" -m http.server 5500 --directory "C:\Users\preeti pattar\Downloads\stitch_satya_ai_legal_assistant"
```

Open: http://localhost:5500/code.html

## 8. Important Note

SATYA AI provides legal information and general guidance. It is not a substitute for advice from a qualified legal professional. Users should verify legal provisions and review generated documents before submitting them.

## 9. Future Enhancements

- Multilingual legal assistance
- User authentication and secure cloud storage
- Integration with official consumer grievance services
- Improved legal document retrieval
- More automated complaint workflows

## 10. Project Name

**SATYA AI – Smart Legal Assistance for Every Citizen**

