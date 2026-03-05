"""
Session Factory - Creates GameSession instances with all dependencies.

Simplifies session creation by centralizing dependency setup.
"""
from typing import Optional
from dataclasses import dataclass


@dataclass
class SessionConfig:
    """Configuration for creating a game session."""
    session_id: str
    enable_spatial: bool = True
    enable_learning: bool = True
    auto_approve_patterns: bool = False


def create_session(config: SessionConfig):
    """
    Create a fully-configured GameSession.

    Args:
        config: SessionConfig with session parameters

    Returns:
        GameSession instance with all agents wired
    """
    from game.game_session import GameSession

    return GameSession(
        session_id=config.session_id,
        config=config
    )
