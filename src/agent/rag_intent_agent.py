"""
RAG Intent Lookup Agent - D&D Rules-Based Intent Discovery

This agent searches D&D manuals when an intent is unclear, attempting to map
player actions to known game mechanics.

Purpose:
- Fallback when regex/LLM intent detection has low confidence
- Search D&D manuals for similar actions/mechanics
- Discover new intents based on rules
- Propose patterns for future learning

Flow:
1. Receive unclear intent (confidence < threshold)
2. Search RAG database for similar actions
3. Analyze rules to understand mechanics
4. Return structured intent + rule references
5. Optionally trigger pattern learning
"""

import openai
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from data.entity_manager import EntityManager
from agent.intent_agent import Intent, ActionType, SkillType


@dataclass
class RuleReference:
    """Reference to a rule in the manual"""
    source: str  # "PHB", "DMG", "Monster Manual", etc.
    page: Optional[int] = None
    section: Optional[str] = None
    rule_text: str = ""
    relevance_score: float = 0.0


@dataclass
class RAGIntentResult:
    """Result from RAG-based intent lookup"""
    intent: Optional[Intent] = None
    rule_references: List[RuleReference] = None
    confidence: float = 0.0
    suggests_new_pattern: bool = False
    pattern_proposal: Optional[Dict] = None
    mechanics_description: str = ""


