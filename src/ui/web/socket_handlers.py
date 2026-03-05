"""
WebSocket event handlers for the web UI.

Handles connect, disconnect, session management, and messaging events.
"""
import json
import logging
import os
import traceback
from datetime import datetime
from typing import Optional
from flask import request
from flask_socketio import emit, join_room, leave_room

logger = logging.getLogger(__name__)

# --- Gameplay logging for the monitoring agent ---
_GAMEPLAY_LOG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    'data', 'agent', 'gameplay.jsonl'
)


def _log_gameplay(session_id, event_type, data):
    """Append a gameplay event for the monitoring agent to read.

    Events: player_input, dm_response, system_msg, error,
            combat_action, dice_roll, game_state_change
    """
    try:
        os.makedirs(os.path.dirname(_GAMEPLAY_LOG), exist_ok=True)
        entry = {
            'ts': datetime.utcnow().isoformat(),
            'session_id': session_id,
            'event': event_type,
            'data': data,
        }
        with open(_GAMEPLAY_LOG, 'a') as f:
            f.write(json.dumps(entry) + '\n')
    except Exception:
        pass  # never break the game for logging

from game.game_session import GameSession, SessionConfig
from ui.web.serializers import serialize_game_state
from ui.web.commands import handle_command

# Session management - keyed by session_id (not socket_id)
sessions = {}  # {session_id: GameSession}

# Map socket_id -> session_id for fast lookup
_socket_to_session = {}  # {socket_id: session_id}


def _default_config() -> SessionConfig:
    return SessionConfig(
        enable_learning=os.getenv('ENABLE_LEARNING', 'false').lower() == 'true',
        auto_approve_patterns=False,
        enable_spatial=True,
    )


def _create_new_session() -> GameSession:
    """Create a brand-new game session with a fresh UUID."""
    import uuid
    session_id = str(uuid.uuid4())
    config = _default_config()
    session = GameSession(session_id, config)
    sessions[session_id] = session
    logger.info("Created new session %s", session_id)
    return session


def _bind_socket(socket_id: str, session_id: str):
    """Bind a socket_id to a session_id and join the location room."""
    _socket_to_session[socket_id] = session_id
    # Join location-based room so all sessions in same location get map updates
    join_room('room:tavern_main', sid=socket_id)


def _get_session_for_socket(socket_id: str) -> Optional[GameSession]:
    """Get the GameSession bound to this socket, if any."""
    sid = _socket_to_session.get(socket_id)
    if sid:
        return sessions.get(sid)
    return None


def broadcast_map_to_location(socketio, location_id: str, exclude_sid: str = None):
    """Broadcast map update to all sockets in a location room.

    Each socket gets a map built for *its own* session so is_own_session
    flags are correct per-viewer.
    """
    room_name = f'room:{location_id}'
    # Get all socket_ids in the room
    try:
        room_sids = socketio.server.manager.get_participants('/', room_name)
    except Exception:
        room_sids = []

    for sid_tuple in room_sids:
        sid = sid_tuple[0] if isinstance(sid_tuple, tuple) else sid_tuple
        if sid == exclude_sid:
            continue
        session_id = _socket_to_session.get(sid)
        if not session_id:
            continue
        session = sessions.get(session_id)
        if not session or not session.spatial_agent:
            continue
        try:
            from game.workflow.map_builder import build_map_state
            map_state = build_map_state(session.spatial_agent, session_id, location_id)
            if map_state:
                socketio.emit('map_update', map_state, to=sid)
        except Exception as e:
            logger.warning("Failed to broadcast map to %s: %s", sid, e)


