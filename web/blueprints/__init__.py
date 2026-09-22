"""
Flask Blueprints Package
Registers all Web Dashboard modular blueprints onto the Flask application.
"""
from web.blueprints.auth import auth_bp
from web.blueprints.views import views_bp
from web.blueprints.tickets import tickets_bp
from web.blueprints.staff_users import staff_users_bp
from web.blueprints.system import system_bp

ALL_BLUEPRINTS = [auth_bp, views_bp, tickets_bp, staff_users_bp, system_bp]

def register_blueprints(app):
    for bp in ALL_BLUEPRINTS:
        app.register_blueprint(bp)
