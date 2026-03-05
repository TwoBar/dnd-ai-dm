"""Spell casting tools for the DM agent"""
import logging
from typing import Optional

from game.dice import DiceRoller

logger = logging.getLogger(__name__)

dice_roller = DiceRoller()


def cast_spell(
    spell_name: str,
    character_name: str = "",
    target: Optional[str] = None,
    slot_level: Optional[int] = None,
    game_state=None,
    spatial_agent=None,
    session_id: Optional[str] = None,
) -> dict:
    """
    Cast a spell by name, automatically looking up damage/effects and rolling dice.

    Args:
        spell_name: Name of the spell (e.g. "Fireball", "Magic Missile")
        character_name: Name of the caster
        target: Optional target name
        slot_level: Optional spell slot level for upcasting
        game_state: Optional GameState for applying damage
        spatial_agent: Optional SpatialAgent (unused for now)
        session_id: Optional session ID

    Returns:
        Dictionary with cast result
    """
    # Look up spell in reference DB
    spell_data = _lookup_spell(spell_name)

    if not spell_data or spell_data.get('error'):
        # Spell not found — still allow a generic cast with narrative
        return {
            'action': 'cast_spell',
            'spell_name': spell_name,
            'caster': character_name,
            'target': target,
            'status': 'success',
            'success': True,
            'note': f"Spell '{spell_name}' not found in reference DB; DM will narrate effects.",
            'rolls': [],
        }

    damage_dice = spell_data.get('damage')
    save_type = spell_data.get('save')
    spell_level = spell_data.get('level', 0)
    cast_level = slot_level if slot_level and slot_level >= spell_level else spell_level

    rolls = []
    total_damage = 0

    # Roll damage if the spell has a damage component
    if damage_dice:
        # Handle upcasting: many spells add 1dX per level above base
        effective_dice = _scale_damage(damage_dice, spell_level, cast_level)
        try:
            result = dice_roller.roll(effective_dice)
            total_damage = result.total
            rolls.append({
                'type': 'damage',
                'notation': effective_dice,
                'total': result.total,
                'rolls': result.rolls,
                'description': str(result),
            })
        except Exception as e:
            logger.warning("Failed to roll spell damage %s: %s", effective_dice, e)

    # Apply damage to target if we have game_state
    damage_applied = False
    if total_damage > 0 and target and game_state:
        entity = game_state.get_character(target) or game_state.get_monster(target)
        if entity:
            game_state.damage_entity(target, total_damage)
            damage_applied = True

    return {
        'action': 'cast_spell',
        'spell_name': spell_data.get('name', spell_name),
        'caster': character_name,
        'target': target,
        'spell_level': spell_level,
        'cast_level': cast_level,
        'damage': total_damage,
        'damage_dice': damage_dice,
        'save': save_type,
        'damage_applied': damage_applied,
        'rolls': rolls,
        'description': spell_data.get('description', '')[:200],
        'status': 'success',
        'success': True,
    }


def _lookup_spell(spell_name: str) -> Optional[dict]:
    """Look up a spell in the reference database."""
    try:
        from tools.entity_tools import get_spell
        return get_spell(spell_name)
    except Exception as e:
        logger.warning("Spell lookup failed for '%s': %s", spell_name, e)
        return None


def _scale_damage(base_dice: str, base_level: int, cast_level: int) -> str:
    """Scale spell damage for upcasting.

    Simple heuristic: if the spell has a pattern like '8d6',
    add 1dX per level above base (common 5e pattern).
    """
    if cast_level <= base_level:
        return base_dice

    # Parse base dice (e.g. "8d6" -> count=8, sides=6)
    import re
    match = re.match(r'(\d+)d(\d+)', base_dice)
    if not match:
        return base_dice

    count = int(match.group(1))
    sides = int(match.group(2))
    extra = cast_level - base_level
    new_count = count + extra
    # Preserve any suffix (e.g. "+3")
    suffix = base_dice[match.end():]
    return f"{new_count}d{sides}{suffix}"


# ============================================================================
# TOOL DEFINITIONS (OpenAI Function Calling format)
# ============================================================================

SPELL_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "cast_spell",
            "description": "Cast a spell by name. Automatically looks up the spell, rolls damage dice, and optionally applies damage to a target.",
            "parameters": {
                "type": "object",
                "properties": {
                    "spell_name": {
                        "type": "string",
                        "description": "Name of the spell to cast (e.g., 'Fireball', 'Magic Missile', 'Cure Wounds')"
                    },
                    "character_name": {
                        "type": "string",
                        "description": "Name of the character casting the spell"
                    },
                    "target": {
                        "type": "string",
                        "description": "Target of the spell (creature or object name)"
                    },
                    "slot_level": {
                        "type": "integer",
                        "description": "Spell slot level used (for upcasting). Defaults to spell's base level."
                    }
                },
                "required": ["spell_name"]
            }
        }
    }
]

SPELL_FUNCTION_MAP = {
    "cast_spell": cast_spell,
}
