# Backend Branch Strategy

This project uses a protected `main` branch and small feature branches for each backend milestone.

## Branches

- `chore/00-repo-bootstrap`: repository bootstrap, environment template, dependency manifest, package skeleton
- `feature/02-dart-integration`: OpenDART client, corporation code parsing, CSV cache, DART error handling
- `feature/03-financial-analysis`: account matching, amount parsing, ratio calculation, growth comparison, risk signals
- `feature/04-llm-safety`: Upstage LLM client, follow-up answers, investment-advice guardrails
- `feature/05-langgraph-workflow`: workflow state and analysis nodes
- `feature/06-fastapi-backend`: FastAPI endpoints, schemas, in-memory session store

Frontend work is intentionally separated into `feature/07-streamlit-ui`.

## Rules

- Do not push directly to `main`.
- Open one pull request per milestone branch.
- Keep frontend code out of backend milestone pull requests.
- Run the relevant tests before requesting review.
- Do not commit local secrets, caches, or generated files.
