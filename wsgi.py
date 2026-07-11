"""
PathFinder — WSGI entry point for production servers (gunicorn, uWSGI).
"""
from app import create_app

application = create_app()
app = application
