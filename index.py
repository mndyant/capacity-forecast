"""Vercel WSGI entrypoint; local development still uses run.py."""
from app import create_app

app = create_app()
