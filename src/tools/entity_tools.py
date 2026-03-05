"""Entity retrieval tools - Two-stage retrieval for DM agent"""
from typing import Optional, List, Dict, Any

from config import REFERENCE_DB_PATH, VECTOR_DB_DIR
from data.entity_manager import EntityManager


# Initialize entity manager
entity_manager = None

def get_entity_manager() -> EntityManager:
    """Lazy-initialize entity manager"""
    global entity_manager
    if entity_manager is None:
        entity_manager = EntityManager(REFERENCE_DB_PATH, VECTOR_DB_DIR)
    return entity_manager


# ============================================================================
# TOOL FUNCTIONS (Called by DM Agent)
# ============================================================================

def get_spell(name: str) -> dict:
    """
    Get a specific spell by name (exact match)

    Args:
        name: Spell name (e.g., "Fireball", "Magic Missile")

    Returns:
        Spell details including level, school, damage, etc.

    Example:
        get_spell("Fireball")
        → {
            "name": "Fireball",
            "level": 3,
            "school": "Evocation",
            "damage": "8d6",
            "save": "Dexterity",
            "description": "...",
            ...
        }
    """
    em = get_entity_manager()
    spell = em.get_spell(name=name)

    if not spell:
        return {"error": f"Spell '{name}' not found"}

    return {
        "name": spell.name,
        "level": spell.level,
        "school": spell.school,
        "classes": spell.classes,
        "casting_time": spell.casting_time,
        "range": spell.range,
        "components": spell.components,
        "duration": spell.duration,
        "description": spell.description,
        "higher_levels": spell.higher_levels,
        "damage": spell.damage,
        "save": spell.save,
        "tags": spell.tags
    }


def search_spells(query: str, level: Optional[int] = None, school: Optional[str] = None) -> dict:
    """
    Search for spells using natural language query + optional filters

    Uses two-stage retrieval:
    - Stage 1: Filter by level/school metadata
    - Stage 2: Semantic search within filtered results

    Args:
        query: Natural language description (e.g., "fire damage area spell")
        level: Optional spell level filter (0-9)
        school: Optional school filter (Evocation, Abjuration, etc.)

    Returns:
        List of matching spells (top 3)

    Example:
        search_spells("fire damage spell", level=3)
        → Returns Fireball, Flame Arrows, etc.
    """
    em = get_entity_manager()
    spells = em.search_spells(query=query, level=level, school=school)

    return {
        "count": len(spells),
        "spells": [
            {
                "name": s.name,
                "level": s.level,
                "school": s.school,
                "damage": s.damage,
                "description": s.description[:200] + "..." if len(s.description) > 200 else s.description
            }
            for s in spells[:3]  # Top 3 results
        ]
    }


def get_monster(name: str) -> dict:
    """
    Get a specific monster by name

    Args:
        name: Monster name (e.g., "Goblin", "Adult Red Dragon")

    Returns:
        Monster stat block

    Example:
        get_monster("Goblin")
        → {
            "name": "Goblin",
            "cr": 0.25,
            "ac": 15,
            "hp": "7 (2d6)",
            ...
        }
    """
    em = get_entity_manager()
    monster = em.get_monster(name=name)

    if not monster:
        return {"error": f"Monster '{name}' not found"}

    return {
        "name": monster.name,
        "cr": monster.cr,
        "size": monster.size,
        "type": monster.type_alignment,
        "ac": monster.ac,
        "hp": monster.hp,
        "speed": monster.speed,
        "abilities": monster.abilities,
        "traits": monster.traits,
        "actions": monster.actions,
        "tags": monster.tags,
        "description": monster.content[:500] + "..." if len(monster.content) > 500 else monster.content
    }


