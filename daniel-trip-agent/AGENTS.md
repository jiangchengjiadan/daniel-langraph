# Repository Guidelines

## Project Structure & Module Organization

This repository contains a LangGraph/FastAPI backend and a Vue 3 frontend for an intelligent travel planner.

- `backend/app/agents/`: LangGraph planner, state definitions, and node implementations.
- `backend/app/api/`: FastAPI application entry point and route modules.
- `backend/app/services/`: integrations for LLM, Amap, and Unsplash services.
- `backend/app/tools/`: Amap and MCP tool wrappers used by agent nodes.
- `backend/app/models/`: Pydantic request/response schemas.
- `backend/test_langgraph_basic.py`: backend smoke test script.
- `frontend/src/views/`: Vue route pages such as `Home.vue` and `Result.vue`.
- `frontend/src/services/`: API client code.
- `frontend/src/types/`: shared TypeScript types.

## Build, Test, and Development Commands

Backend:

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000
python test_langgraph_basic.py
```

Frontend:

```bash
cd frontend
npm install
npm run dev
npm run build
npm run preview
```

`npm run dev` starts Vite on the local development port. `npm run build` runs `vue-tsc` type checking before producing the production bundle.

## Coding Style & Naming Conventions

Use Python 3.10+ with 4-space indentation, type hints where practical, and Pydantic models for API boundaries. Keep backend modules grouped by responsibility: routes in `api/routes`, integrations in `services`, and agent behavior in `agents` or `tools`.

Use Vue single-file components with TypeScript. Name page components in PascalCase, for example `Home.vue`, and keep shared API types in `frontend/src/types/index.ts`. Prefer clear service functions in `frontend/src/services/api.ts` over direct Axios calls in components.

## Testing Guidelines

Run `python backend/test_langgraph_basic.py` after changes to agent state, nodes, tools, or planner initialization. Add focused tests or smoke checks when introducing new graph nodes or external service wrappers. Run `npm run build` before frontend pull requests to catch TypeScript and Vue template errors.

## Commit & Pull Request Guidelines

The current Git history uses short, descriptive Chinese commit messages, for example `旅行规划服务`. Keep commits concise and focused on one change.

Pull requests should include a brief summary, affected backend/frontend areas, test commands run, and screenshots or screen recordings for visible UI changes. Link related issues when available.

## Security & Configuration Tips

Do not commit real `.env` secrets. Backend configuration expects keys such as `AMAP_API_KEY`, `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL_ID`, and optional Unsplash keys. Frontend local configuration uses `VITE_AMAP_WEB_KEY` in `frontend/.env`.
