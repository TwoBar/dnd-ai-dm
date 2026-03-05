"""
Parameter Extractor - Conversation-aware parameter extraction

Extracts parameters from FULL CONVERSATION HISTORY, not just the current message.
This allows players to provide information across multiple turns.

Example:
    Turn 1: "I want to be a wizard"
    Turn 2: "My name is Gandalf"
    Turn 3: "Level 5"

    Extracts: {'class_name': 'Wizard', 'name': 'Gandalf', 'level': 5}
"""

import re
import json
import logging
from typing import Dict, List, Optional, Any

from agent.intent_agent import ActionType, SkillType

# Set up logger
logger = logging.getLogger(__name__)


class ParameterExtractor:
    """
    Extracts parameters from full conversation history.

    Uses multiple strategies:
    1. Pattern matching (fast, deterministic)
    2. LLM extraction (for complex cases)
    3. Context inference (spatial, game state)
    4. Conversation history analysis
    """

    def __init__(self, openai_api_key: Optional[str] = None):
        """
        Initialize parameter extractor.

        Args:
            openai_api_key: Optional OpenAI API key for LLM extraction
        """
        self.openai_api_key = openai_api_key
        self.has_llm = bool(openai_api_key)

        if self.has_llm:
            import openai
            openai.api_key = self.openai_api_key

    def _extract_multiple_choice_answer(
        self,
        message: str,
        question_context: Dict
    ) -> Optional[str]:
        """
        Match user response to multiple choice options.

        Generic matcher that works for ANY multiple-choice question.

        Handles:
        - Number selection: "1", "option 1", "number 2"
        - Keyword matching: "standard", "point buy"
        - Partial matches: "roll" matches "Roll 4d6 drop lowest"

        Args:
            message: User's response message
            question_context: Dict with 'parameter' and 'options' list

        Returns:
            Matched option value, or None if no match
        """
        message_lower = message.lower().strip()
        options = question_context.get('options', [])

        if not options:
            return None

        # Strategy 1: Number selection ("1", "option 2", "number 3")
        number_match = re.search(r'(?:option\s+)?(?:number\s+)?(\d+)', message_lower)
        if number_match:
            number = int(number_match.group(1))
            for option in options:
                if option.get('number') == number:
                    logger.info(f"[ParameterExtractor] Matched by number: {number} → {option['value']}")
                    return option['value']

        # Strategy 2: Exact keyword matching (highest confidence)
        for option in options:
            keywords = option.get('keywords', [])
            # Check if ALL keywords appear in message (exact match)
            if len(keywords) > 0 and all(kw.lower() in message_lower for kw in keywords):
                logger.info(f"[ParameterExtractor] Exact match: {keywords} → {option['value']}")
                return option['value']

        # Strategy 3: Partial keyword matching
        best_match = None
        best_score = 0

        for option in options:
            keywords = option.get('keywords', [])
            # Count how many keywords appear
            match_count = sum(1 for kw in keywords if kw.lower() in message_lower)

            if match_count > best_score:
                best_score = match_count
                best_match = option

        if best_match and best_score > 0:
            logger.info(f"[ParameterExtractor] Partial match ({best_score} keywords): {best_match['label']} → {best_match['value']}")
            return best_match['value']

        # Strategy 4: Fuzzy label matching (last resort)
        # Check if user's message is contained in any option label
        for option in options:
            label_lower = option['label'].lower()
            if message_lower in label_lower or label_lower in message_lower:
                logger.info(f"[ParameterExtractor] Fuzzy label match: '{message}' ≈ '{option['label']}' → {option['value']}")
                return option['value']

        logger.warning(f"[ParameterExtractor] No match found for '{message}' against {len(options)} options")
        return None

    def extract_from_conversation(
        self,
        conversation_history: List[Dict],
        current_message: str,
        action_type: ActionType,
        context: Optional[Dict] = None,
        previously_extracted: Optional[Dict[str, Any]] = None,
        pending_question: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Extract parameters from ENTIRE CONVERSATION.

        Automatically merges with previously extracted parameters, ensuring
        parameter persistence across conversation turns for ALL interaction types.

        Args:
            conversation_history: List of previous messages [{'speaker': 'player'/'dm', 'message': '...'}]
            current_message: The current player message
            action_type: The type of action being performed
            context: Optional context (spatial, game state)
            previously_extracted: Previously extracted parameters from conversation state
            pending_question: Optional context for pending multiple-choice question

        Returns:
            Dictionary of extracted parameters (merged with previous)

        Example:
            >>> extract_from_conversation(
            ...     [{'speaker': 'player', 'message': 'I want to be a wizard'}],
            ...     'My name is Gandalf',
            ...     ActionType.CHARACTER_CREATION,
            ...     previously_extracted={'level': 5}
            ... )
            {'class_name': 'Wizard', 'name': 'Gandalf', 'level': 5}
        """
        context = context or {}
        previously_extracted = previously_extracted or {}

        # Start with previously extracted parameters (persistence layer)
        extracted = dict(previously_extracted)

        # PRIORITY: If awaiting multiple-choice response, try to match first
        if pending_question and pending_question.get('question_type') == 'multiple_choice':
            answer = self._extract_multiple_choice_answer(current_message, pending_question)
            if answer:
                param = pending_question.get('parameter')
                logger.info(f"[ParameterExtractor] Answered multiple-choice for '{param}': {answer}")
                extracted[param] = answer
                # Return immediately - question answered, don't run other strategies
                return extracted
            else:
                logger.warning(f"[ParameterExtractor] No match for pending question about '{pending_question.get('parameter')}'")
                # Fall through to normal extraction strategies

        # Strategy 1: Extract from current message (pattern matching)
        extracted.update(
            self._extract_with_patterns(current_message, action_type)
        )

        # Strategy 2: Extract from conversation history
        # Look at last 5 player messages
        # Support both formats: 'speaker'/'role' and 'message'/'content'
        for msg in reversed(conversation_history[-5:]):
            # Check if this is a player message (handle both formats)
            is_player = (msg.get('speaker') == 'player' or msg.get('role') == 'user')
            if is_player:
                # Get message content (handle both formats)
                msg_content = msg.get('message') or msg.get('content', '')
                extracted.update(
                    self._extract_with_patterns(msg_content, action_type)
                )

        # Strategy 3: LLM extraction with full conversation context
        if self.has_llm and len(conversation_history) > 0:
            llm_extracted = self._extract_with_llm_and_history(
                current_message,
                conversation_history,
                action_type,
                context
            )
            # LLM results override pattern matching for higher accuracy
            extracted.update(llm_extracted)

        # Strategy 4: Context inference (spatial, game state)
        extracted.update(self._extract_from_context(action_type, context))

        return extracted

    def _extract_with_patterns(
        self,
        message: str,
        action_type: ActionType
    ) -> Dict[str, Any]:
        """
        Pattern-based extraction using regex.

        Fast and deterministic, good for common formats.
        """
        message_lower = message.lower()
        extracted = {}

        # CHARACTER CREATION patterns
        if action_type == ActionType.CHARACTER_CREATION:
            # Name patterns
            name_patterns = [
                r'named\s+(\w+)',  # "elf barbarian named eldor"
                r'(?:name is|call me|i am|i\'m|want to be)\s+(\w+)',
                r'^(\w+),?\s+(?:a|the|an)\s+',  # "Gandalf, a wizard"
                r'my\s+name\s+is\s+(\w+)',
                r'im\s+(\w+)',  # "im eldor"
            ]
            for pattern in name_patterns:
                match = re.search(pattern, message_lower)
                if match:
                    extracted['name'] = match.group(1).capitalize()
                    break

            # Fallback: if message is just a single word (likely answering "What's your name?")
            if 'name' not in extracted:
                standalone_word = re.match(r'^(\w+)$', message.strip())
                if standalone_word:
                    extracted['name'] = standalone_word.group(1).capitalize()

            # Class patterns
            classes = ['wizard', 'fighter', 'rogue', 'cleric', 'barbarian', 'ranger', 'paladin', 'druid', 'monk', 'warlock', 'sorcerer', 'bard']
            for cls in classes:
                if cls in message_lower:
                    extracted['class_name'] = cls.capitalize()
                    break

            # Race patterns
            races = ['human', 'elf', 'dwarf', 'halfling', 'dragonborn', 'gnome', 'half-elf', 'half-orc', 'tiefling']
            for race in races:
                if race in message_lower:
                    extracted['race'] = race.capitalize()
                    break

            # Level patterns
            level_match = re.search(r'(?:level|lvl)\s*(\d+)', message_lower)
            if level_match:
                extracted['level'] = int(level_match.group(1))
            # Also check for standalone numbers in context of character creation
            elif re.search(r'^\d+$', message.strip()):
                extracted['level'] = int(message.strip())

            # Background patterns (keep these as they're not multiple-choice questions)
            backgrounds = ['acolyte', 'charlatan', 'criminal', 'entertainer', 'folk hero',
                          'guild artisan', 'hermit', 'noble', 'outlander', 'sage',
                          'sailor', 'soldier', 'urchin']
            for bg in backgrounds:
                if bg in message_lower:
                    extracted['background'] = bg.title()
                    break

        # ATTACK patterns
        elif action_type == ActionType.ATTACK:
            # Actor extraction — "Grok attacks the goblin"
            actor_match = re.search(r'(\w+)\s+attacks?\s+', message_lower)
            if actor_match and actor_match.group(1).lower() not in ('i', 'my', 'we', 'let', 'lets'):
                extracted['actor'] = actor_match.group(1).capitalize()

            # Target patterns
            attack_verbs = ['attack', 'strike', 'hit', 'slash', 'stab', 'shoot', 'fire at']
            for verb in attack_verbs:
                pattern = f'{verb}(?:\\s+the)?\\s+(\\w+)'
                match = re.search(pattern, message_lower)
                if match:
                    extracted['target'] = match.group(1)
                    break

            # Also check for just entity names (e.g., "the goblin")
            if 'target' not in extracted:
                target_pattern = r'(?:the|a|an)\s+(\w+)'
                match = re.search(target_pattern, message_lower)
                if match:
                    extracted['target'] = match.group(1)

            # Weapon patterns
            weapon_pattern = r'(?:with|using)\s+(?:my\s+)?(\w+)'
            match = re.search(weapon_pattern, message_lower)
            if match:
                extracted['weapon'] = match.group(1)

        # SPELL CAST patterns
        elif action_type == ActionType.SPELL_CAST:
            # Spell name patterns
            spell_patterns = [
                r'(?:cast|use)\s+([a-z\s]+?)(?:\s+on|\s+at|\s+targeting)',
                r'(?:cast|use)\s+([a-z\s]+)',
            ]
            for pattern in spell_patterns:
                match = re.search(pattern, message_lower)
                if match:
                    spell_name = match.group(1).strip()
                    extracted['spell_name'] = spell_name
                    break

            # Target patterns
            target_patterns = [
                r'(?:at|on|targeting)\s+(?:the\s+)?(\w+)',
                r'(?:the|a|an)\s+(\w+)',
            ]
            for pattern in target_patterns:
                match = re.search(pattern, message_lower)
                if match:
                    extracted['target'] = match.group(1)
                    break

        # SKILL CHECK patterns
        elif action_type == ActionType.SKILL_CHECK:
            # Try to detect which skill
            for skill in SkillType:
                if skill.value in message_lower:
                    extracted['skill'] = skill.value
                    break

        # DICE ROLL patterns
        elif action_type == ActionType.DICE_ROLL:
            # Extract dice notation (e.g., "2d6+3", "1d20", "4d6kh3")
            dice_pattern = r'\b(\d+d\d+(?:[kKdD][hHlL]?\d+)?(?:[+\-]\d+)?)\b'
            match = re.search(dice_pattern, message)
            if match:
                extracted['notation'] = match.group(1)

        # MOVEMENT patterns
        elif action_type == ActionType.MOVEMENT:
            # Actor extraction — "move Grok to the bar"
            actor_match = re.search(r'(?:move|walk|send)\s+(\w+)\s+(?:to|toward|towards)', message_lower)
            if actor_match and actor_match.group(1).lower() not in ('me', 'my', 'us', 'to', 'the'):
                extracted['actor'] = actor_match.group(1).capitalize()

            # Target location — "walk to the bar", "move Grok to the bar", "go to the fireplace"
            location_match = re.search(
                r'(?:to|toward|towards)\s+(?:the\s+)?(.+?)(?:\s*$)',
                message_lower
            )
            if location_match:
                extracted['target_location'] = location_match.group(1).strip()

            # Direction patterns
            directions = {
                'north': 'north', 'south': 'south', 'east': 'east', 'west': 'west',
                'up': 'up', 'down': 'down', 'forward': 'forward', 'back': 'back'
            }
            for direction, value in directions.items():
                if direction in message_lower:
                    extracted['direction'] = value
                    break

            # Distance patterns
            distance_match = re.search(r'(\d+)\s*(?:feet|ft|meters|m)', message_lower)
            if distance_match:
                extracted['distance'] = int(distance_match.group(1))

        return extracted

    def _extract_with_llm_and_history(
        self,
        current_message: str,
        conversation_history: List[Dict],
        action_type: ActionType,
        context: Dict
    ) -> Dict[str, Any]:
        """
        LLM-based extraction using conversation context.

        Uses GPT to extract parameters from complex conversations.
        """
        if not self.has_llm:
            return {}

        try:
            import openai

            # Build conversation context
            # Support both formats: 'speaker'/'role' and 'message'/'content'
            conversation_lines = []
            for msg in conversation_history[-5:]:  # Last 5 messages
                speaker = msg.get('speaker') or ('player' if msg.get('role') == 'user' else 'dm')
                message = msg.get('message') or msg.get('content', '')
                conversation_lines.append(f"{speaker}: {message}")

            conversation_text = "\n".join(conversation_lines)
            conversation_text += f"\nplayer: {current_message}"

            # Determine what parameters to look for based on action type
            param_descriptions = self._get_parameter_descriptions(action_type)

            prompt = f"""Extract parameters from this D&D conversation.

Conversation:
{conversation_text}

Action type: {action_type.value}

Expected parameters:
{param_descriptions}

Spatial context:
- Nearby entities: {context.get('nearby_enemies', [])}
- Location: {context.get('location', 'unknown')}

Return ONLY a JSON object with extracted parameters. Only include parameters you're confident about.
If a parameter is not mentioned, omit it from the JSON.

Example response: {{"name": "Gandalf", "class_name": "Wizard", "level": 5}}
"""

            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a parameter extraction assistant for a D&D game. Extract parameters from conversations accurately."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=200
            )

            content = response.choices[0].message.content.strip()

            # Extract JSON from response (may be wrapped in ```json```)
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                content = content.split('```')[1].split('```')[0].strip()

            return json.loads(content)

        except Exception as e:
            print(f"LLM extraction failed: {e}")
            return {}

    def _extract_from_context(
        self,
        action_type: ActionType,
        context: Dict
    ) -> Dict[str, Any]:
        """
        Infer parameters from spatial/game context.

        Uses spatial awareness and game state to fill in obvious parameters.
        """
        extracted = {}

        # Note: We intentionally don't auto-fill parameters from context
        # to avoid incorrect assumptions. Context is used for suggestions only.

        return extracted

    def _get_parameter_descriptions(self, action_type: ActionType) -> str:
        """Get human-readable parameter descriptions for LLM prompt"""
        descriptions = {
            ActionType.CHARACTER_CREATION: """
- name (string): Character's name
- class_name (string): Character class (Wizard, Fighter, Rogue, etc.)
- race (string): Character race (Human, Elf, Dwarf, etc.)
- level (integer): Starting level (1-20)
""",
            ActionType.ATTACK: """
- actor (string): Name of character performing the attack (null if "I" or implied)
- target (string): Name of the enemy to attack
- weapon (string): Optional weapon to use
""",
            ActionType.SPELL_CAST: """
- spell_name (string): Name of the spell to cast
- target (string): Target of the spell (if applicable)
- spell_slot_level (integer): Optional spell slot level to use
""",
            ActionType.SKILL_CHECK: """
- skill (string): Which skill to check (athletics, stealth, perception, etc.)
- difficulty (integer): Optional DC (difficulty class)
""",
            ActionType.MOVEMENT: """
- actor (string): Name of character to move (null if "I" or implied)
- target_location (string): Name of place to move to (e.g., "bar", "fireplace", "entrance")
- direction (string): Which direction to move (north, south, east, west, etc.)
- distance (integer): Optional distance in feet
"""
        }

        return descriptions.get(action_type, "No specific parameters required")
