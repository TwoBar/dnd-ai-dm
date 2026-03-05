"""Dice rolling tools for the DM agent"""
from game.dice import DiceRoller, DiceRoll


# Initialize dice roller
dice_roller = DiceRoller()


def roll_dice(notation: str, advantage: bool = False, disadvantage: bool = False) -> dict:
    """
    Roll dice using D&D notation

    Args:
        notation: Dice notation (e.g., "2d6+3", "1d20", "4d6kh3")
        advantage: Roll with advantage (d20 only)
        disadvantage: Roll with disadvantage (d20 only)

    Returns:
        Dictionary with roll results

    Examples:
        roll_dice("2d6+3") → {total: 11, rolls: [4, 5], modifier: 3, ...}
        roll_dice("1d20", advantage=True) → {total: 18, rolls: [18], ...}
    """
    try:
        result = dice_roller.roll(notation, advantage=advantage, disadvantage=disadvantage)

        return {
            "notation": result.notation,
            "total": result.total,
            "rolls": result.rolls,
            "modifier": result.modifier,
            "is_critical": result.is_critical,
            "is_fumble": result.is_fumble,
            "advantage": result.advantage,
            "disadvantage": result.disadvantage,
            "description": str(result)
        }
    except Exception as e:
        return {
            "error": str(e),
            "notation": notation
        }


def roll_attack(
    ability_modifier: int,
    proficiency_bonus: int = 0,
    advantage: bool = False,
    disadvantage: bool = False
) -> dict:
    """
    Roll an attack roll (d20 + modifiers)

    Args:
        ability_modifier: Strength or Dexterity modifier
        proficiency_bonus: Proficiency bonus if proficient
        advantage: Roll with advantage
        disadvantage: Roll with disadvantage

    Returns:
        Attack roll result
    """
    result = dice_roller.roll_attack(
        ability_modifier=ability_modifier,
        proficiency_bonus=proficiency_bonus,
        advantage=advantage,
        disadvantage=disadvantage
    )

    return {
        "total": result.total,
        "rolls": result.rolls,
        "modifier": result.modifier,
        "is_critical": result.is_critical,
        "is_fumble": result.is_fumble,
        "description": str(result)
    }


def roll_damage(
    dice_notation: str,
    ability_modifier: int = 0,
    critical: bool = False
) -> dict:
    """
    Roll damage dice

    Args:
        dice_notation: Base weapon damage (e.g., "1d8", "2d6")
        ability_modifier: Strength/Dexterity modifier to add
        critical: True if critical hit (doubles dice, not modifier)

    Returns:
        Damage roll result
    """
    result = dice_roller.roll_damage(
        dice_notation=dice_notation,
        ability_modifier=ability_modifier,
        critical=critical
    )

    return {
        "total": result.total,
        "rolls": result.rolls,
        "modifier": result.modifier,
        "critical": critical,
        "description": str(result)
    }


def roll_saving_throw(
    ability_modifier: int,
    proficiency_bonus: int = 0,
    advantage: bool = False,
    disadvantage: bool = False
) -> dict:
    """
    Roll a saving throw

    Args:
        ability_modifier: Relevant ability modifier
        proficiency_bonus: Proficiency bonus if proficient in save
        advantage: Roll with advantage
        disadvantage: Roll with disadvantage

    Returns:
        Saving throw result
    """
    result = dice_roller.roll_ability_check(
        ability_modifier=ability_modifier,
        proficiency_bonus=proficiency_bonus,
        advantage=advantage,
        disadvantage=disadvantage
    )

    return {
        "total": result.total,
        "rolls": result.rolls,
        "modifier": result.modifier,
        "description": str(result)
    }


def roll_ability_scores(method: str = "4d6kh3") -> dict:
    """
    Roll ability scores for character creation

    Args:
        method: Rolling method
            "4d6kh3" - Roll 4d6, keep highest 3 (default)
            "3d6" - Roll 3d6 straight
            "2d6+6" - Roll 2d6+6

    Returns:
        Six ability scores in descending order
    """
    scores = dice_roller.roll_stats(method=method)

    return {
        "scores": scores,
        "method": method,
        "description": f"Ability scores ({method}): {scores}"
    }


# Tool definitions for OpenAI function calling
DICE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "roll_dice",
            "description": "Roll dice using D&D notation (e.g., 2d6+3, 1d20, 4d6kh3). Use this for any dice rolling.",
            "parameters": {
                "type": "object",
                "properties": {
                    "notation": {
                        "type": "string",
                        "description": "Dice notation (e.g., '2d6+3', '1d20', '4d6kh3')"
                    },
                    "advantage": {
                        "type": "boolean",
                        "description": "Roll with advantage (d20 only)",
                        "default": False
                    },
                    "disadvantage": {
                        "type": "boolean",
                        "description": "Roll with disadvantage (d20 only)",
                        "default": False
                    }
                },
                "required": ["notation"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "roll_attack",
            "description": "Roll an attack roll (d20 + ability modifier + proficiency)",
            "parameters": {
                "type": "object",
                "properties": {
                    "ability_modifier": {
                        "type": "integer",
                        "description": "Strength or Dexterity modifier"
                    },
                    "proficiency_bonus": {
                        "type": "integer",
                        "description": "Proficiency bonus if proficient with weapon",
                        "default": 0
                    },
                    "advantage": {
                        "type": "boolean",
                        "description": "Roll with advantage",
                        "default": False
                    },
                    "disadvantage": {
                        "type": "boolean",
                        "description": "Roll with disadvantage",
                        "default": False
                    }
                },
                "required": ["ability_modifier"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "roll_damage",
            "description": "Roll weapon damage dice",
            "parameters": {
                "type": "object",
                "properties": {
                    "dice_notation": {
                        "type": "string",
                        "description": "Base weapon damage (e.g., '1d8', '2d6')"
                    },
                    "ability_modifier": {
                        "type": "integer",
                        "description": "Ability modifier to add to damage",
                        "default": 0
                    },
                    "critical": {
                        "type": "boolean",
                        "description": "True if critical hit (doubles dice)",
                        "default": False
                    }
                },
                "required": ["dice_notation"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "roll_saving_throw",
            "description": "Roll a saving throw (d20 + ability modifier + proficiency if proficient)",
            "parameters": {
                "type": "object",
                "properties": {
                    "ability_modifier": {
                        "type": "integer",
                        "description": "Relevant ability modifier (STR, DEX, CON, INT, WIS, or CHA)"
                    },
                    "proficiency_bonus": {
                        "type": "integer",
                        "description": "Proficiency bonus if proficient in this save",
                        "default": 0
                    },
                    "advantage": {
                        "type": "boolean",
                        "description": "Roll with advantage",
                        "default": False
                    },
                    "disadvantage": {
                        "type": "boolean",
                        "description": "Roll with disadvantage",
                        "default": False
                    }
                },
                "required": ["ability_modifier"]
            }
        }
    }
]


# Function mapping for execution
DICE_FUNCTION_MAP = {
    "roll_dice": roll_dice,
    "roll_attack": roll_attack,
    "roll_damage": roll_damage,
    "roll_saving_throw": roll_saving_throw,
    "roll_ability_scores": roll_ability_scores
}