class RAGIntentAgent:
    """
    Uses RAG (Retrieval-Augmented Generation) to discover intents from D&D rules.

    This agent bridges the gap between player language and D&D mechanics by
    searching official rules for similar actions.
    """

    # Confidence threshold for triggering RAG lookup
    LOW_CONFIDENCE_THRESHOLD = 0.7

    def __init__(
        self,
        entity_manager: EntityManager,
        openai_api_key: str,
        confidence_threshold: float = 0.7
    ):
        """
        Initialize RAG Intent Agent.

        Args:
            entity_manager: EntityManager with RAG capabilities
            openai_api_key: OpenAI API key
            confidence_threshold: Trigger RAG if confidence below this
        """
        self.entity_manager = entity_manager
        self.openai_api_key = openai_api_key
        self.confidence_threshold = confidence_threshold
        openai.api_key = openai_api_key

    def should_trigger_rag(self, intent: Intent) -> bool:
        """
        Determine if RAG lookup should be triggered.

        Args:
            intent: Intent from primary detection

        Returns:
            True if RAG should be used for clarification
        """
        # Trigger RAG if:
        # 1. Confidence below threshold
        # 2. Action type is UNCLEAR or NARRATIVE_ONLY
        # 3. Detection method was LLM (not regex - regex is reliable)

        if intent.confidence < self.confidence_threshold:
            return True

        if intent.action_type in [ActionType.UNCLEAR, ActionType.NARRATIVE_ONLY]:
            return True

        # If LLM detected but not confident, verify with rules
        if intent.detection_method == 'llm' and intent.confidence < 0.85:
            return True

        return False

    def lookup_intent(
        self,
        original_message: str,
        uncertain_intent: Intent,
        context: Optional[Dict] = None
    ) -> RAGIntentResult:
        """
        Search D&D rules to clarify uncertain intent.

        Args:
            original_message: Player's original message
            uncertain_intent: Intent with low confidence
            context: Optional game context

        Returns:
            RAGIntentResult with clarified intent and rule references
        """
        print(f"[RAG Intent] Searching rules for: '{original_message}'")

        # Step 1: Search for relevant rules
        rule_refs = self._search_rules_for_action(original_message, context)

        if not rule_refs:
            print("[RAG Intent] No relevant rules found")
            return RAGIntentResult(
                intent=uncertain_intent,
                rule_references=[],
                confidence=uncertain_intent.confidence,
                suggests_new_pattern=False
            )

        # Step 2: Analyze rules to extract intent
        analyzed_intent = self._analyze_rules_for_intent(
            original_message,
            rule_refs,
            uncertain_intent,
            context
        )

        print(f"[RAG Intent] Found intent: {analyzed_intent.action_type.value} "
              f"(confidence: {analyzed_intent.confidence:.2f})")

        # Step 3: Check if this suggests a new pattern
        suggests_pattern = self._should_propose_pattern(analyzed_intent, rule_refs)

        pattern_proposal = None
        if suggests_pattern:
            pattern_proposal = self._generate_pattern_proposal(
                original_message,
                analyzed_intent,
                rule_refs
            )
            print(f"[RAG Intent] Proposing new pattern: {pattern_proposal.get('name')}")

        return RAGIntentResult(
            intent=analyzed_intent,
            rule_references=rule_refs,
            confidence=analyzed_intent.confidence,
            suggests_new_pattern=suggests_pattern,
            pattern_proposal=pattern_proposal,
            mechanics_description=rule_refs[0].rule_text if rule_refs else ""
        )

    def _search_rules_for_action(
        self,
        message: str,
        context: Optional[Dict]
    ) -> List[RuleReference]:
        """
        Search RAG database for rules matching the action.

        Uses semantic search to find relevant rules.
        """
        # Construct search query
        search_query = self._build_search_query(message, context)

        # Search for rules (using EntityManager's RAG capabilities)
        # Note: EntityManager can search rules, spells, etc.
        rule_results = []

        # Search rules/conditions
        try:
            # Try to find rules about actions
            rules = self.entity_manager.search_entities(
                query=search_query,
                entity_type='rule',
                limit=3
            )

            for rule in rules:
                rule_refs.append(RuleReference(
                    source=rule.get('source', 'Unknown'),
                    page=rule.get('page'),
                    section=rule.get('name'),
                    rule_text=rule.get('description', ''),
                    relevance_score=rule.get('_score', 0.5)
                ))

        except Exception as e:
            print(f"[RAG Intent] Rule search failed: {e}")

        # Also search abilities/actions in spells/features
        try:
            spells = self.entity_manager.search_entities(
                query=search_query,
                entity_type='spell',
                limit=2
            )

            for spell in spells:
                rule_results.append(RuleReference(
                    source='Spell',
                    section=spell.get('name'),
                    rule_text=spell.get('description', ''),
                    relevance_score=spell.get('_score', 0.5)
                ))

        except Exception as e:
            print(f"[RAG Intent] Spell search failed: {e}")

        # Sort by relevance
        rule_results.sort(key=lambda r: r.relevance_score, reverse=True)

        return rule_results[:3]  # Top 3 most relevant

    def _analyze_rules_for_intent(
        self,
        message: str,
        rule_refs: List[RuleReference],
        base_intent: Intent,
        context: Optional[Dict]
    ) -> Intent:
        """
        Analyze retrieved rules to extract proper intent.

        Uses LLM to understand rules and map to intent.
        """
        # Build context from rules
        rules_text = "\n\n".join([
            f"Rule: {ref.section}\n{ref.rule_text}"
            for ref in rule_refs
        ])

        system_prompt = """You are a D&D 5e rules expert analyzing player actions.

Given a player's message and relevant rules from the manual, determine:
1. What ACTION TYPE the player wants to perform
2. What MECHANICS are involved (dice rolls, saves, etc.)
3. What PARAMETERS are needed (target, skill, spell, etc.)

Available action types:
- attack: Physical/ranged attack
- spell_cast: Casting a spell
- skill_check: Skill check (Persuasion, Stealth, etc.)
- ability_check: Raw ability check
- saving_throw: Saving throw
- dodge/dash/disengage/hide/help: Standard actions
- movement: Movement
- conversation: Pure roleplay (no mechanics)

Respond with JSON:
{
  "action_type": "skill_check",
  "confidence": 0.9,
  "skill": "athletics",
  "mechanics": "Player rolls d20 + Athletics modifier vs DC",
  "requires_dice": true,
  "reasoning": "Grappling requires an Athletics check contested by Athletics or Acrobatics"
}"""

        context_str = ""
        if context:
            context_str = f"\n\nGame Context:\n{context}"

        user_prompt = f"""Player's message: "{message}"

Relevant D&D Rules:
{rules_text}
{context_str}

Analyze the action and determine the intent."""

        try:
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=300
            )

            response_text = response.choices[0].message.content.strip()

            # Parse JSON
            if '```json' in response_text:
                response_text = response_text.split('```json')[1].split('```')[0].strip()
            elif '```' in response_text:
                response_text = response_text.split('```')[1].split('```')[0].strip()

            import json
            result = json.loads(response_text)

            # Convert to Intent
            action_type = ActionType(result.get('action_type', 'unclear'))
            skill = None
            if result.get('skill'):
                try:
                    skill = SkillType(result['skill'].lower())
                except ValueError:
                    pass

            return Intent(
                action_type=action_type,
                confidence=result.get('confidence', 0.8),
                target=base_intent.target,  # Keep from original
                skill=skill,
                spell_name=result.get('spell_name'),
                original_message=message,
                detection_method='rag'
            )

        except Exception as e:
            print(f"[RAG Intent] Analysis failed: {e}")
            # Return original intent
            return base_intent

    def _should_propose_pattern(
        self,
        intent: Intent,
        rule_refs: List[RuleReference]
    ) -> bool:
        """
        Determine if a new pattern should be proposed.

        Criteria:
        - Intent has high confidence (>0.8)
        - Found in official rules
        - Not already in pattern library
        """
        if intent.confidence < 0.8:
            return False

        if not rule_refs:
            return False

        # Check if official source (not homebrew)
        official_sources = ['PHB', 'DMG', 'Basic Rules', 'SRD']
        has_official_source = any(
            ref.source in official_sources for ref in rule_refs
        )

        return has_official_source

    def _generate_pattern_proposal(
        self,
        message: str,
        intent: Intent,
        rule_refs: List[RuleReference]
    ) -> Dict:
        """
        Generate a pattern proposal for the Pattern Generator Agent.

        Returns a structured proposal that can be validated and added.
        """
        # Extract key words/phrases from message
        import re
        message_lower = message.lower()

        # Try to identify the key action verb
        action_verbs = re.findall(r'\b(grapple|shove|trip|disarm|tumble|vault)\b', message_lower)

        return {
            'name': intent.action_type.value + '_' + ('_'.join(action_verbs) if action_verbs else 'custom'),
            'action_type': intent.action_type.value,
            'trigger_phrases': action_verbs,
            'example_message': message,
            'detected_skill': intent.skill.value if intent.skill else None,
            'rule_references': [
                {
                    'source': ref.source,
                    'section': ref.section,
                    'text': ref.rule_text[:200]  # Truncate
                }
                for ref in rule_refs
            ],
            'confidence': intent.confidence,
            'mechanics_summary': rule_refs[0].rule_text[:500] if rule_refs else "",
            'proposed_regex': self._suggest_regex_pattern(message, action_verbs),
            'requires_validation': True,
            'status': 'pending_review'
        }

    def _suggest_regex_pattern(self, message: str, action_verbs: List[str]) -> str:
        """Suggest a regex pattern based on the message"""
        if not action_verbs:
            return ""

        # Create a simple pattern
        verbs_pattern = '|'.join(action_verbs)
        return f"r'\\b({verbs_pattern})\\s+'"

    def _build_search_query(self, message: str, context: Optional[Dict]) -> str:
        """Build an optimized search query for RAG"""
        query_parts = [message]

        if context:
            if context.get('in_combat'):
                query_parts.append("combat action")

        return " ".join(query_parts)
