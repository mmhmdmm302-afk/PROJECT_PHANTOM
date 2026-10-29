import os, tempfile, unittest
_tmp = tempfile.TemporaryDirectory()
os.environ['PHANTOM_DATA_DIR'] = _tmp.name
os.environ['PHANTOM_SESSION_SECRET'] = 'test-only-secret-key'
os.environ['PHANTOM_ADMIN_USER'] = 'testuser'
os.environ['PHANTOM_ADMIN_PASSWORD'] = 'test-password'
os.environ['PHANTOM_FLAG_1'] = 'PHANTOM{testflag1}'
os.environ['PHANTOM_FLAG_2'] = 'PHANTOM{testflag2}'
os.environ['PHANTOM_FLAG_3'] = 'PHANTOM{testflag3}'
from src.app import app, connect_db

class PhantomTests(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()
        self.client.post('/', data={'username':'testuser','password':'test-password'})
        with self.client.session_transaction() as sess: self.csrf = sess['csrf_token']
    def post_csrf(self, url, **data):
        data['csrf_token'] = self.csrf
        return self.client.post(url, data=data, follow_redirects=False)
    def start_run(self): self.post_csrf('/run/start')
    def validate_credential(self): return self.post_csrf('/legacy/validate', service_user='svc_legacy', service_password='ghost-in-the-machine')
    def test_health(self):
        r = self.client.get('/health'); self.assertEqual(r.status_code, 200); self.assertEqual(r.json['status'], 'ok')
    def test_stage_two_locked_at_start(self):
        self.start_run()
        self.assertEqual(self.client.get('/stage/2').status_code, 403)
        self.assertEqual(self.client.get('/stage/3').status_code, 403)
    def test_flag_one_requires_credential_exercise(self):
        self.start_run()
        self.post_csrf('/flags', stage='1', flag='PHANTOM{testflag1}')
        self.assertEqual(self.client.get('/stage/2').status_code, 403)
    def test_bad_flag_does_not_unlock(self):
        self.start_run()
        r = self.post_csrf('/flags', stage='2', flag='PHANTOM{testflag2}')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.client.get('/stage/2').status_code, 403)
    def test_idor_fixture_is_synthetic(self):
        self.start_run()
        self.validate_credential()
        self.post_csrf('/flags', stage='1', flag='PHANTOM{testflag1}')
        r = self.client.get('/records/102')
        self.assertEqual(r.status_code, 200); self.assertIn(b'Synthetic memo', r.data)
        self.assertEqual(self.client.get('/records/999').status_code, 404)
    def test_path_traversal_is_simulated(self):
        self.start_run()
        self.validate_credential()
        self.post_csrf('/flags', stage='1', flag='PHANTOM{testflag1}')
        # Mark both Stage 2 exercises and advance via server flag for route coverage.
        with connect_db() as db:
            rid = self.client.get('/dashboard').data
            # Current run id is available through session in test client.
        with self.client.session_transaction() as sess: rid = sess['run_id']
        with connect_db() as db:
            db.execute('UPDATE exercises SET idor_done=1,csrf_done=1 WHERE run_id=?', (rid,))
        self.post_csrf('/flags', stage='2', flag='PHANTOM{testflag2}')
        r = self.client.get('/archive?file=../../etc/passwd')
        self.assertEqual(r.status_code, 200)
        self.assertNotIn(b'root:x:', r.data)
        self.assertIn(b'Synthetic evidence recovered', r.data)

if __name__ == '__main__': unittest.main()
