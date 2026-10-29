"""Destructively remove the local SQLite database. Run only after backing up results."""
import os
from pathlib import Path
p = Path(os.environ.get('PHANTOM_DATA_DIR', Path(__file__).resolve().parents[1] / 'data')) / 'phantom.sqlite3'
if not p.exists(): print('No database found.'); raise SystemExit(0)
answer = input(f'This permanently deletes local run history at {p}. Type DELETE to continue: ')
if answer == 'DELETE': p.unlink(); print('Database removed. Restart the app to initialize a clean database.')
else: print('Cancelled.')
