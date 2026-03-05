"""
GameState serialization for the web frontend.

Converts GameState objects to JSON-serializable dictionaries.
"""
from game.game_session import GameSession


def serialize_game_state(session: GameSession) -> dict:
    """Serialize a GameSession's state for the frontend."""
    game_state = session.game_state

    return {
        'characters': [
            {
                'name': char.name,
                'class': char.class_name,
                'level': char.level,
                'hp': char.hp,
                'max_hp': char.max_hp,
                'ac': char.ac,
                'conditions': char.conditions,
                'initiative': char.initiative,
                'race': char.race,
                'ability_scores': char.ability_scores,
                'background': char.background,
                'is_draft': char.is_draft,
            }
            for char in game_state.characters
        ],
        'monsters': [
            {
                'name': monster.name,
                'hp': monster.hp,
                'max_hp': monster.max_hp,
                'ac': monster.ac,
                'cr': monster.cr,
                'conditions': monster.conditions,
                'initiative': monster.initiative
            }
            for monster in game_state.monsters
        ],
        'combat': {
            'active': game_state.in_combat,
            'round': game_state.round_number,
            'current_turn': game_state.current_turn,
            'initiative_order': game_state.get_initiative_order() if hasattr(game_state, 'get_initiative_order') else []
        },
        'dice_rolls': [
            {
                'notation': roll.notation,
                'result': roll.result,
                'context': getattr(roll, 'context', ''),
                'timestamp': roll.timestamp.isoformat()
            }
            for roll in game_state.dice_rolls[-10:]
        ],
        'stats': {
            'cache_hit_rate': '0%',
            'total_characters': len(game_state.characters),
            'total_monsters': len(game_state.monsters)
        }
    }
