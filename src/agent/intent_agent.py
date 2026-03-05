"""
Intent Detection Agent - Fast, deterministic action classification

This agent analyzes player messages to detect what action they want to perform,
WITHOUT executing any mechanics or generating narrative.

Purpose:
- Detect player intent (attack, spell, skill check, etc.)
- Extract action parameters (target, modifiers, etc.)
- Determine if mechanics are needed
- Fast and deterministic where possible

Strategy:
- Layer 1: Regex pattern matching (instant, deterministic)
- Layer 2: LLM fallback for complex/ambiguous cases
- Layer 3: Context-aware disambiguation
"""

import logging
import re
import json
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum
import openai

logger = logging.getLogger(__name__)


class ActionType(Enum):
    """Types of actions players can take"""
    # Combat actions
    ATTACK = "attack"
    SPELL_CAST = "spell_cast"
    DODGE = "dodge"
    DASH = "dash"
    DISENGAGE = "disengage"
    HIDE = "hide"
    HELP = "help"
    READY_ACTION = "ready_action"

    # Skill checks
    SKILL_CHECK = "skill_check"
    ABILITY_CHECK = "ability_check"
    SAVING_THROW = "saving_throw"

    # Character management
    CHARACTER_CREATION = "character_creation"
    LEVEL_UP = "level_up"
    REST = "rest"

    # Combat management
    INITIATIVE = "initiative"
    END_TURN = "end_turn"

    # Dice rolling
    DICE_ROLL = "dice_roll"

    # Social/exploration
    CONVERSATION = "conversation"
    INVESTIGATION = "investigation"
    MOVEMENT = "movement"

    # Meta
    UNCLEAR = "unclear"
    NARRATIVE_ONLY = "narrative_only"


class SkillType(Enum):
    """D&D 5e skills"""
    ACROBATICS = "acrobatics"
    ANIMAL_HANDLING = "animal_handling"
    ARCANA = "arcana"
    ATHLETICS = "athletics"
    DECEPTION = "deception"
    HISTORY = "history"
    INSIGHT = "insight"
    INTIMIDATION = "intimidation"
    INVESTIGATION = "investigation"
    MEDICINE = "medicine"
    NATURE = "nature"
    PERCEPTION = "perception"
    PERFORMANCE = "performance"
    PERSUASION = "persuasion"
    RELIGION = "religion"
    SLEIGHT_OF_HAND = "sleight_of_hand"
    STEALTH = "stealth"
    SURVIVAL = "survival"


@dataclass
class Intent:
    """Represents a detected player intent"""
    action_type: ActionType
    confidence: float  # 0.0 to 1.0

    # Actor — who performs the action (None = resolve by context cascade)
    actor: Optional[str] = None

    # Action parameters
    target: Optional[str] = None
    skill: Optional[SkillType] = None
    spell_name: Optional[str] = None
    weapon: Optional[str] = None
    dice_notation: Optional[str] = None

    # Modifiers
    advantage: bool = False
    disadvantage: bool = False

    # Conditional/reactive
    is_conditional: bool = False
    condition: Optional[str] = None

    # Multi-action
    is_multi_action: bool = False
    sub_actions: List['Intent'] = None

    # Original message
    original_message: str = ""

    # Detection method
    detection_method: str = "unknown"  # 'regex', 'llm', 'context'

    # NEW: Reasoning support (for iterative clarification system)
    extracted_parameters: Dict[str, Any] = None  # Parameters extracted during reasoning
    reasoning_trace: List[str] = None  # Trace of reasoning steps for transparency

    def requires_mechanics(self) -> bool:
        """Does this intent require dice rolls or game state changes?"""
        mechanics_required = [
            ActionType.ATTACK,
            ActionType.SPELL_CAST,
            ActionType.SKILL_CHECK,
            ActionType.ABILITY_CHECK,
            ActionType.SAVING_THROW,
            ActionType.DICE_ROLL,
            ActionType.INITIATIVE,
            ActionType.CHARACTER_CREATION,
            ActionType.MOVEMENT,  # Movement updates spatial state!
        ]
        return self.action_type in mechanics_required

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'action_type': self.action_type.value,
            'confidence': self.confidence,
            'actor': self.actor,
            'target': self.target,
            'skill': self.skill.value if self.skill else None,
            'spell_name': self.spell_name,
            'weapon': self.weapon,
            'dice_notation': self.dice_notation,
            'advantage': self.advantage,
            'disadvantage': self.disadvantage,
            'is_conditional': self.is_conditional,
            'condition': self.condition,
            'is_multi_action': self.is_multi_action,
            'sub_actions': [a.to_dict() for a in self.sub_actions] if self.sub_actions else None,
            'original_message': self.original_message,
            'extracted_parameters': self.extracted_parameters or {},
            'reasoning_trace': self.reasoning_trace or [],
            'detection_method': self.detection_method,
            'requires_mechanics': self.requires_mechanics()
        }


