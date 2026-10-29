# Test Checklist

## Automated tests
Run: `py -m unittest discover -s tests -v`

- [ ] Flask app imports and initializes the SQLite schema.
- [ ] Health endpoint returns JSON status `ok`.
- [ ] Login requires configured credentials.
- [ ] Stage 2/3 are denied before earlier flags are verified.
- [ ] Stage 2 IDOR fixture is synthetic and only known record IDs are served.
- [ ] Path traversal selector returns fixed content and does not read arbitrary filesystem paths.

## Docker / Windows acceptance checks
- [ ] `docker compose config` succeeds after `.env` creation.
- [ ] `docker compose up --build -d` succeeds.
- [ ] `http://127.0.0.1:8787/health` responds.
- [ ] Correct credentials log in; incorrect credentials fail.
- [ ] Stage 1 opens; stages 2 and 3 are locked initially.
- [ ] Stage 2 IDOR and CSRF exercises must both be recorded before FLAG 02.
- [ ] FLAG 02 is rejected before FLAG 01; FLAG 03 is rejected before FLAG 02.
- [ ] Correct flags advance progress to 25%, 65%, then 100%.
- [ ] Refresh and normal container restart preserve progress and timer.
- [ ] Final completion text is exactly `PHANTOM PROTOCOL COMPLETE — 100%`.
- [ ] Starting a new run preserves earlier run history.
- [ ] Review audit log and ensure no passwords or flag values appear.
- [ ] Confirm service is bound only to localhost.

## Test status
The build archive should be treated as a deliverable candidate until the tests actually run in the environment. Any Docker checks not performed must remain unchecked; do not claim end-to-end verification without evidence.
