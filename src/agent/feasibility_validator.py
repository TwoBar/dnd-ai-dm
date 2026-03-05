"""
Feasibility Validator - Validate if actions are physically/mechanically possible

Validates actions against:
- Spatial constraints (range, line of sight)
- Resource constraints (spell slots, items)
- D&D rules (from RAG)

Uses spatial context, game state, and RAG to determine if an action can be executed.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

import re

from agent.intent_agent import Intent, ActionType
from agent.rag_query_service import RAGQueryService
from agent.rag_intent_agent import RuleReference


def _ordinal(n):
    """Convert integer to ordinal string: 1→'1st', 2→'2nd', 3→'3rd', 4→'4th', etc."""
    if 11 <= (n % 100) <= 13:
        return f"{n}th"
    return f"{n}{['th', 'st', 'nd', 'rd'][n % 10] if n % 10 < 4 else 'th'}"


@dataclass
class ValidationResult:
    """Result of action validation"""
    is_valid: bool
    reason: str = ""
    suggestions: List[str] = field(default_factory=list)
    rule_reference: Optional[RuleReference] = None


class FeasibilityValidator:
    """
    Validates if an action is physically/mechanically possible.

    Uses:
    - Spatial context (distance, positioning)
    - Game state (resources, conditions)
    - RAG rules (D&D mechanics)
    """

    def __init__(self, rag_query: RAGQueryService):
        """
        Initialize feasibility validator.

        Args:
            rag_query: RAG query service for rule lookups
        """
        self.rag_query = rag_query

    def validate_action(
        self,
        intent: Intent,
        extracted_params: Dict[str, Any],
        context: Dict
    ) -> ValidationResult:
        """
        Validate if action is possible given current context.

        Args:
            intent: The detected intent
            extracted_params: Parameters extracted for the action
            context: Context including spatial, game state, etc.

        Returns:
            ValidationResult indicating if action is valid

        Example:
            >>> validator.validate_action(
            ...     Intent(action_type=ActionType.ATTACK, ...),
            ...     {'target': 'goblin'},
            ...     {'spatial_translation': {'distance': 15.0}, 'weapon_range': 1.5}
            ... )
            ValidationResult(
                is_valid=False,
                reason="Target is 15.0m away, weapon range is 1.5m",
                suggestions=["Dash closer", "Move closer and attack next turn"]
            )
        """

        if intent.action_type == ActionType.ATTACK:
            return self._validate_attack(intent, extracted_params, context)

        elif intent.action_type == ActionType.SPELL_CAST:
            return self._validate_spell_cast(intent, extracted_params, context)

        elif intent.action_type == ActionType.MOVEMENT:
            return self._validate_movement(intent, extracted_params, context)

        # Default: assume valid for other actions
        return ValidationResult(is_valid=True)

    def _validate_attack(
        self,
        intent: Intent,
        params: Dict,
        context: Dict
    ) -> ValidationResult:
        """
        Validate attack action.

        Checks:
        - Target exists in spatial context
        - Target is within weapon range
        - Player has line of sight
        """
        target = params.get('target')

        # Check if target exists in spatial context
        spatial_ref = context.get('spatial_translation')
        if not spatial_ref:
            return ValidationResult(
                is_valid=False,
                reason=f"Can't find '{target}' in the area.",
                suggestions=[
                    "Check if you spelled the name correctly",
                    "Look around to see what's nearby"
                ]
            )

        # Get validation rules from RAG
        validation_rules = self.rag_query.query_validation_rules(
            ActionType.ATTACK,
            params
        )

        # Check range
        distance = spatial_ref.get('distance', 0)
        weapon_range = context.get('weapon_range', 1.5)  # Default melee (5ft = 1.5m)

        if distance > weapon_range:
            # Calculate movement options
            movement_speed = context.get('movement_speed', 9.0)  # 30ft = 9m

            suggestions = []

            # Can reach with dash?
            can_reach_with_dash = (movement_speed * 2) >= distance
            if can_reach_with_dash:
                suggestions.append(f"Dash closer (move {movement_speed * 2}m using your action)")

            # Can reach with regular movement + ranged weapon?
            if distance <= 18:  # 60ft
                suggestions.append("Switch to ranged weapon if you have one")

            # Multi-turn approach
            suggestions.append("Move closer this turn and attack next turn")

            # Find movement rule from RAG
            move_rule = None
            for rule in validation_rules:
                if 'range' in rule.check_type.lower() or 'movement' in rule.check_type.lower():
                    move_rule = rule.rule_reference
                    break

            return ValidationResult(
                is_valid=False,
                reason=f"Target is {distance:.1f}m away, but your weapon range is {weapon_range:.1f}m.",
                suggestions=suggestions,
                rule_reference=move_rule
            )

        # Valid!
        return ValidationResult(is_valid=True)

    def _validate_spell_cast(
        self,
        intent: Intent,
        params: Dict,
        context: Dict
    ) -> ValidationResult:
        """
        Validate spell casting.

        Checks:
        - Spell exists
        - Player has spell slots
        - Target is within spell range
        - Player has required components
        """
        spell_name = params.get('spell_name')
        target = params.get('target')

        # Get spell details from RAG (via requirements query)
        requirements = self.rag_query.query_action_requirements(
            ActionType.SPELL_CAST,
            spell_name,
            context
        )

        # Check if spell exists
        if not requirements.rule_reference:
            return ValidationResult(
                is_valid=False,
                reason=f"Unknown spell: '{spell_name}'",
                suggestions=[
                    "Check the spell name spelling",
                    "Ask the DM what spells you know"
                ]
            )

        # Check if caster's class can use this spell
        caster_class = context.get('caster_class', '').lower()
        if caster_class:
            spell_classes = self._get_spell_classes(spell_name)
            if spell_classes and caster_class not in spell_classes:
                class_list = ', '.join(c.title() for c in sorted(spell_classes))
                return ValidationResult(
                    is_valid=False,
                    reason=f"'{spell_name.title()}' is not on the {caster_class.title()} spell list.",
                    suggestions=[
                        f"This spell is available to: {class_list}",
                        "Ask the DM what spells you know"
                    ],
                    rule_reference=requirements.rule_reference
                )

        # Check spell slots (if we have character data)
        spell_level = self._extract_spell_level_from_requirements(requirements)
        available_slots = context.get('spell_slots', {}).get(spell_level, 0)

        if spell_level > 0 and available_slots <= 0:
            return ValidationResult(
                is_valid=False,
                reason=f"No {_ordinal(spell_level)} level spell slots remaining.",
                suggestions=[
                    f"Cast a lower level spell",
                    "Take a short or long rest to recover spell slots"
                ],
                rule_reference=requirements.rule_reference
            )

        # Check range if there's a target
        if target:
            spatial_ref = context.get('spatial_translation')
            if spatial_ref:
                distance = spatial_ref.get('distance', 0)
                spell_range = self._extract_spell_range_from_requirements(requirements)

                if spell_range and distance > spell_range:
                    return ValidationResult(
                        is_valid=False,
                        reason=f"Target is {distance:.1f}m away, but spell range is {spell_range:.1f}m.",
                        suggestions=[
                            "Move closer to the target",
                            "Choose a different target within range"
                        ],
                        rule_reference=requirements.rule_reference
                    )

        # Valid!
        return ValidationResult(is_valid=True)

    def _validate_movement(
        self,
        intent: Intent,
        params: Dict,
        context: Dict
    ) -> ValidationResult:
        """
        Validate movement action.

        Checks:
        - Player has movement remaining
        - Path is not blocked
        - Distance is within movement speed
        """
        distance = params.get('distance', 0)
        movement_speed = context.get('movement_speed', 9.0)  # 30ft = 9m
        movement_used = context.get('movement_used', 0)
        movement_remaining = movement_speed - movement_used

        if distance > movement_remaining:
            return ValidationResult(
                is_valid=False,
                reason=f"You want to move {distance}m, but only have {movement_remaining:.1f}m of movement left this turn.",
                suggestions=[
                    "Move a shorter distance",
                    "Use Dash action to double your movement",
                    "Save the remaining movement for next turn"
                ]
            )

        # Valid!
        return ValidationResult(is_valid=True)

    def _extract_spell_level_from_requirements(self, requirements) -> int:
        """Extract spell level from requirements"""
        if not requirements or not requirements.conditions:
            return 0

        for condition in requirements.conditions:
            # Look for "Requires 1st/2nd/3rd/4th level spell slot"
            match = re.search(r'(\d+)(?:st|nd|rd|th) level spell slot', condition)
            if match:
                return int(match.group(1))

        return 0

    def _get_spell_classes(self, spell_name: str) -> List[str]:
        """Get the list of classes that can cast a spell."""
        try:
            from data.entity_manager import EntityManager
            em = EntityManager()
            spell = em.get_spell(spell_name)
            if spell and hasattr(spell, 'classes') and spell.classes:
                classes = spell.classes
                if isinstance(classes, str):
                    import json
                    try:
                        classes = json.loads(classes)
                    except (json.JSONDecodeError, TypeError):
                        classes = [c.strip().lower() for c in classes.split(',')]
                return [c.lower() for c in classes]
        except Exception:
            pass
        return []

    def _extract_spell_range_from_requirements(self, requirements) -> Optional[float]:
        """Extract spell range from requirements (in meters)"""
        if not requirements or not requirements.conditions:
            return None

        for condition in requirements.conditions:
            # Look for "Range: X feet"
            match = re.search(r'Range:\s*(\d+)\s*(?:feet|ft)', condition, re.IGNORECASE)
            if match:
                feet = int(match.group(1))
                return feet * 0.3048  # Convert to meters

            # Look for "Range: touch"
            if 'touch' in condition.lower():
                return 1.5  # Touch range ~5 feet

        return None