def emit_session_state(session: GameSession):
    """Send full session state to the current client."""
    emit('session_ready', {'session_id': session.session_id})
    emit('game_state', serialize_game_state(session))

    # Send message history as new_message events so they render properly
    for msg in session.message_history:
        role = msg.get('role', '')
        if role in ('player', 'user'):
            speaker = 'You'
            msg_type = 'user'
        elif role in ('dm', 'assistant'):
            speaker = 'DM'
            msg_type = 'dm'
        else:
            speaker = 'System'
            msg_type = 'system'
        emit('new_message', {
            'timestamp': msg.get('timestamp', datetime.now().isoformat()),
            'speaker': speaker,
            'message': msg.get('content', ''),
            'type': msg_type,
        })

    # Send map state if spatial is available
    if session.spatial_agent:
        try:
            from game.workflow.map_builder import build_map_state
            map_state = build_map_state(session.spatial_agent, session.session_id, 'tavern_main')
            if map_state:
                emit('map_update', map_state)
        except Exception as e:
            logger.warning("Failed to build map state during session emit: %s", e)


def get_available_sessions():
    """Query DB for sessions with character info.

    Uses the REAL schema: sessions.status, sessions.last_played_at,
    and session_game_characters (our persistence table).
    """
    try:
        from game.game_session import _db_query

        rows = _db_query("""
            SELECT s.id, s.name, s.last_played_at,
                   GROUP_CONCAT(c.name, ', ') as character_names,
                   GROUP_CONCAT(c.class_name, ', ') as character_classes
            FROM sessions s
            LEFT JOIN session_game_characters c ON c.session_id = s.id
            WHERE s.status = 'active'
            GROUP BY s.id
            ORDER BY s.last_played_at DESC
            LIMIT 10
        """)

        # Count connected sockets per session
        connected_counts = {}
        for sock_id, sess_id in _socket_to_session.items():
            connected_counts[sess_id] = connected_counts.get(sess_id, 0) + 1

        result = []
        for row in rows:
            sid = row['id']
            online = connected_counts.get(sid, 0)
            result.append({
                'session_id': sid,
                'name': row['name'],
                'last_played': row.get('last_played_at', ''),
                'characters': row.get('character_names', '') or 'No characters',
                'classes': row.get('character_classes', '') or '',
                'players_online': online,
            })
        return result
    except Exception as e:
        logger.error("Failed to query available sessions: %s", e, exc_info=True)
        return []