class IntentAgent:
    """
    Intent detection using agentic LLM semantic understanding.

    This agent ONLY detects intent - it doesn't execute mechanics or generate narrative.
    Uses LLM for semantic understanding with pure dice notation as fast fallback.
    """

    def __init__(self, openai_api_key: Optional[str] = None):
        """
        Initialize Intent Agent.

        Args:
            openai_api_key: OpenAI API key for LLM fallback (optional)
        """
        self.openai_api_key = openai_api_key
        if openai_api_key:
            openai.api_key = openai_api_key

    def detect(
        self,
        message: str,
        context: Optional[Dict] = None,
        message_history: Optional[List[Dict]] = None
    ) -> Intent:
        """
        Detect player intent using **fully agentic semantic understanding**.

        **Philosophy**:
        Language is ambiguous and context-dependent. Keywords fail because:
        - "I attack" vs "I'm under attack" - same words, opposite meanings
        - "where is my character?" vs "I want to be a wizard" - both mention character
        - "the goblin" - needs conversation context to understand reference
        - "yes" - meaning depends entirely on what was asked

        **Approach**:
        1. PRIMARY: LLM with conversation history for semantic understanding
        2. FALLBACK: Pure dice notation only (truly unambiguous)
        3. FAILURE: Ask player to reiterate (no regex guessing)

        Args:
            message: Player's message
            context: Game state context (in_combat, nearby_entities, etc.)
            message_history: Recent conversation history for semantic context

        Returns:
            Intent object with detected action and parameters
        """
        message_lower = message.lower().strip()

        # ================================================================
        # FALLBACK 1: Pure Dice Notation (truly unambiguous)
        # ================================================================
        # "1d20+5" or "2d6" - these have no ambiguity
        # Check this first as it's deterministic and fast
        dice_pattern = r'^(\d+d\d+(?:[+-]\d+)?)$'
        if re.match(dice_pattern, message_lower.strip()):
            return Intent(
                action_type=ActionType.DICE_ROLL,
                confidence=1.0,
                dice_notation=message_lower.strip(),
                original_message=message,
                detection_method='dice_notation'
            )

        # ================================================================
        # PRIMARY: AGENTIC LLM DETECTION
        # ================================================================
        # Use LLM to understand semantic meaning with full context
        if self.openai_api_key:
            llm_intent = self._detect_with_llm(message, context, message_history)

            if llm_intent:
                # Trust LLM for all semantic understanding
                return llm_intent

        # ================================================================
        # FAILURE: LLM Unavailable or Failed
        # ================================================================
        # NO REGEX FALLBACK - keyword matching defeats the purpose
        # Instead, ask player to reiterate
        logger.warning("LLM semantic understanding unavailable, asking player to reiterate")

        return Intent(
            action_type=ActionType.UNCLEAR,
            confidence=0.0,  # We have no idea
            original_message=message,
            detection_method='llm_unavailable'
        )

    def _detect_with_llm(
        self,
        message: str,
        context: Optional[Dict] = None,
        message_history: Optional[List[Dict]] = None
    ) -> Optional[Intent]:
        """
        Agentic LLM-based intent detection with semantic understanding.

        Uses conversation history and context to understand meaning, not just keywords.
        Can rewrite ambiguous prompts to unpack meaning.
        """

        system_prompt = """You are an intelligent intent classifier for a D&D 5e game.

Your job is to understand the **semantic meaning** of the player's message, not just match keywords.

**Key Principles**:
1. **Context Matters**: Use conversation history to understand references ("the goblin", "him", "it")
2. **Semantic Understanding**: "where is my character?" is NOT character creation - it's asking about location
3. **Intent vs Content**: "I want to talk about wizards" (conversation) vs "I want to be a wizard" (character creation)
4. **Ambiguity Resolution**: If unclear, prefer narrative_only with low confidence
5. **Referential Understanding**: "yes" might mean confirming an attack, continuing creation, etc.
6. **Scene Awareness**: Use the entities in scene to resolve targets. If the player says "I attack" and there's only one monster, set target to that monster. If ambiguous, leave target null.

**Available Action Types**:
- attack: Player wants to attack a target physically
- spell_cast: Player wants to cast a spell
- skill_check: Player wants to use a skill (Persuasion, Stealth, Investigation, Perception, etc.)
- ability_check: Raw ability check (STR, DEX, CON, INT, WIS, CHA)
- saving_throw: Making a saving throw
- dice_roll: Explicit dice notation request (1d20, 2d6+3, etc.)
- initiative: Rolling initiative for combat
- character_creation: **Creating a NEW character** (not asking about existing character!)
- conversation: Dialogue with NPCs or asking questions
- movement: Moving to a location or direction
- investigation: Looking around, searching, examining
- narrative_only: Pure roleplay, no mechanics needed

**Semantic Examples**:
- "where is my character?" → conversation (asking about existing character, NOT creating)
- "I want to be a wizard" → character_creation (wants to create)
- "I am a wizard" (in isolation) → character_creation (introducing new character)
- "I am a wizard" (after character exists) → conversation (stating fact about existing character)
- "can I try to sneak?" → skill_check (stealth)
- "I attack" → attack (target from context/scene)
- "I attack the goblin" → attack (explicit target)
- "tell me about wizards" → conversation (inquiry, not creation)
- "walk to the bar" → movement
- "go to the fireplace" → movement
- "head to the entrance" → movement
- "move Grok to the bar" → movement (actor="Grok")
- "Grok attacks the goblin" → attack (actor="Grok", target="goblin")

**Actor Extraction Rules**:
The "actor" field identifies WHO performs the action.
- Set to the specific name when explicitly stated as subject:
  "Grok attacks" → actor="Grok", "the bartender walks" → actor="bartender"
- Set to null for first-person or implied subject:
  "I attack" → null, "lets move" → null, "attack the goblin" → null,
  "move to the bar" → null, "cast fireball" → null

**Respond with JSON**:
{
  "action_type": "attack",
  "confidence": 0.9,
  "reasoning": "Player clearly states attack intent with explicit target",
  "actor": null,
  "target": "goblin",
  "skill": null,
  "spell_name": null,
  "weapon": null,
  "dice_notation": null,
  "advantage": false,
  "disadvantage": false
}

**Include "reasoning" field** to explain your semantic understanding."""

        # Build conversation context
        conversation_context = ""
        if message_history:
            # Include last 3 turns for context
            recent_history = message_history[-6:]  # Last 3 exchanges
            conversation_context = "\n\nRecent Conversation:\n"
            for msg in recent_history:
                role = msg.get('role', msg.get('speaker', 'unknown'))
                content = msg.get('content', msg.get('message', ''))
                speaker = 'Player' if role in ['user', 'player'] else 'DM'
                conversation_context += f"{speaker}: {content}\n"

        # Build game context
        game_context = ""
        if context:
            game_context = "\n\nGame Context:\n"
            if context.get('in_combat'):
                game_context += "- In combat\n"
            if context.get('player_characters'):
                game_context += f"- Player's characters: {', '.join(context['player_characters'])}\n"
            if context.get('scene_entities'):
                game_context += "- Entities in scene:\n"
                for e in context['scene_entities']:
                    game_context += f"  - {e['name']} ({e['type']}, {e['distance']}m away)\n"
            elif context.get('nearby_entities'):
                entities = context['nearby_entities']
                game_context += f"- Nearby entities: {', '.join(entities)}\n"
            if context.get('current_location'):
                game_context += f"- Location: {context['current_location']}\n"
            if context.get('character_exists'):
                game_context += "- Player already has a character\n"

        user_prompt = f"Current Message: {message}{conversation_context}{game_context}"

        try:
            response = openai.chat.completions.create(
                model="gpt-4o-mini",  # Fast, cheap model for intent
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,  # Low temperature for consistency
                max_tokens=300
            )

            response_text = response.choices[0].message.content.strip()

            # Parse JSON response
            # Handle markdown code blocks
            if '```json' in response_text:
                response_text = response_text.split('```json')[1].split('```')[0].strip()
            elif '```' in response_text:
                response_text = response_text.split('```')[1].split('```')[0].strip()

            intent_data = json.loads(response_text)

            # Log reasoning for transparency
            reasoning = intent_data.get('reasoning', '')
            if reasoning:
                logger.debug("LLM reasoning: %s", reasoning)

            # Convert to Intent object
            action_type = ActionType(intent_data.get('action_type', 'narrative_only'))

            # Handle skill type conversion (case-insensitive)
            skill = None
            if intent_data.get('skill'):
                skill_str = intent_data['skill'].lower().replace(' ', '_')
                try:
                    skill = SkillType(skill_str)
                except ValueError:
                    # Skill name not in enum, leave as None
                    logger.debug("Unknown skill: %s, ignoring", intent_data['skill'])

            return Intent(
                action_type=action_type,
                confidence=intent_data.get('confidence', 0.7),
                actor=intent_data.get('actor'),
                target=intent_data.get('target'),
                skill=skill,
                spell_name=intent_data.get('spell_name'),
                weapon=intent_data.get('weapon'),
                dice_notation=intent_data.get('dice_notation'),
                advantage=intent_data.get('advantage', False),
                disadvantage=intent_data.get('disadvantage', False),
                original_message=message,
                detection_method='llm'
            )

        except Exception as e:
            logger.error("LLM intent detection failed: %s", e, exc_info=True)
            return None

