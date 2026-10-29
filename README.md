# PROJECT PHANTOM — PHANTOM v1.0

A locally hosted, three-stage cybersecurity CTF lab for Windows and Docker Desktop. It uses fictional data and is intended for authorized local training only.

## Features

- Three-stage web security challenge.
- Simulated credential leakage, IDOR, CSRF, and path traversal.
- Docker-based setup for local use.
- Local progress storage using a Docker volume.
- Security-focused configuration and documentation.

## Requirements

- Windows 10/11
- Docker Desktop with Docker Compose
- Git (optional, for cloning the repository)

## Quick Start — Windows

1. Download or clone this repository.
2. Open PowerShell in the project directory.
3. Create a local `.env` file based on `.env.example`.
4. Replace all placeholder values with unique local values. Use a strong password and a randomly generated session secret. Configure your own local challenge flags.
5. Start the lab:

   ```powershell
   docker compose up --build -d
   ```

6. Open [http://127.0.0.1:8787](http://127.0.0.1:8787) in your browser and sign in using the administrator credentials you configured in `.env`.

## Stop and Restart

Stop the lab:

```powershell
docker compose down
```

Start it again:

```powershell
docker compose up -d
```

The named Docker volume preserves local progress when you stop the containers without removing the volume.

**Warning:** `docker compose down -v` deletes the named volume and its stored progress.

## Local Development Without Docker

Requires Python 3.12 and pip.

1. Create and configure `.env` as described above.
2. Install dependencies:

   ```powershell
   py -m pip install -r requirements.txt
   ```

3. Run the application:

   ```powershell
   py app.py
   ```

4. Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Security Notes

- This project is an educational lab, not a production authentication service.
- The application is intended for local use.
- Never commit `.env`, real passwords, session secrets, or private challenge flags.
- The path traversal challenge is simulated and does not open arbitrary filesystem paths.
- Use only in systems you own or are authorized to test.

## Documentation

- [Player Guide](PLAYER_GUIDE.md)
- [Security Review](SECURITY_REVIEW.md)
- [Test Checklist](TEST_CHECKLIST.md)

## Disclaimer

PROJECT PHANTOM is provided for educational and authorized security training purposes only.
