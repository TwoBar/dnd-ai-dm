"""
Character creation and management tools for the Command Agent.

Handles draft_character, update_draft_character, and finalize_character.
"""
import logging
import random
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def tool_draft_character(
    game_state,
    name: str,
    race: str,
    class_name: str,
    level: int,
    ability_scores=None,
    background: str = None
) -> Dict:
    """Create or update a draft character."""
    from domain.game_state import Character

    ability_scores = _resolve_ability_scores(ability_scores, class_name)

    con_mod = (ability_scores.get('CON', 10) - 10) // 2
    dex_mod = (ability_scores.get('DEX', 10) - 10) // 2

    hp = 8 + con_mod + (level - 1) * (5 + con_mod)
    ac = 10 + dex_mod

    spell_slots = _get_spell_slots(class_name, level)
    spells_known = _get_default_spells(class_name, level)

    existing = game_state.get_character(name)
    if existing:
        existing.race = race
        existing.class_name = class_name
        existing.level = level
        existing.hp = hp
        existing.max_hp = hp
        existing.ac = ac
        existing.ability_scores = ability_scores
        existing.background = background
        existing.spell_slots = spell_slots or None
        existing.spells_known = spells_known or None
        existing.is_draft = True
    else:
        char = Character(
            name=name,
            class_name=class_name,
            level=level,
            hp=hp,
            max_hp=hp,
            ac=ac,
            race=race,
            ability_scores=ability_scores,
            background=background,
            is_draft=True,
            spell_slots=spell_slots or None,
            spells_known=spells_known or None,
        )
        game_state.add_character(char)
        logger.info("Created draft character: %s (Lvl %d %s) with %d spell slots, %d spells",
                     name, level, class_name, sum(spell_slots.values()) if spell_slots else 0, len(spells_known))

    return {
        'tool': 'draft_character',
        'status': 'success',
        'name': name,
        'details': f"Draft: {name} (Lvl {level} {race} {class_name})"
    }


def tool_update_draft_character(game_state, name: str, updates: Dict) -> Dict:
    """Update a draft character."""
    char = game_state.get_character(name)
    if not char:
        return {'tool': 'update_draft_character', 'status': 'error', 'error': 'Character not found'}

    if not getattr(char, 'is_draft', False):
        return {'tool': 'update_draft_character', 'status': 'error', 'error': 'Character is finalized'}

    for key, value in updates.items():
        if key == 'ability_scores':
            char.ability_scores = value
            con_mod = (value.get('CON', 10) - 10) // 2
            dex_mod = (value.get('DEX', 10) - 10) // 2
            char.max_hp = 8 + con_mod + (char.level - 1) * (5 + con_mod)
            char.hp = char.max_hp
            char.ac = 10 + dex_mod
        else:
            setattr(char, key, value)

    return {
        'tool': 'update_draft_character',
        'status': 'success',
        'name': name
    }


def tool_finalize_character(game_state, name: str, hp: int = None, ac: int = None) -> Dict:
    """Finalize a draft character."""
    char = game_state.get_character(name)
    if not char:
        return {'tool': 'finalize_character', 'status': 'error', 'error': 'Character not found'}

    if hp:
        char.max_hp = hp
        char.hp = hp
    if ac:
        char.ac = ac

    char.is_draft = False

    return {
        'tool': 'finalize_character',
        'status': 'success',
        'name': name,
        'details': f"Finalized: {name} (Lvl {char.level} {char.class_name}) - HP: {char.hp}/{char.max_hp}, AC: {char.ac}"
    }


# ========================================================================
# Ability Score Resolution
# ========================================================================

