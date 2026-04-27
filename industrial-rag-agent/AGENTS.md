# Repository Guidelines

## Project Structure & Module Organization

This repository contains an industrial after-sales RAG chatbot with a Python backend and React frontend.

- `backend/main.py` starts the FastAPI application.
- `backend/api/` defines HTTP routes, including chat and health endpoints.
- `backend/workflow/` builds the LangGraph workflow.
- `backend/nodes/` contains workflow steps such as query enhancement, validation, retrieval, assessment, generation, and optimization.
- `backend/knowledge/` holds knowledge-base setup and the persisted Chroma database under `chroma_db/`.
- `backend/config/`, `backend/logging/`, and `backend/models/` contain shared settings, logging, and state models.
- `frontend/src/` contains the Vite React app; `frontend/src/components/` contains reusable UI components.
- `logs/` stores runtime logs. Avoid committing noisy generated logs unless they are intentionally part of an example.

## Build, Test, and Development Commands

Backend setup and run:

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd ..
python -m backend.main
```

Frontend setup and run:

```bash
cd frontend
npm install
npm run dev
npm run build
npm run preview
```

The backend expects an OpenAI-compatible API key and uses `OPENAI_API_KEY`, optional `OPENAI_BASE_URL`, `LLM_MODEL`, and `EMBEDDING_MODEL` from `.env`.

## Coding Style & Naming Conventions

Use 4-space indentation for Python and 2-space indentation for TypeScript/React. Keep Python modules lowercase with descriptive names, matching the existing `backend/nodes/*.py` pattern. Use `PascalCase` for React components, `camelCase` for variables and functions, and colocate component CSS beside the component when practical. Follow existing docstring and Chinese domain terminology where it improves clarity.

## Testing Guidelines

No formal test framework is currently configured. For backend changes, add focused tests under `backend/tests/` if introducing non-trivial logic, preferably with `pytest` and files named `test_*.py`. For frontend changes, add tests under `frontend/src/**/*.test.tsx` if a test runner is introduced. At minimum, verify `python -m backend.main`, `npm run build`, `GET /api/health`, and a sample `POST /api/chat`.

## Commit & Pull Request Guidelines

Recent commits use short, descriptive Chinese summaries such as `工业诊断机器人` and `多文档知识`. Keep commit subjects concise and focused on one change. Pull requests should include a brief description, affected backend/frontend areas, setup or configuration changes, manual verification steps, and screenshots or short recordings for UI changes.

## Security & Configuration Tips

Use `.env` for local settings such as `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `LLM_MODEL`, `EMBEDDING_MODEL`, `CHROMA_PERSIST_DIR`, `LOG_LEVEL`, and `LOG_FILE`. Do not commit secrets, private endpoints, or machine-specific paths. Restrict CORS origins before production deployment.
