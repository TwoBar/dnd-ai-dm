"""
Flask application factory and entry point.

Creates the Flask app, SocketIO, and registers all handlers.
"""
from pathlib import Path
from flask import Flask, render_template
from flask_socketio import SocketIO

from ui.web.socket_handlers import register_handlers


def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__,
                template_folder=str(Path(__file__).parent.parent / 'templates'),
                static_folder=str(Path(__file__).parent.parent / 'static'))
    app.config['SECRET_KEY'] = 'dnd-ai-dm-secret-key'

    socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=120, ping_interval=25)

    @app.route('/')
    def index():
        return render_template('index.html')

    sessions = register_handlers(socketio)

    return app, socketio, sessions


def main():
    """Run the web server."""
    from core.logging_config import setup_logging
    from config import LOG_LEVEL
    setup_logging(LOG_LEVEL)

    print("D&D AI Dungeon Master - Web UI")
    print("=" * 50)
    print("\n  Spatial system enabled with emoji sprites")
    print("Starting web server...")
    print("\n  Open in your browser:")
    print("   http://localhost:5001")
    print("\nPress Ctrl+C to stop\n")

    app, socketio, sessions = create_app()

    try:
        socketio.run(app, host='0.0.0.0', port=5001, debug=False)
    finally:
        print("\n\nShutting down...")
        print(f"Cleaning up {len(sessions)} session(s)...")
        for session_id, session in sessions.items():
            try:
                session.cleanup()
            except Exception as e:
                print(f"Error cleaning up session {session_id}: {e}")
        print("Goodbye!")


if __name__ == '__main__':
    main()
