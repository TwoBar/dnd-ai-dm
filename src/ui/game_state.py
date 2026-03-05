"""
Re-export facade - Domain models moved to domain/game_state.py

All imports from ui.game_state still work for backward compatibility.
New code should import from domain.game_state directly.
"""
from domain.game_state import (
    Character,
    Monster,
    DiceRoll,
    CombatEvent,
    GameState,
)

__all__ = ['Character', 'Monster', 'DiceRoll', 'CombatEvent', 'GameState']
