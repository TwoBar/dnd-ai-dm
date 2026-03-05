"""
Web Server - Re-export facade.

The implementation has moved to ui/web/ package.
This file maintains backward compatibility for existing imports.
"""
from ui.web.app import create_app, main

__all__ = ['create_app', 'main']

if __name__ == '__main__':
    main()