# Standard array assignments per class archetype
_CLASS_ARRAYS = {
    'caster_int': {'STR': 8, 'DEX': 13, 'CON': 12, 'INT': 15, 'WIS': 10, 'CHA': 14},
    'caster_cha': {'STR': 13, 'DEX': 10, 'CON': 12, 'INT': 8, 'WIS': 14, 'CHA': 15},
    'martial_str': {'STR': 15, 'DEX': 14, 'CON': 13, 'INT': 8, 'WIS': 10, 'CHA': 12},
    'martial_dex': {'STR': 10, 'DEX': 15, 'CON': 12, 'INT': 13, 'WIS': 14, 'CHA': 8},
    'caster_wis': {'STR': 10, 'DEX': 12, 'CON': 13, 'INT': 8, 'WIS': 15, 'CHA': 14},
    'balanced': {'STR': 13, 'DEX': 14, 'CON': 15, 'INT': 10, 'WIS': 12, 'CHA': 8},
}

_CLASS_ARCHETYPE = {
    'wizard': 'caster_int', 'sorcerer': 'caster_int',
    'bard': 'caster_cha', 'warlock': 'caster_cha', 'paladin': 'caster_cha',
    'fighter': 'martial_str', 'barbarian': 'martial_str', 'ranger': 'martial_str',
    'rogue': 'martial_dex', 'monk': 'martial_dex',
    'cleric': 'caster_wis', 'druid': 'caster_wis',
}

# Roll priority per class archetype
_ROLL_PRIORITY = {
    'caster_int': ['INT', 'DEX', 'CON', 'CHA', 'WIS', 'STR'],
    'caster_cha': ['CHA', 'STR', 'CON', 'DEX', 'WIS', 'INT'],
    'martial_str': ['STR', 'CON', 'DEX', 'WIS', 'CHA', 'INT'],
    'martial_dex': ['DEX', 'WIS', 'CON', 'INT', 'CHA', 'STR'],
    'caster_wis': ['WIS', 'CON', 'DEX', 'CHA', 'INT', 'STR'],
    'balanced': ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA'],
}


def _resolve_ability_scores(ability_scores, class_name: str) -> Dict[str, int]:
    """Resolve ability scores from various input formats."""
    if ability_scores is None:
        return {'STR': 15, 'DEX': 14, 'CON': 13, 'INT': 12, 'WIS': 10, 'CHA': 8}

    if isinstance(ability_scores, dict):
        return ability_scores

    if isinstance(ability_scores, str):
        archetype = _CLASS_ARCHETYPE.get(class_name.lower(), 'balanced')
        method = ability_scores.lower()

        if method in ['standard_array', 'standard']:
            return dict(_CLASS_ARRAYS[archetype])

        elif method in ['point_buy', 'point buy']:
            return dict(_CLASS_ARRAYS[archetype])

        elif method == 'roll':
            def roll_stat():
                rolls = sorted([random.randint(1, 6) for _ in range(4)])
                return sum(rolls[1:])

            stats = sorted([roll_stat() for _ in range(6)], reverse=True)
            priority = _ROLL_PRIORITY[archetype]
            return {ability: stats[i] for i, ability in enumerate(priority)}

    # Unknown format, return defaults
    return {'STR': 10, 'DEX': 10, 'CON': 10, 'INT': 10, 'WIS': 10, 'CHA': 10}


# ========================================================================
# Spell Slot Tables (5e SRD)
# ========================================================================

# Full casters: bard, cleric, druid, sorcerer, wizard
# Half casters: paladin (from lvl 2), ranger (from lvl 2)
# Pact magic: warlock (separate system)
# No casting: barbarian, fighter, monk, rogue

# spell_slots_by_level[class_type][character_level] = {spell_level: num_slots}
_FULL_CASTER_SLOTS = {
    1:  {1: 2},
    2:  {1: 3},
    3:  {1: 4, 2: 2},
    4:  {1: 4, 2: 3},
    5:  {1: 4, 2: 3, 3: 2},
    6:  {1: 4, 2: 3, 3: 3},
    7:  {1: 4, 2: 3, 3: 3, 4: 1},
    8:  {1: 4, 2: 3, 3: 3, 4: 2},
    9:  {1: 4, 2: 3, 3: 3, 4: 3, 5: 1},
    10: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2},
}

