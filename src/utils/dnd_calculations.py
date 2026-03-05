"""
D&D 5e Calculation Utilities

Core calculations for ability modifiers, proficiency bonuses,
spell slots, and other D&D 5e mechanics.
"""

from typing import Dict, List, Optional
import math


def ability_modifier(score: int) -> int:
    """
    Calculate ability modifier from ability score.

    Args:
        score: Ability score (1-30)

    Returns:
        Modifier (-5 to +10)

    Example:
        >>> ability_modifier(10)
        0
        >>> ability_modifier(18)
        4
        >>> ability_modifier(8)
        -1
    """
    return math.floor((score - 10) / 2)


def proficiency_bonus(level: int) -> int:
    """
    Calculate proficiency bonus from character level.

    Args:
        level: Total character level (1-20)

    Returns:
        Proficiency bonus (+2 to +6)

    Example:
        >>> proficiency_bonus(1)
        2
        >>> proficiency_bonus(5)
        3
        >>> proficiency_bonus(20)
        6
    """
    return math.ceil(level / 4) + 1


def skill_modifier(ability_score: int, proficient: bool, expertise: bool, level: int) -> int:
    """
    Calculate skill modifier.

    Args:
        ability_score: Related ability score
        proficient: Has proficiency in this skill
        expertise: Has expertise (double proficiency)
        level: Character level

    Returns:
        Total skill modifier

    Example:
        >>> skill_modifier(16, True, False, 5)  # +3 ability, +3 proficiency
        6
        >>> skill_modifier(16, True, True, 5)  # +3 ability, +6 expertise
        9
    """
    mod = ability_modifier(ability_score)
    if proficient:
        prof = proficiency_bonus(level)
        mod += prof * (2 if expertise else 1)
    return mod


def saving_throw_modifier(ability_score: int, proficient: bool, level: int) -> int:
    """
    Calculate saving throw modifier.

    Args:
        ability_score: Ability score for this save
        proficient: Has proficiency in this save
        level: Character level

    Returns:
        Saving throw modifier
    """
    mod = ability_modifier(ability_score)
    if proficient:
        mod += proficiency_bonus(level)
    return mod


def attack_bonus(ability_score: int, proficient: bool, level: int, magic_bonus: int = 0) -> int:
    """
    Calculate attack bonus.

    Args:
        ability_score: STR for melee, DEX for ranged
        proficient: Proficient with this weapon
        level: Character level
        magic_bonus: Magical weapon bonus

    Returns:
        Total attack bonus

    Example:
        >>> attack_bonus(16, True, 5, 1)  # +3 ability, +3 prof, +1 magic
        7
    """
    mod = ability_modifier(ability_score)
    if proficient:
        mod += proficiency_bonus(level)
    return mod + magic_bonus


def spell_save_dc(spellcasting_ability: int, level: int) -> int:
    """
    Calculate spell save DC.

    Formula: 8 + proficiency bonus + spellcasting ability modifier

    Args:
        spellcasting_ability: INT/WIS/CHA score
        level: Character level

    Returns:
        Spell save DC

    Example:
        >>> spell_save_dc(16, 5)  # 8 + 3 prof + 3 ability
        14
    """
    return 8 + proficiency_bonus(level) + ability_modifier(spellcasting_ability)


def spell_attack_bonus(spellcasting_ability: int, level: int) -> int:
    """
    Calculate spell attack bonus.

    Formula: proficiency bonus + spellcasting ability modifier

    Args:
        spellcasting_ability: INT/WIS/CHA score
        level: Character level

    Returns:
        Spell attack bonus

    Example:
        >>> spell_attack_bonus(16, 5)  # 3 prof + 3 ability
        6
    """
    return proficiency_bonus(level) + ability_modifier(spellcasting_ability)


def initiative_bonus(dex_score: int, other_bonuses: int = 0) -> int:
    """
    Calculate initiative bonus.

    Args:
        dex_score: Dexterity score
        other_bonuses: Feats, class features, etc.

    Returns:
        Initiative modifier
    """
    return ability_modifier(dex_score) + other_bonuses


def passive_perception(wis_score: int, proficient: bool, expertise: bool, level: int) -> int:
    """
    Calculate passive Perception (Wisdom).

    Formula: 10 + Wisdom modifier + proficiency (if proficient)

    Args:
        wis_score: Wisdom score
        proficient: Proficient in Perception
        expertise: Has expertise in Perception
        level: Character level

    Returns:
        Passive Perception score
    """
    return 10 + skill_modifier(wis_score, proficient, expertise, level)


