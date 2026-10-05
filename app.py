"""
Root Web Dashboard Runner Entrypoint
Delegates application creation to web.app_factory.
"""
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

from web.app_factory import create_app, init_web_db
from database.connection import get_db_connection

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)