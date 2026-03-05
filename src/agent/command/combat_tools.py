"""
Combat-related tools for the Command Agent.

Handles damage, healing, combat management, initiative, and conditions.
Also includes ISSUE 9 fix: dead monsters are removed from spatial system.
"""
from typing import Dict, Optional


def tool_create_monster(game_state, name: str, hp: int, ac: int, cr: float) -> Dict:
    """Create a monster."""
    from domain.game_state import Monster

    monster = Monster(name=name, hp=hp, max_hp=hp, ac=ac, cr=cr)
    game_state.add_monster(monster)

    return {
        'tool': 'create_monster',
        'status': 'success',
        'name': name,
        'details': f"{name} (CR {cr}) - HP: {hp}/{hp}, AC: {ac}"
    }


def tool_apply_damage(game_state, name: str, damage: int, damage_type: str = "untyped",
                       spatial_agent=None) -> Dict:
    """Apply damage to a creature. Removes dead monsters from spatial system (ISSUE 9 fix)."""
    success = game_state.damage_entity(name, damage)

    if success:
        entity = game_state.get_character(name) or game_state.get_monster(name)
        defeated = entity.hp <= 0 if entity else False

        # ISSUE 9 FIX: Remove dead monster from spatial system
        if defeated and spatial_agent:
            monster = game_state.get_monster(name)
            if monster:
                _remove_dead_monster_from_spatial(spatial_agent, name)

        return {
            'tool': 'apply_damage',
            'status': 'success',
            'name': name,
            'damage': damage,
            'damage_type': damage_type,
            'defeated': defeated
        }
    else:
        return {'tool': 'apply_damage', 'status': 'error', 'error': 'Entity not found'}


def tool_heal_character(game_state, name: str, healing: int, source: str = None) -> Dict:
    """Heal a character."""
    success = game_state.heal_entity(name, healing)

    if success:
        return {
            'tool': 'heal_character',
            'status': 'success',
            'name': name,
            'healing': healing,
            'source': source
        }
    else:
        return {'tool': 'heal_character', 'status': 'error', 'error': 'Entity not found'}


def tool_start_combat(game_state) -> Dict:
    """Start combat."""
    game_state.start_combat()
    return {'tool': 'start_combat', 'status': 'success'}


def tool_set_initiative(game_state, name: str, initiative: int) -> Dict:
    """Set initiative for a creature."""
    entity_type = "monster" if game_state.get_monster(name) else "character"
    game_state.set_initiative(name, initiative, entity_type)

    return {
        'tool': 'set_initiative',
        'status': 'success',
        'name': name,
        'initiative': initiative
    }


def tool_add_condition(game_state, name: str, condition: str) -> Dict:
    """Add a condition to a creature."""
    success = game_state.add_condition(name, condition)

    if success:
        return {
            'tool': 'add_condition',
            'status': 'success',
            'name': name,
            'condition': condition
        }
    else:
        return {'tool': 'add_condition', 'status': 'error', 'error': 'Entity not found'}


def tool_remove_condition(game_state, name: str, condition: str) -> Dict:
    """Remove a condition from a creature."""
    success = game_state.remove_condition(name, condition)

    if success:
        return {
            'tool': 'remove_condition',
            'status': 'success',
            'name': name,
            'condition': condition
        }
    else:
        return {'tool': 'remove_condition', 'status': 'error', 'error': 'Entity not found'}


def _remove_dead_monster_from_spatial(spatial_agent, monster_name: str):
    """Remove a dead monster from the spatial system (ISSUE 9 fix)."""
    try:
        entity = spatial_agent.get_entity_by_creature_id(monster_name)
        if entity:
            entity_id = entity.get('id') or entity.get('entity_id')
            if entity_id:
                spatial_agent.remove_entity(entity_id)
                print(f"[Spatial] Removed dead monster '{monster_name}' from spatial system")
    except Exception as e:
        print(f"[Spatial] Failed to remove dead monster '{monster_name}': {e}")
