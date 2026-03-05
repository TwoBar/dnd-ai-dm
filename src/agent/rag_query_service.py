"""
RAG Query Service - Interface to query RAG for domain knowledge

This service enables the reasoning agent to consult the RAG system to understand:
- What actions are possible in a given situation
- What parameters are required for an action
- What validation rules apply to an action

Integrates with existing RAGIntentAgent and EntityManager.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from agent.rag_intent_agent import RAGIntentAgent, RuleReference
from data.entity_manager import EntityManager
from agent.intent_agent import ActionType


def _ordinal(n):
    """Convert integer to ordinal string: 1→'1st', 2→'2nd', 3→'3rd', 4→'4th', etc."""
    if 11 <= (n % 100) <= 13:
        return f"{n}th"
    return f"{n}{['th', 'st', 'nd', 'rd'][n % 10] if n % 10 < 4 else 'th'}"


@dataclass
class ActionPossibility:
    """Represents a possible action discovered from RAG rules"""
    action_name: str
    rule_reference: RuleReference
    confidence: float
    mechanics_summary: str


@dataclass
class ActionRequirements:
    """Requirements for executing an action, based on D&D rules"""
    required_params: List[str] = field(default_factory=list)
    conditions: List[str] = field(default_factory=list)
    rule_reference: Optional[RuleReference] = None


@dataclass
class ValidationRule:
    """A validation rule from D&D manuals"""
    check_type: str  # 'range', 'resource', 'condition'
    description: str
    rule_reference: RuleReference


class RAGQueryService:
    """
    Query RAG to understand what actions are possible and their requirements.

    This service sits between the reasoning agent and the RAG system,
    providing a clean interface for domain knowledge queries.
    """

    def __init__(self, rag_agent: RAGIntentAgent, entity_manager: EntityManager):
        self.rag_agent = rag_agent
        self.entity_manager = entity_manager

    def query_possible_actions(
        self,
        user_message: str,
        context: Optional[Dict] = None
    ) -> List[ActionPossibility]:
        """
        Query: What actions are possible in this situation?

        Searches D&D rules for actions matching the user's message.

        Args:
            user_message: The player's natural language message
            context: Optional context (in_combat, location, etc.)

        Returns:
            List of possible actions with rule references and confidence scores

        Example:
            >>> service.query_possible_actions("I try to hide")
            [ActionPossibility(action_name='Hide', rule_reference=..., confidence=0.85)]
        """
        context = context or {}

        # Determine search domain based on context
        domain = 'combat' if context.get('in_combat') else None

        # Search rules for matching actions
        rules = self.entity_manager.search_rules(
            query=user_message,
            domain=domain
        )[:5]  # Limit to top 5 results

        possibilities = []
        for rule in rules:
            # Extract relevance score (assuming entity_manager adds this)
            relevance = getattr(rule, 'relevance_score', 0.5)

            # Extract metadata safely
            metadata = getattr(rule, 'metadata', {})
            source = metadata.get('source', 'SRD')

            possibility = ActionPossibility(
                action_name=rule.name,
                rule_reference=RuleReference(
                    source=source,
                    section=rule.name,
                    rule_text=rule.content,
                    relevance_score=relevance
                ),
                confidence=relevance,
                mechanics_summary=rule.content[:200]  # Python slicing handles length automatically
            )
            possibilities.append(possibility)

        return sorted(possibilities, key=lambda x: x.confidence, reverse=True)

    def query_action_requirements(
        self,
        action_type: ActionType,
        action_name: str,
        context: Optional[Dict] = None
    ) -> ActionRequirements:
        """
        Query: What parameters/conditions are required for this action?

        Looks up D&D rules to determine what the action needs.

        Args:
            action_type: The type of action (ATTACK, SPELL_CAST, etc.)
            action_name: Specific action name (e.g., "Fireball")
            context: Optional context

        Returns:
            ActionRequirements with required params, conditions, and rule reference

        Example:
            >>> service.query_action_requirements(ActionType.SPELL_CAST, "Fireball")
            ActionRequirements(
                required_params=['spell_name', 'target'],
                conditions=['Requires 3rd level spell slot', 'Range: 150 feet'],
                rule_reference=...
            )
        """
        context = context or {}

        # SPELL_CAST: Look up spell details
        if action_type == ActionType.SPELL_CAST:
            try:
                spell = self.entity_manager.get_spell(action_name)
                if spell:
                    # Determine if spell requires target
                    requires_target = bool(spell.damage) or 'target' in spell.content.lower()

                    required_params = ['spell_name']
                    if requires_target:
                        required_params.append('target')

                    # Extract metadata safely
                    spell_metadata = getattr(spell, 'metadata', {})

                    conditions = [
                        f"Requires {_ordinal(spell.level)} level spell slot" if spell.level > 0 else "Cantrip (no spell slot required)",
                        f"Range: {spell_metadata.get('range', 'touch')}",
                        f"Components: {spell_metadata.get('components', 'V,S')}"
                    ]

                    return ActionRequirements(
                        required_params=required_params,
                        conditions=conditions,
                        rule_reference=RuleReference(
                            source='PHB',
                            section=spell.name,
                            rule_text=spell.content,
                            relevance_score=1.0
                        )
                    )
            except:
                pass  # Spell not found, fall through to default

        # ATTACK: Look up combat rules
        elif action_type == ActionType.ATTACK:
            rules = self.entity_manager.search_rules(
                query="attack action range",
                domain="combat"
            )[:1]  # Limit to top result

            if rules:
                return ActionRequirements(
                    required_params=['target', 'weapon'],
                    conditions=[
                        "Target must be within weapon range",
                        "Requires action in combat"
                    ],
                    rule_reference=RuleReference(
                        source='PHB',
                        section='Making an Attack',
                        rule_text=rules[0].content,
                        relevance_score=0.9
                    )
                )

        # CHARACTER_CREATION: Character creation requirements
        elif action_type == ActionType.CHARACTER_CREATION:
            return ActionRequirements(
                required_params=['name', 'class_name', 'level'],
                conditions=[
                    "Name must be unique",
                    "Class must be a valid D&D class",
                    "Level must be between 1 and 20"
                ],
                rule_reference=None  # Built-in rule
            )

        # Fallback: minimal requirements
        return ActionRequirements(required_params=[])

    def query_validation_rules(
        self,
        action_type: ActionType,
        extracted_params: Optional[Dict] = None
    ) -> List[ValidationRule]:
        """
        Query: What rules must be checked to validate this action?

        Searches D&D manuals for validation rules (range, resources, etc.).

        Args:
            action_type: The type of action to validate
            extracted_params: Parameters already extracted

        Returns:
            List of validation rules with their D&D rule references

        Example:
            >>> service.query_validation_rules(ActionType.ATTACK, {'target': 'goblin'})
            [ValidationRule(
                check_type='range',
                description='Target must be within weapon range',
                rule_reference=...
            )]
        """
        extracted_params = extracted_params or {}
        validation_rules = []

        if action_type == ActionType.ATTACK:
            # Get range rules
            range_rules = self.entity_manager.search_rules(
                query="weapon range attack distance",
                domain="combat"
            )[:2]  # Limit to top 2 results

            for rule in range_rules:
                validation_rules.append(ValidationRule(
                    check_type='range',
                    description=rule.content[:200],
                    rule_reference=RuleReference(
                        source='PHB',
                        section=rule.name,
                        rule_text=rule.content,
                        relevance_score=getattr(rule, 'relevance_score', 0.7)
                    )
                ))

        elif action_type == ActionType.SPELL_CAST:
            # Get spell slot rules
            spell_rules = self.entity_manager.search_rules(
                query="spell slot level casting",
                domain="magic"
            )[:2]  # Limit to top 2 results

            for rule in spell_rules:
                validation_rules.append(ValidationRule(
                    check_type='resource',
                    description=rule.content[:200],
                    rule_reference=RuleReference(
                        source='PHB',
                        section=rule.name,
                        rule_text=rule.content,
                        relevance_score=getattr(rule, 'relevance_score', 0.7)
                    )
                ))

        return validation_rules
