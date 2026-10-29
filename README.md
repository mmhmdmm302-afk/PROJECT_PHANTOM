# PROJECT PHANTOM — PHANTOM v1.0

A locally hosted, three-stage web CTF lab for Windows + Docker Desktop. It uses fictional data and is intended for local training only. The target 10/10 difficulty is aspirational and has not been validated with external players.

## Quick start (Windows)
1. Install and start Docker Desktop.
2. Extract this folder from `PROJECT_PHANTOM.zip`.
3. Open PowerShell in the extracted `PROJECT_PHANTOM` directory.
4. Run `py scripts/init_env.py`. Save the generated password shown in the terminal; do not share `.env`.
5. Run `docker compose up --build -d`.
6. Open <http://127.0.0.1:8787> and sign in as `phantom` with the generated password.
7. Check health with `Invoke-WebRequest http://127.0.0.1:8787/health`.

To stop: `docker compose down`. Run `docker compose up -d` to restart; progress is stored in the named Docker volume. To preserve the database, use `docker compose down` (not `-v`). To delete all local progress, run `docker compose down -v` after backing up anything needed, then start again. Use `py scripts/reset_data.py` only for a local non-container run.

## Local development without Docker
Requires Python 3.12 and pip. Run `py scripts/init_env.py`, then `py -m pip install -r requirements.txt`, then `py app.py`. Open <http://127.0.0.1:8000>. This mode writes SQLite data to `./data/`.

## Notes
- The published port is bound to `127.0.0.1`, not all interfaces.
- The session secret and lab password are generated into `.env`; challenge flags are configured there and must never be pasted into public materials.
- The four intentional categories are Credential Leakage, IDOR, CSRF, and Path Traversal. The path traversal behavior is safely simulated: it does not open arbitrary disk paths.
- This is an educational lab, not a production authentication service. A local administrator can inspect or modify local files and state.
- See `PLAYER_GUIDE.md`, `OWNER_WALKTHROUGH.md`, `SECURITY_REVIEW.md`, and `TEST_CHECKLIST.md`.
