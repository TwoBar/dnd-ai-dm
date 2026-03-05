"""
Re-export facade - Reference models moved to data/reference_models.py

All imports from data.entities still work for backward compatibility.
New code should import from data.reference_models directly.
"""
from data.reference_models import (
    Entity,
    Spell,
    Monster,
    Rule,
    Item,
    EntityCache,
)

__all__ = ['Entity', 'Spell', 'Monster', 'Rule', 'Item', 'EntityCache']
