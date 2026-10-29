import os, sqlite3, time, secrets, logging, hmac
from pathlib import Path
from datetime import datetime, timezone
from functools import wraps
from flask import Flask, request, session, redirect, url_for, render_template, flash, g, abort, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get('PHANTOM_DATA_DIR', ROOT / 'data'))
DB_PATH = DATA_DIR / 'phantom.sqlite3'
CHALLENGE_DIR = (ROOT / 'challenge_data' / 'archive').resolve()
APP_SECRET = os.environ.get('PHANTOM_SESSION_SECRET', '')
FLAGS = [os.environ.get(f'PHANTOM_FLAG_{i}', '') for i in range(1, 4)]
ADMIN_USER = os.environ.get('PHANTOM_ADMIN_USER', '')
ADMIN_PASSWORD = os.environ.get('PHANTOM_ADMIN_PASSWORD', '')
HINT_LIMIT = int(os.environ.get('PHANTOM_HINT_LIMIT', '2'))

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = APP_SECRET or 'unsafe-development-secret-not-for-use'
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax', MAX_CONTENT_LENGTH=64 * 1024, PERMANENT_SESSION_LIFETIME=3600)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger('phantom')


def now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def connect_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    return conn

def init_db():
    with connect_db() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, status TEXT NOT NULL, stage INTEGER NOT NULL, progress INTEGER NOT NULL, started_at TEXT NOT NULL, completed_at TEXT, hints_used INTEGER NOT NULL DEFAULT 0, completed_flags TEXT NOT NULL DEFAULT '', FOREIGN KEY(user_id) REFERENCES users(id));
        CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, user_id INTEGER, event TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS exercises (run_id TEXT PRIMARY KEY, credential_done INTEGER NOT NULL DEFAULT 0, idor_done INTEGER NOT NULL DEFAULT 0, csrf_done INTEGER NOT NULL DEFAULT 0, FOREIGN KEY(run_id) REFERENCES runs(id));
        ''')
        if ADMIN_USER and ADMIN_PASSWORD:
            found = db.execute('SELECT id FROM users WHERE username=?', (ADMIN_USER,)).fetchone()
            if not found:
                db.execute('INSERT INTO users(username,password_hash) VALUES(?,?)', (ADMIN_USER, generate_password_hash(ADMIN_PASSWORD)))

def event(name, detail=''):
    try:
        with connect_db() as db:
            db.execute('INSERT INTO events(run_id,user_id,event,detail,created_at) VALUES(?,?,?,?,?)', (session.get('run_id'), session.get('user_id'), name, str(detail)[:240], now()))
    except Exception: log.exception('Could not record audit event')

def get_run():
    rid = session.get('run_id'); uid = session.get('user_id')
    if not rid or not uid: return None
    with connect_db() as db: return db.execute('SELECT * FROM runs WHERE id=? AND user_id=?', (rid, uid)).fetchone()
def require_login(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if not session.get('user_id'): return redirect(url_for('login'))
        return fn(*a, **kw)
    return wrapper
def require_stage(n):
    run = get_run()
    if not run or run['stage'] < n:
        event('locked_stage_denied', f'stage={n}')
        abort(403)
    return run

@app.before_request
def csrf_protection():
    # Intentional exception: the Stage 2 role-change exercise is the sole CSRF lab endpoint.
    if request.method in ('POST','PUT','PATCH','DELETE') and request.endpoint not in ('login','role_change_vulnerable'):
        token = session.get('csrf_token')
        supplied = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token')
        if not token or not supplied or not hmac.compare_digest(token, supplied): abort(400, 'Invalid request token')

@app.context_processor
def shared(): return {'csrf_token': session.get('csrf_token',''), 'hint_limit': HINT_LIMIT}

@app.route('/health')
def health(): return jsonify(status='ok', service='PROJECT PHANTOM')

@app.route('/', methods=['GET','POST'])
def login():
    if session.get('user_id'): return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username','')[:80]; password = request.form.get('password','')[:200]
        key = 'login_attempts'; attempts = session.get(key, 0)
        if attempts >= 8:
            flash('Too many attempts. Wait and restart the local session.', 'error'); event('login_throttled'); return render_template('login.html'), 429
        with connect_db() as db: user = db.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
        if user and check_password_hash(user['password_hash'], password):
            session.clear(); session['user_id'] = user['id']; session['username'] = user['username']; session['csrf_token'] = secrets.token_urlsafe(32); session.permanent = True
            with connect_db() as db:
                run = db.execute('SELECT * FROM runs WHERE user_id=? AND status="active" ORDER BY started_at DESC LIMIT 1', (user['id'],)).fetchone()
                if run: session['run_id'] = run['id']
            event('login_success'); return redirect(url_for('dashboard'))
        session[key] = attempts + 1; log.warning('Failed login for username=%s', username); event('login_failure', f'username={username}'); flash('Sign-in failed. Check your lab credentials.', 'error')
    return render_template('login.html')

@app.post('/logout')
@require_login
def logout():
    event('logout'); session.clear(); return redirect(url_for('login'))

@app.route('/dashboard')
@require_login
def dashboard():
    run = get_run()
    with connect_db() as db:
        previous = db.execute('SELECT id,status,progress,started_at,completed_at FROM runs WHERE user_id=? ORDER BY started_at DESC LIMIT 8', (session['user_id'],)).fetchall()
    elapsed = elapsed_seconds(run) if run else 0
    return render_template('dashboard.html', run=run, elapsed=elapsed, previous=previous)

def elapsed_seconds(run):
    if not run: return 0
    try:
        start = datetime.fromisoformat(run['started_at']); end = datetime.fromisoformat(run['completed_at']) if run['completed_at'] else datetime.now(timezone.utc)
        return max(0, int((end-start).total_seconds()))
    except Exception: return 0

@app.post('/run/start')
@require_login
def start_run():
    with connect_db() as db:
        old = db.execute('SELECT id FROM runs WHERE user_id=? AND status="active"', (session['user_id'],)).fetchall()
        for row in old: db.execute('UPDATE runs SET status="abandoned" WHERE id=?', (row['id'],))
        rid = secrets.token_hex(12)
        db.execute('INSERT INTO runs(id,user_id,status,stage,progress,started_at) VALUES(?,?,?,?,?,?)', (rid,session['user_id'],'active',1,0,now()))
        db.execute('INSERT INTO exercises(run_id) VALUES(?)', (rid,))
    session['run_id'] = rid; event('run_started'); return redirect(url_for('dashboard'))

@app.post('/run/reset')
@require_login
def reset_run():
    run = get_run()
    if run and run['status']=='active':
        with connect_db() as db: db.execute('UPDATE runs SET status="abandoned" WHERE id=?', (run['id'],))
        event('run_abandoned')
    session.pop('run_id', None); return redirect(url_for('dashboard'))

@app.route('/stage/<int:n>')
@require_login
def stage(n):
    if n not in (1,2,3): abort(404)
    run = require_stage(n)
    if run['status'] != 'active': return redirect(url_for('complete'))
    with connect_db() as db: exercise = db.execute('SELECT * FROM exercises WHERE run_id=?', (run['id'],)).fetchone()
    return render_template(f'stage{n}.html', run=run, exercise=exercise)

@app.post('/hint/<int:n>')
@require_login
def hint(n):
    run = require_stage(n)
    if run['status'] != 'active': abort(403)
    if run['hints_used'] >= HINT_LIMIT: flash('No hints remain for this run.', 'error')
    else:
        with connect_db() as db: db.execute('UPDATE runs SET hints_used=hints_used+1 WHERE id=?', (run['id'],))
        event('hint_used', f'stage={n}')
        hints = {1:'Inspect the supplied deployment notes and compare the service account names.',2:'Check whether the record API checks ownership, and inspect how the role-change request is protected.',3:'Compare the requested archive name with the intended evidence directory boundary.'}
        flash('HINT: ' + hints[n], 'info')
    return redirect(url_for('stage', n=n))

@app.route('/legacy/validate', methods=['GET','POST'])
@require_login
def legacy_validate():
    run = require_stage(1)
    if request.method == 'POST':
        username = request.form.get('service_user','')[:80]
        password = request.form.get('service_password','')[:120]
        if hmac.compare_digest(username, 'svc_legacy') and hmac.compare_digest(password, 'ghost-in-the-machine'):
            with connect_db() as db: db.execute('UPDATE exercises SET credential_done=1 WHERE run_id=?', (run['id'],))
            event('credential_leakage_success', 'synthetic service credential validated')
            flash('Synthetic legacy credential accepted. The Stage 1 objective is recorded.', 'success')
        else:
            event('credential_leakage_failure', 'synthetic credential rejected')
            flash('Credential rejected. Re-check the supplied deployment artifacts.', 'error')
        return redirect(url_for('stage', n=1))
    return render_template('legacy_validate.html')

@app.route('/records/<int:record_id>')
@require_login
def record(record_id):
    run = require_stage(2)
    # Intentional IDOR: records are synthetic and this endpoint omits object-level ownership checks.
    records = {101:{'owner':'analyst','title':'Routine access review','body':'Quarterly review complete. Nothing unusual.'},102:{'owner':'director','title':'PHANTOM acquisition memo','body':'Synthetic memo: the archive team used the legacy account during the internal migration.'},103:{'owner':'finance','title':'Budget forecast','body':'Synthetic forecast for training purposes.'}}
    rec = records.get(record_id)
    event('idor_record_access', f'id={record_id};found={bool(rec)}')
    if not rec: abort(404)
    if record_id == 102:
        with connect_db() as db: db.execute('UPDATE exercises SET idor_done=1 WHERE run_id=?', (run['id'],))
    return render_template('record.html', record=rec, record_id=record_id)

@app.route('/stage2/role/change', methods=['GET','POST'])
@require_login
def role_change_vulnerable():
    run = require_stage(2)
    if request.method == 'POST':
        # Intentionally missing CSRF token validation only for this synthetic lab action.
        target = request.form.get('target','analyst')[:40]
        if target == 'auditor':
            with connect_db() as db: db.execute('UPDATE exercises SET csrf_done=1 WHERE run_id=?', (run['id'],))
            event('csrf_exercise_success', 'synthetic role changed to auditor')
            flash('Controlled exercise recorded: synthetic role changed to auditor.', 'success')
        else:
            event('csrf_exercise_attempt', 'invalid synthetic role'); flash('Role unchanged. Use the lab target described in the exercise.', 'error')
        return redirect(url_for('stage', n=2))
    return render_template('role_change.html')

@app.route('/archive')
@require_login
def archive():
    run = require_stage(3)
    requested = request.args.get('file','readme.txt')[:240]
    # Vulnerability is intentionally simulated: traversal syntax is accepted only as a selector
    # for a fixed synthetic artifact. No user-controlled path is ever opened on disk.
    traversal = '../' in requested or '..\\' in requested
    event('archive_access_attempt', f'traversal={traversal};selector={requested[:80]}')
    if traversal:
        content = 'PHANTOM ARCHIVE INDEX\nSynthetic evidence recovered. The archive path validation is flawed in this exercise.\n'
        with connect_db() as db: db.execute('UPDATE runs SET completed_flags=CASE WHEN instr(completed_flags,"PATH")>0 THEN completed_flags ELSE completed_flags || ",PATH" END WHERE id=?', (run['id'],))
        return render_template('archive.html', filename=requested, content=content, traversal=True)
    safe_name = Path(requested).name
    target = (CHALLENGE_DIR / safe_name).resolve()
    if CHALLENGE_DIR not in target.parents and target != CHALLENGE_DIR: abort(403)
    try: content = target.read_text(encoding='utf-8')
    except (OSError, UnicodeError): abort(404)
    return render_template('archive.html', filename=safe_name, content=content, traversal=False)

@app.route('/flags', methods=['GET','POST'])
@require_login
def flags():
    run = get_run()
    if not run: flash('Start a challenge run first.', 'error'); return redirect(url_for('dashboard'))
    if request.method == 'POST':
        stage_no = request.form.get('stage','')
        if stage_no not in ('1','2','3'): flash('Invalid stage selection.', 'error'); return redirect(url_for('flags'))
        n = int(stage_no)
        run = get_run()
        if run['status'] != 'active' or n > run['stage']:
            event('flag_order_denied', f'stage={n}'); flash('That stage is locked or this run is complete.', 'error'); return redirect(url_for('flags'))
        if not FLAGS[n-1]: flash('Owner configuration is incomplete: flags are not configured.', 'error'); return redirect(url_for('flags'))
        submitted = request.form.get('flag','').strip()
        if not hmac.compare_digest(submitted, FLAGS[n-1]):
            event('flag_failure', f'stage={n}'); flash('Flag rejected. Continue investigating the lab evidence.', 'error'); return redirect(url_for('flags'))
        if n == 1:
            with connect_db() as db: ex = db.execute('SELECT * FROM exercises WHERE run_id=?', (run['id'],)).fetchone()
            if not ex or not ex['credential_done']:
                flash('Validate the synthetic leaked credential before submitting FLAG 01.', 'error'); return redirect(url_for('flags'))
        if n == 2:
            with connect_db() as db: ex = db.execute('SELECT * FROM exercises WHERE run_id=?', (run['id'],)).fetchone()
            if not ex or not ex['idor_done'] or not ex['csrf_done']:
                flash('Complete both Stage 2 exercises before submitting this flag.', 'error'); return redirect(url_for('flags'))
        if n == 3 and 'PATH' not in (run['completed_flags'] or ''):
            flash('Retrieve the synthetic archive evidence before submitting the final flag.', 'error'); return redirect(url_for('flags'))
        with connect_db() as db:
            updated = (run['completed_flags'] + ',' if run['completed_flags'] else '') + f'FLAG{n}'
            if n < 3: db.execute('UPDATE runs SET completed_flags=?,stage=?,progress=? WHERE id=?', (updated,n+1,{1:25,2:65}[n],run['id']))
            else: db.execute('UPDATE runs SET completed_flags=?,stage=3,progress=100,status="completed",completed_at=? WHERE id=?', (updated,now(),run['id']))
        event('flag_success', f'stage={n}')
        if n == 3: return redirect(url_for('complete'))
        flash(f'FLAG 0{n} verified. Stage {n+1} unlocked.', 'success'); return redirect(url_for('dashboard'))
    return render_template('flags.html', run=run)

@app.route('/complete')
@require_login
def complete():
    run = get_run()
    if not run or run['status'] != 'completed': return redirect(url_for('dashboard'))
    return render_template('complete.html', run=run, elapsed=elapsed_seconds(run))

@app.route('/owner/events')
@require_login
def owner_events():
    # Local lab owner audit view; only authenticated account can see it.
    with connect_db() as db: rows = db.execute('SELECT event,detail,created_at FROM events WHERE user_id=? ORDER BY id DESC LIMIT 100', (session['user_id'],)).fetchall()
    return render_template('events.html', rows=rows)

@app.errorhandler(403)
def forbidden(e): return render_template('error.html', code=403, message='Access denied. This stage or action is not available yet.'), 403
@app.errorhandler(404)
def not_found(e): return render_template('error.html', code=404, message='The requested lab resource was not found.'), 404
@app.errorhandler(400)
def bad_request(e): return render_template('error.html', code=400, message='Request rejected. Refresh the page and try again.'), 400

if not APP_SECRET or not all(FLAGS) or not ADMIN_USER or not ADMIN_PASSWORD:
    log.warning('Configuration incomplete. Run scripts/init_env.py and configure .env before starting.')
init_db()
