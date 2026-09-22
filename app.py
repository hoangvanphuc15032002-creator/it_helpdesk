"""
Root Web Dashboard Runner Entrypoint
Delegates application creation to web.app_factory.
"""
from web.app_factory import create_app, init_web_db
from database.connection import get_db_connection

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)