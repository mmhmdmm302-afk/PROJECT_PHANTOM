# Security Review

## Intended scope
Exactly four intentional vulnerability categories are included: Credential Leakage, IDOR, CSRF, and Path Traversal. Credential leakage exists only in fictional public artifacts; IDOR only serves fixed fictional records; CSRF only affects a synthetic role marker; path traversal syntax is simulated against fixed content and never reads arbitrary paths.

## Controls
- Passwords are stored using Werkzeug's password hashing; credentials are generated locally.
- Session cookie is HTTP-only and SameSite=Lax. The lab uses local HTTP, so Secure is not enabled by default.
- State-changing endpoints require CSRF tokens except the single deliberate Stage 2 exercise endpoint.
- Flags and stage ordering are checked server-side; flags are not injected into templates or client scripts.
- SQLite queries use parameterized statements.
- Request body size is limited; login attempts are throttled per session.
- Docker binds to loopback, drops capabilities, uses `no-new-privileges`, a read-only root filesystem, and a dedicated named volume for mutable data.
- The path selector never controls a filesystem open path.
- Error pages avoid stack traces and internal paths. Audit logs do not contain passwords or flag values.

## Known limitations and review status
This is an educational local lab, not production-ready authentication software. Login throttling is per session and not a distributed rate limiter. A local administrator can inspect `.env`, modify the database, or control Docker. The vulnerable CSRF endpoint is a scoped training feature. The archive path traversal is simulated safely, so it does not expose a host filesystem. Static/unit checks cannot prove absence of all defects. Verify Docker behavior on the intended Windows host and conduct a player usability test before describing the difficulty as verified 10/10.
