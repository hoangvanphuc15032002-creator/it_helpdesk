"""
Flask Web Dashboard Routes (Facade)
Provides backward-compatibility interface delegating to web.blueprints and web.middleware.
"""
from web.middleware import login_required
from web.blueprints import register_blueprints

def register_routes(app):
    """
    Backward-compatibility wrapper registering all modular Flask Blueprints.
    """
    register_blueprints(app)