def search_monsters(query: str, cr: Optional[float] = None, size: Optional[str] = None) -> dict:
    """
    Search for monsters using natural language + optional filters

    Args:
        query: Natural language description (e.g., "small undead creature")
        cr: Optional challenge rating filter
        size: Optional size filter (Tiny, Small, Medium, Large, Huge, Gargantuan)

    Returns:
        List of matching monsters (top 3)
    """
    em = get_entity_manager()
    monsters = em.search_monsters(query=query, cr=cr, size=size)

    return {
        "count": len(monsters),
        "monsters": [
            {
                "name": m.name,
                "cr": m.cr,
                "size": m.size,
                "ac": m.ac,
                "hp": m.hp
            }
            for m in monsters[:3]
        ]
    }


def get_rule(query: str, domain: Optional[str] = None) -> dict:
    """
    Get a specific game rule

    Args:
        query: Rule description (e.g., "grappling", "attack of opportunity")
        domain: Optional domain filter (combat, magic, exploration, conditions)

    Returns:
        Rule details

    Example:
        get_rule("grappling")
        → Returns grappling mechanics from Combat rules
    """
    em = get_entity_manager()
    rules = em.search_rules(query=query, domain=domain)

    if not rules:
        return {"error": f"No rule found for '{query}'"}

    rule = rules[0]  # Top result

    return {
        "name": rule.name,
        "domain": rule.domain,
        "category": rule.category,
        "content": rule.content,
        "tags": rule.tags
    }


def get_condition(name: str) -> dict:
    """
    Get a specific condition (blinded, charmed, etc.)

    Args:
        name: Condition name (e.g., "Blinded", "Paralyzed")

    Returns:
        Condition effects
    """
    em = get_entity_manager()
    condition = em.get_rule(name=name, domain="conditions")

    if not condition:
        return {"error": f"Condition '{name}' not found"}

    return {
        "name": condition.name,
        "effects": condition.content,
        "tags": condition.tags
    }


def get_cache_stats() -> dict:
    """
    Get entity cache statistics

    Returns:
        Cache performance metrics
    """
    em = get_entity_manager()
    return em.cache_stats()


# ============================================================================
# TOOL DEFINITIONS (For OpenAI Function Calling)
# ============================================================================

ENTITY_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_spell",
            "description": "Get a specific D&D spell by exact name. Use this when a player mentions a spell by name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Exact spell name (e.g., 'Fireball', 'Magic Missile')"
                    }
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_spells",
            "description": "Search for spells using natural language. Use when you need to find spells by description or properties.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language query (e.g., 'fire damage area spell', 'healing spell')"
                    },
                    "level": {
                        "type": "integer",
                        "description": "Optional: Filter by spell level (0-9)",
                        "minimum": 0,
                        "maximum": 9
                    },
                    "school": {
                        "type": "string",
                        "description": "Optional: Filter by school (Evocation, Abjuration, Conjuration, etc.)"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_monster",
            "description": "Get a specific monster's stat block by exact name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Monster name (e.g., 'Goblin', 'Adult Red Dragon')"
                    }
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_monsters",
            "description": "Search for monsters using natural language and optional filters.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language query (e.g., 'small undead creature', 'flying dragon')"
                    },
                    "cr": {
                        "type": "number",
                        "description": "Optional: Filter by challenge rating"
                    },
                    "size": {
                        "type": "string",
                        "description": "Optional: Filter by size (Tiny, Small, Medium, Large, Huge, Gargantuan)"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_rule",
            "description": "Look up a specific D&D 5E game rule. Use this when you need to check how a mechanic works.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Rule description (e.g., 'grappling', 'attack of opportunity', 'concentration')"
                    },
                    "domain": {
                        "type": "string",
                        "description": "Optional: Rule domain (combat, magic, exploration, conditions)"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_condition",
            "description": "Get details about a specific condition (blinded, charmed, paralyzed, etc.).",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Condition name (e.g., 'Blinded', 'Paralyzed', 'Prone')"
                    }
                },
                "required": ["name"]
            }
        }
    }
]


# Function mapping for execution
ENTITY_FUNCTION_MAP = {
    "get_spell": get_spell,
    "search_spells": search_spells,
    "get_monster": get_monster,
    "search_monsters": search_monsters,
    "get_rule": get_rule,
    "get_condition": get_condition,
    "get_cache_stats": get_cache_stats
}
