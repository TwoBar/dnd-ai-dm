"""
Skill Query Service - Interface to query available skills and their requirements

This service enables the reasoning agent to understand:
- What skills can handle a given action
- What parameters those skills require
- What the skill implementations are

Uses ACTION_TOOL_REGISTRY as the single authoritative mapping from ActionType to tool.
Both the reasoning agent and orchestrator import from here.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)

from agent.intent_agent import ActionType


# ========================================================================
# SINGLE AUTHORITATIVE REGISTRY: ActionType → Tool Name
# ========================================================================
# Both ReasoningAgent and Orchestrator use this. No more competing maps.

ACTION_TOOL_REGISTRY: Dict[ActionType, str] = {
    ActionType.ATTACK:             'roll_attack',
    ActionType.SPELL_CAST:         'cast_spell',
    ActionType.SKILL_CHECK:        'roll_dice',
    ActionType.ABILITY_CHECK:      'roll_dice',
    ActionType.SAVING_THROW:       'roll_saving_throw',
    ActionType.DICE_ROLL:          'roll_dice',
    ActionType.CHARACTER_CREATION: 'draft_character',
    ActionType.MOVEMENT:           'move_character',
    ActionType.INITIATIVE:         'set_initiative',
    ActionType.REST:               'heal_character',
    # Not mapped (narrative-only, handled by DM agent):
    # CONVERSATION, INVESTIGATION, NARRATIVE_ONLY, DODGE, DASH,
    # DISENGAGE, HIDE, HELP, READY_ACTION, END_TURN, LEVEL_UP, UNCLEAR
}

# Params the orchestrator auto-resolves (reasoning should NOT ask for these)
AUTO_RESOLVED_PARAMS: Dict[str, List[str]] = {
    'move_character': ['character_name'],
    'roll_attack':    ['ability_modifier', 'proficiency_bonus'],
    'cast_spell':     ['character_name'],
}


@dataclass
class ApplicableSkill:
    """Represents a skill that can handle an action"""
    skill_name: str
    confidence: float
    required_params: List[str]
    optional_params: List[str]
    parameter_schemas: Dict
    description: str


class SkillQueryService:
    """
    Query skill system to understand what can be executed and what parameters are needed.

    Uses ACTION_TOOL_REGISTRY for deterministic ActionType → tool lookup.
    No more keyword matching — the IntentAgent (LLM) already classified the action.
    """

    def __init__(self):
        """Initialize skill query service with existing tool definitions"""
        try:
            from tools.dice_tools import DICE_TOOLS, DICE_FUNCTION_MAP
            from tools.entity_tools import ENTITY_TOOLS, ENTITY_FUNCTION_MAP
            from tools.movement_tools import MOVEMENT_TOOLS, MOVEMENT_FUNCTION_MAP
            from tools.spell_tools import SPELL_TOOLS, SPELL_FUNCTION_MAP
            from agent.command.tool_definitions import get_tool_definitions

            self.tool_definitions = DICE_TOOLS + ENTITY_TOOLS + MOVEMENT_TOOLS + SPELL_TOOLS
            self.function_map = {**DICE_FUNCTION_MAP, **ENTITY_FUNCTION_MAP, **MOVEMENT_FUNCTION_MAP, **SPELL_FUNCTION_MAP}

            command_tools = get_tool_definitions()
            self.tool_definitions.extend(command_tools)

            # Build name → definition index for fast lookup
            self._tool_by_name: Dict[str, Dict] = {
                t['function']['name']: t for t in self.tool_definitions
            }

            logger.info("Loaded %d tools, registry covers %d action types",
                        len(self.tool_definitions), len(ACTION_TOOL_REGISTRY))

        except ImportError as e:
            logger.warning("Could not import all tool definitions: %s", e)
            self.tool_definitions = []
            self.function_map = {}
            self._tool_by_name = {}

    def query_applicable_skills(
        self,
        action_type: ActionType,
        user_message: str,
        context: Optional[Dict] = None
    ) -> List[ApplicableSkill]:
        """
        Query: What skills can handle this action?

        Uses ACTION_TOOL_REGISTRY for deterministic lookup — no keyword matching.
        The IntentAgent already classified the action type; we just map it to a tool.
        """
        tool_name = ACTION_TOOL_REGISTRY.get(action_type)
        if not tool_name:
            return []

        tool_def = self._tool_by_name.get(tool_name)
        if not tool_def:
            logger.warning("Registry maps %s -> '%s' but tool not found in definitions",
                          action_type.value, tool_name)
            return []

        func = tool_def['function']
        params = func['parameters']
        required = list(params.get('required', []))
        all_props = list(params.get('properties', {}).keys())
        optional = [k for k in all_props if k not in required]

        # Exclude auto-resolved params (orchestrator fills these)
        auto_resolved = AUTO_RESOLVED_PARAMS.get(tool_name, [])
        required = [p for p in required if p not in auto_resolved]
        optional = [p for p in optional if p not in auto_resolved]

        return [ApplicableSkill(
            skill_name=tool_name,
            confidence=1.0,  # Deterministic registry match
            required_params=required,
            optional_params=optional,
            parameter_schemas=params.get('properties', {}),
            description=func['description']
        )]

    def get_skill_parameters(self, skill_name: str) -> Dict:
        """
        Query: What parameters does this skill need?
        """
        tool_def = self._tool_by_name.get(skill_name)
        if tool_def:
            return tool_def['function']['parameters']
        return {}

    def get_all_skills(self) -> List[Dict]:
        """Get all available skills."""
        return self.tool_definitions

    def has_skill(self, skill_name: str) -> bool:
        """Check if a skill exists."""
        return skill_name in self._tool_by_name
