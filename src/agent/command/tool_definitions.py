"""
OpenAI function call tool definitions for the Command Agent.

Defines the tool schemas used by the LLM to select game mechanics actions.
"""
from typing import Dict, List


def get_tool_definitions() -> List[Dict]:
    """Define all available tools for the command agent."""
    return [
        {
            "type": "function",
            "function": {
                "name": "draft_character",
                "description": "Create a draft character that can be freely modified during creation. Use this when player starts character creation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Character name (use 'Unnamed' if not specified yet)"
                        },
                        "race": {
                            "type": "string",
                            "description": "D&D race (Human, Elf, Dwarf, etc.)"
                        },
                        "class_name": {
                            "type": "string",
                            "description": "D&D class (Wizard, Bard, Fighter, etc.)"
                        },
                        "level": {
                            "type": "integer",
                            "description": "Character level (1-20), default 1"
                        },
                        "ability_scores": {
                            "type": "object",
                            "description": "Ability scores as object with STR, DEX, CON, INT, WIS, CHA keys",
                            "properties": {
                                "STR": {"type": "integer"},
                                "DEX": {"type": "integer"},
                                "CON": {"type": "integer"},
                                "INT": {"type": "integer"},
                                "WIS": {"type": "integer"},
                                "CHA": {"type": "integer"}
                            }
                        },
                        "background": {
                            "type": "string",
                            "description": "Character background (Soldier, Noble, etc.)"
                        }
                    },
                    "required": ["name", "race", "class_name", "level"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "update_draft_character",
                "description": "Update a draft character during creation. Can modify any field freely before finalization.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Name of draft character to update"
                        },
                        "updates": {
                            "type": "object",
                            "description": "Fields to update (can include race, class_name, ability_scores, etc.)"
                        }
                    },
                    "required": ["name", "updates"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "finalize_character",
                "description": "Lock a draft character, making it immutable except via game rules. Use when player says 'finalize', 'I'm ready', or 'let's go'.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Name of draft character to finalize"
                        },
                        "hp": {
                            "type": "integer",
                            "description": "Max HP (will calculate from class + CON if not provided)"
                        },
                        "ac": {
                            "type": "integer",
                            "description": "Armor Class (will calculate from DEX + armor if not provided)"
                        }
                    },
                    "required": ["name"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "roll_dice",
                "description": "Roll dice using standard notation (1d20+5, 2d6+3, 4d6kh3). Use for all dice rolls.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "notation": {
                            "type": "string",
                            "description": "Dice notation (e.g., '1d20+5', '2d6+3', '4d6kh3')"
                        },
                        "advantage": {
                            "type": "boolean",
                            "description": "Roll with advantage (2d20 keep highest)"
                        },
                        "disadvantage": {
                            "type": "boolean",
                            "description": "Roll with disadvantage (2d20 keep lowest)"
                        },
                        "context": {
                            "type": "string",
                            "description": "What the roll is for (e.g., 'attack roll', 'perception check')"
                        }
                    },
                    "required": ["notation"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "create_monster",
                "description": "Add a monster to the encounter. Use when DM mentions a monster appearing.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Monster name (e.g., 'Goblin', 'Ancient Red Dragon')"
                        },
                        "hp": {
                            "type": "integer",
                            "description": "Monster's hit points"
                        },
                        "ac": {
                            "type": "integer",
                            "description": "Monster's armor class"
                        },
                        "cr": {
                            "type": "number",
                            "description": "Challenge rating"
                        }
                    },
                    "required": ["name", "hp", "ac", "cr"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "apply_damage",
                "description": "Apply damage to a character or monster. Use when damage is dealt in combat.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Character or monster name"
                        },
                        "damage": {
                            "type": "integer",
                            "description": "Damage amount (positive number)"
                        },
                        "damage_type": {
                            "type": "string",
                            "description": "Type of damage (slashing, fire, poison, etc.)"
                        }
                    },
                    "required": ["name", "damage"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "heal_character",
                "description": "Heal a character. Use when healing spells cast or potions consumed.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Character name"
                        },
                        "healing": {
                            "type": "integer",
                            "description": "HP to restore (positive number)"
                        },
                        "source": {
                            "type": "string",
                            "description": "Source of healing (spell, potion, rest)"
                        }
                    },
                    "required": ["name", "healing"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "start_combat",
                "description": "Begin a combat encounter. Use when combat starts.",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "set_initiative",
                "description": "Set initiative for a character or monster in combat.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Character or monster name"
                        },
                        "initiative": {
                            "type": "integer",
                            "description": "Initiative roll result"
                        }
                    },
                    "required": ["name", "initiative"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "add_condition",
                "description": "Apply a D&D condition to a creature (poisoned, prone, paralyzed, etc.).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Character or monster name"
                        },
                        "condition": {
                            "type": "string",
                            "description": "D&D condition (blinded, charmed, frightened, poisoned, prone, etc.)"
                        }
                    },
                    "required": ["name", "condition"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "remove_condition",
                "description": "Remove a condition from a creature.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Character or monster name"
                        },
                        "condition": {
                            "type": "string",
                            "description": "Condition to remove"
                        }
                    },
                    "required": ["name", "condition"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "cast_spell",
                "description": "Cast a spell by name. Looks up the spell, rolls damage dice, and optionally applies damage to a target. Use when a player says 'I cast [spell]'.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "spell_name": {
                            "type": "string",
                            "description": "Name of the spell (e.g., 'Fireball', 'Magic Missile')"
                        },
                        "character_name": {
                            "type": "string",
                            "description": "Name of the caster"
                        },
                        "target": {
                            "type": "string",
                            "description": "Target of the spell"
                        },
                        "slot_level": {
                            "type": "integer",
                            "description": "Spell slot level for upcasting"
                        }
                    },
                    "required": ["spell_name"]
                }
            }
        }
    ]