_HALF_CASTER_SLOTS = {
    1:  {},
    2:  {1: 2},
    3:  {1: 3},
    4:  {1: 3},
    5:  {1: 4, 2: 2},
    6:  {1: 4, 2: 2},
    7:  {1: 4, 2: 3},
    8:  {1: 4, 2: 3},
    9:  {1: 4, 2: 3, 3: 2},
    10: {1: 4, 2: 3, 3: 2},
}

_CASTER_TYPE = {
    'bard': 'full', 'cleric': 'full', 'druid': 'full',
    'sorcerer': 'full', 'wizard': 'full',
    'paladin': 'half', 'ranger': 'half',
}

# Number of cantrips known per class at each level (simplified)
_CANTRIPS_KNOWN = {
    'bard':     {1: 2, 2: 2, 3: 2, 4: 3, 5: 3, 10: 4},
    'cleric':   {1: 3, 2: 3, 3: 3, 4: 4, 5: 4, 10: 5},
    'druid':    {1: 2, 2: 2, 3: 2, 4: 3, 5: 3, 10: 4},
    'sorcerer': {1: 4, 2: 4, 3: 4, 4: 5, 5: 5, 10: 6},
    'wizard':   {1: 3, 2: 3, 3: 3, 4: 4, 5: 4, 10: 5},
    'warlock':  {1: 2, 2: 2, 3: 2, 4: 3, 5: 3, 10: 4},
}

# Default starting spells per class (cantrips + 1st level)
_DEFAULT_SPELLS = {
    'bard': {
        'cantrips': ['vicious-mockery', 'minor-illusion'],
        'spells': ['healing-word', 'thunderwave', 'charm-person', 'faerie-fire'],
    },
    'cleric': {
        'cantrips': ['sacred-flame', 'guidance', 'light'],
        'spells': ['cure-wounds', 'bless', 'shield-of-faith', 'guiding-bolt'],
    },
    'druid': {
        'cantrips': ['druidcraft', 'produce-flame'],
        'spells': ['cure-wounds', 'entangle', 'faerie-fire', 'thunderwave'],
    },
    'sorcerer': {
        'cantrips': ['fire-bolt', 'mage-hand', 'prestidigitation', 'light'],
        'spells': ['magic-missile', 'shield'],
    },
    'wizard': {
        'cantrips': ['fire-bolt', 'mage-hand', 'prestidigitation'],
        'spells': ['magic-missile', 'shield', 'mage-armor', 'detect-magic', 'sleep', 'thunderwave'],
    },
    'warlock': {
        'cantrips': ['eldritch-blast', 'minor-illusion'],
        'spells': ['hex', 'armor-of-agathys'],
    },
    'paladin': {
        'cantrips': [],
        'spells': ['cure-wounds', 'bless', 'shield-of-faith', 'thunderous-smite'],
    },
    'ranger': {
        'cantrips': [],
        'spells': ['cure-wounds', 'hunters-mark', 'ensnaring-strike'],
    },
}


def _get_spell_slots(class_name: str, level: int) -> Dict[int, int]:
    """Get spell slots for a class at a given level."""
    caster_type = _CASTER_TYPE.get(class_name.lower())
    if not caster_type:
        return {}

    table = _FULL_CASTER_SLOTS if caster_type == 'full' else _HALF_CASTER_SLOTS
    # Clamp to max level in table
    clamped = min(level, max(table.keys()))
    return dict(table.get(clamped, {}))


def _get_default_spells(class_name: str, level: int) -> List[str]:
    """Get default known spells for a class at a given level."""
    defaults = _DEFAULT_SPELLS.get(class_name.lower())
    if not defaults:
        return []

    spells = list(defaults.get('cantrips', []))
    class_spells = defaults.get('spells', [])

    # Bard spells known: 4 at level 1, +1 per level after
    # Simplified: return all defaults up to a reasonable count
    max_spells = 4 + max(0, level - 1)
    spells.extend(class_spells[:max_spells])
    return spells