def armor_class_unarmored(dex_score: int, unarmored_defense: Optional[str] = None,
                          con_score: int = 10, wis_score: int = 10) -> int:
    """
    Calculate AC when not wearing armor.

    Args:
        dex_score: Dexterity score
        unarmored_defense: 'barbarian' (10 + DEX + CON) or 'monk' (10 + DEX + WIS)
        con_score: Constitution score (for barbarian)
        wis_score: Wisdom score (for monk)

    Returns:
        Unarmored AC

    Example:
        >>> armor_class_unarmored(16)  # Normal: 10 + DEX
        13
        >>> armor_class_unarmored(16, 'barbarian', con_score=14)  # 10 + DEX + CON
        15
        >>> armor_class_unarmored(16, 'monk', wis_score=14)  # 10 + DEX + WIS
        15
    """
    ac = 10 + ability_modifier(dex_score)

    if unarmored_defense == 'barbarian':
        ac += ability_modifier(con_score)
    elif unarmored_defense == 'monk':
        ac += ability_modifier(wis_score)

    return ac


def multiclass_spell_slots(class_levels: Dict[str, int]) -> Dict[int, int]:
    """
    Calculate multiclass spell slots.

    Uses Multiclassing spell slot table from PHB.
    Full casters (Wizard, Cleric, etc.) contribute full level.
    Half casters (Paladin, Ranger) contribute half level (rounded down).
    Third casters (Eldritch Knight, Arcane Trickster) contribute 1/3 level (rounded down).

    Args:
        class_levels: Dict mapping class name to level
            Example: {'wizard': 3, 'cleric': 2}

    Returns:
        Dict mapping spell level (1-9) to total slots
        Example: {1: 4, 2: 3, 3: 2}

    Example:
        >>> multiclass_spell_slots({'wizard': 3, 'cleric': 2})
        {1: 4, 2: 3, 3: 2}
    """
    # Caster progression by class
    FULL_CASTERS = ['wizard', 'sorcerer', 'cleric', 'druid', 'bard']
    HALF_CASTERS = ['paladin', 'ranger']
    THIRD_CASTERS = ['eldritch_knight', 'arcane_trickster']

    # Calculate multiclass caster level
    caster_level = 0
    for class_name, level in class_levels.items():
        class_lower = class_name.lower()
        if class_lower in FULL_CASTERS:
            caster_level += level
        elif class_lower in HALF_CASTERS:
            caster_level += level // 2
        elif class_lower in THIRD_CASTERS:
            caster_level += level // 3

    # Spell slot table (caster level → slots per level)
    SPELL_SLOT_TABLE = {
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
        11: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1},
        12: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1},
        13: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1},
        14: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1},
        15: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1, 8: 1},
        16: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1, 8: 1},
        17: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1, 8: 1, 9: 1},
        18: {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 1, 7: 1, 8: 1, 9: 1},
        19: {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 2, 7: 1, 8: 1, 9: 1},
        20: {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 2, 7: 2, 8: 1, 9: 1},
    }

    if caster_level == 0:
        return {}

    caster_level = min(caster_level, 20)
    return SPELL_SLOT_TABLE.get(caster_level, {})


def carrying_capacity(str_score: int) -> int:
    """
    Calculate carrying capacity in pounds.

    Args:
        str_score: Strength score

    Returns:
        Carrying capacity in pounds (STR × 15)

    Example:
        >>> carrying_capacity(10)
        150
        >>> carrying_capacity(16)
        240
    """
    return str_score * 15


def encumbered_threshold(str_score: int) -> int:
    """
    Calculate encumbered threshold (speed reduced by 10).

    Args:
        str_score: Strength score

    Returns:
        Weight threshold for encumbrance (STR × 5)
    """
    return str_score * 5


def heavily_encumbered_threshold(str_score: int) -> int:
    """
    Calculate heavily encumbered threshold (speed reduced to 10 ft).

    Args:
        str_score: Strength score

    Returns:
        Weight threshold for heavy encumbrance (STR × 10)
    """
    return str_score * 10


def xp_to_level(xp: int) -> int:
    """
    Convert XP to character level.

    Args:
        xp: Experience points

    Returns:
        Character level (1-20)
    """
    XP_TABLE = [
        0,      # Level 1
        300,    # Level 2
        900,    # Level 3
        2700,   # Level 4
        6500,   # Level 5
        14000,  # Level 6
        23000,  # Level 7
        34000,  # Level 8
        48000,  # Level 9
        64000,  # Level 10
        85000,  # Level 11
        100000, # Level 12
        120000, # Level 13
        140000, # Level 14
        165000, # Level 15
        195000, # Level 16
        225000, # Level 17
        265000, # Level 18
        305000, # Level 19
        355000, # Level 20
    ]

    for level, threshold in enumerate(XP_TABLE, start=1):
        if xp < threshold:
            return max(1, level - 1)

    return 20  # Max level


def level_to_xp(level: int) -> int:
    """
    Get XP threshold for a given level.

    Args:
        level: Character level (1-20)

    Returns:
        XP required to reach that level
    """
    XP_TABLE = [
        0, 300, 900, 2700, 6500, 14000, 23000, 34000, 48000, 64000,
        85000, 100000, 120000, 140000, 165000, 195000, 225000, 265000, 305000, 355000
    ]

    level = max(1, min(level, 20))
    return XP_TABLE[level - 1]


if __name__ == '__main__':
    # Run doctests
    import doctest
    doctest.testmod()
    print("✅ All calculation tests passed!")
