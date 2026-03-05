"""
Web UI package - split from the monolithic web_server.py.
"""
from ui.web.app import create_app, main

__all__ = ['create_app', 'main']