def register_handlers(socketio):
    """Register all WebSocket event handlers."""

    @socketio.on('connect')
    def handle_connect():
        socket_id = request.sid
        logger.info("Client connected: %s", socket_id)
        # Client will send resume_session or list_sessions next

    @socketio.on('disconnect')
    def handle_disconnect():
        socket_id = request.sid
        logger.info("Client disconnected: %s", socket_id)
        # Leave location room
        leave_room('room:tavern_main', sid=socket_id)
        # Remove socket mapping but keep session alive in memory
        _socket_to_session.pop(socket_id, None)

    @socketio.on('resume_session')
    def handle_resume(data):
        """Client wants to resume a specific session."""
        socket_id = request.sid
        session_id = data.get('session_id', '') if data else ''
        logger.info("resume_session from %s, session_id=%s", socket_id, session_id[:12] if session_id else '(none)')

        if not session_id:
            emit('session_list', {'sessions': get_available_sessions()})
            return

        # Fast path: session still in memory
        if session_id in sessions:
            _bind_socket(socket_id, session_id)
            logger.info("Resumed in-memory session %s for socket %s", session_id, socket_id)
            emit_session_state(sessions[session_id])
            return

        # Slow path: recover from DB
        try:
            config = _default_config()
            session = GameSession.recover(session_id, config)
            sessions[session_id] = session
            _bind_socket(socket_id, session_id)
            logger.info("Recovered session %s from DB for socket %s", session_id, socket_id)
            emit_session_state(session)
        except Exception as e:
            logger.warning("Failed to recover session %s: %s", session_id, e, exc_info=True)
            # Clear stale session from client
            emit('session_expired', {'session_id': session_id})
            emit('session_list', {'sessions': get_available_sessions()})

    @socketio.on('list_sessions')
    def handle_list(data=None):
        """Client wants to see available sessions."""
        logger.info("list_sessions from %s", request.sid)
        try:
            emit('session_list', {'sessions': get_available_sessions()})
        except Exception as e:
            logger.error("list_sessions failed: %s", e, exc_info=True)
            emit('session_list', {'sessions': []})

    @socketio.on('new_session')
    def handle_new(data=None):
        """Client wants to start a new adventure."""
        socket_id = request.sid
        logger.info("new_session from %s", socket_id)
        try:
            session = _create_new_session()
            _bind_socket(socket_id, session.session_id)
            emit_session_state(session)
        except Exception as e:
            logger.error("new_session failed: %s", e, exc_info=True)
            emit('new_message', {
                'timestamp': datetime.now().isoformat(),
                'speaker': 'System',
                'message': f'Failed to create session: {e}',
                'type': 'error',
            })

    @socketio.on('leave_session')
    def handle_leave(data=None):
        """Client wants to leave current session (switch sessions)."""
        socket_id = request.sid
        logger.info("leave_session from %s", socket_id)
        # Leave location room
        leave_room('room:tavern_main', sid=socket_id)
        # Remove socket mapping but keep GameSession alive for resume
        _socket_to_session.pop(socket_id, None)

    @socketio.on('select_session')
    def handle_select(data):
        """Client selected a session from the picker (same as resume)."""
        logger.info("select_session from %s", request.sid)
        handle_resume(data)

    @socketio.on('send_message')
    def handle_message(data):
        socket_id = request.sid
        user_message = data.get('message', '').strip()

        if not user_message:
            return

        session = _get_session_for_socket(socket_id)
        if not session:
            emit('new_message', {
                'timestamp': datetime.now().isoformat(),
                'speaker': 'System',
                'message': 'No active session. Please refresh the page.',
                'type': 'error',
            })
            return

        # Slash commands
        if user_message.startswith('/'):
            handle_command(user_message, session, socketio, emit, serialize_game_state)
            return

        # Log player input for the monitoring agent
        _log_gameplay(session.session_id, 'player_input', {'message': user_message})

        # User message
        emit('new_message', {
            'timestamp': datetime.now().isoformat(),
            'speaker': 'You',
            'message': user_message,
            'type': 'user',
        })

        # Process through workflow
        try:
            logger.info("Session %s processing: %s", session.session_id, user_message)
            result = session.process_message(user_message)

            dm_response = result.get('dm_response', '')

            if 'metrics' in result:
                metrics = result['metrics']
                logger.info("Session %s complete in %.2fs", session.session_id, metrics.get('total', 0))

            if result.get('mechanics_summary'):
                logger.debug("Mechanics summary:\n%s", result['mechanics_summary'])

            # Log DM response for the monitoring agent
            _log_gameplay(session.session_id, 'dm_response', {
                'message': dm_response,
                'intent': result.get('intent_type', ''),
                'mechanics': result.get('mechanics_summary', ''),
            })

            emit('new_message', {
                'timestamp': datetime.now().isoformat(),
                'speaker': 'DM',
                'message': dm_response,
                'type': 'dm',
            })

            if 'map_state' in result and result['map_state']:
                emit('map_update', result['map_state'])
                # Broadcast updated map to other sessions in the same location
                broadcast_map_to_location(socketio, 'tavern_main', exclude_sid=socket_id)

            # Log game state changes
            if result.get('map_state'):
                _log_gameplay(session.session_id, 'game_state_change', {
                    'type': 'map_update',
                    'has_map': True,
                })

            emit('game_state', serialize_game_state(session))

            # Signal that processing is done (for input debounce)
            emit('processing_done', {})

        except Exception as e:
            logger.error("Session %s error: %s", session.session_id, e, exc_info=True)

            # Log error for the monitoring agent
            _log_gameplay(session.session_id, 'error', {
                'error': str(e),
                'traceback': traceback.format_exc(),
            })

            emit('new_message', {
                'timestamp': datetime.now().isoformat(),
                'speaker': 'System',
                'message': f'Error: {str(e)}',
                'type': 'error',
            })

            emit('processing_done', {})

    return sessions  # Return sessions for cleanup
