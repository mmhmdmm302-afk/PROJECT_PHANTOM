import os
from src.app import app

if __name__ == '__main__':
    # Local development binds to loopback. Docker explicitly overrides PHANTOM_HOST.
    app.run(host=os.environ.get('PHANTOM_HOST', '127.0.0.1'), port=int(os.environ.get('PHANTOM_PORT', '8000')), debug=False)
