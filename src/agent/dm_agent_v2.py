"""
DM Agent V2 - Follows core principles:
- Rules are reference, not memory
- DM reasons without manuals
- Tools provide rules only when needed
- Two-stage retrieval for efficiency
"""
import json
from typing import List, Dict, Optional

from config import OPENAI_API_KEY, OPENAI_MODEL
from tools.dice_tools import DICE_TOOLS, DICE_FUNCTION_MAP
from tools.entity_tools import ENTITY_TOOLS, ENTITY_FUNCTION_MAP

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


class DMAgentV2:
    """
    AI Dungeon Master V2 - Two-stage retrieval architecture

    Core principles:
    1. DM brain has NO rules in passive context
    2. Rules are retrieved via tools (on-demand)
    3. Two-stage retrieval: metadata → embedding
    4. Entity caching (LRU)
    5. Context stays small (~500-1k tokens)
    """

    def __init__(self, model: str = None):
        if not OPENAI_AVAILABLE:
            raise ImportError("OpenAI package not installed")

        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not set")

        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.model = model or OPENAI_MODEL
        self.conversation_history = []

        # Combine all tools
        self.tools = DICE_TOOLS + ENTITY_TOOLS
        self.function_map = {**DICE_FUNCTION_MAP, **ENTITY_FUNCTION_MAP}

        # System prompt (NO RULES!)
        self.system_prompt = self._create_system_prompt()

    def _create_system_prompt(self) -> str:
        """
        System prompt with NO manual content

        DM should:
        - Track game state
        - Decide what rules are needed
        - Request tools for rules
        - NOT quote rules from memory
        """
        return """You are an expert Dungeon Master for D&D 5th Edition.

**Core Principles:**
1. You do NOT have the D&D manuals memorized
2. When you need a rule, spell, or monster stat - use the provided tools
3. Do NOT make up rules from memory - always look them up
4. Keep narrative flowing - retrieve rules only when mechanically necessary

**Your Responsibilities:**
- Guide players through adventures with immersive narration
- Track game state (HP, conditions, initiative)
- Decide when rules lookup is needed
- Make fair rulings when rules are unclear

**Available Tools:**

**Dice Rolling:**
- roll_dice(notation) - Any dice roll
- roll_attack(ability_mod, proficiency, advantage, disadvantage)
- roll_damage(dice, ability_mod, critical)
- roll_saving_throw(ability_mod, proficiency, advantage, disadvantage)

**Rule Lookup:**
- get_spell(name) - Look up a specific spell
- search_spells(query, level, school) - Find spells by description
- get_monster(name) - Look up monster stats
- search_monsters(query, cr, size) - Find monsters by description
- get_rule(query, domain) - Look up game rules
- get_condition(name) - Look up condition effects

**When to Use Tools:**
- Player casts a spell → get_spell("Spell Name")
- Combat with monster → get_monster("Monster Name")
- Unclear mechanic → get_rule("mechanic description")
- Player has condition → get_condition("Condition Name")

**When NOT to Use Tools:**
- Narrative descriptions (you can improvise)
- Obvious rules (roll d20 for checks)
- Roleplaying NPCs (no tools needed)

**Important:**
- Only use tools when you actually NEED the information
- Don't look up rules you already retrieved this session
- Keep the game moving - don't over-lookup

**Narrative Style:**
- Be descriptive and engaging
- Ask players what they want to do
- Describe outcomes, not just mechanics
- Use tools silently (players don't see tool calls)

Example turn:
Player: "I cast Fireball at the goblins"
You (internal): Need spell details → use get_spell("Fireball")
You (to player): "As you channel arcane energy, a bright streak flashes from your pointing finger to the center of the goblin group... [use spell details from tool] Make a DC X Dexterity saving throw for each goblin..."
"""

    def chat(self, user_message: str, mechanics_context: str = None) -> str:
        """
        Process user message with tool-based rule retrieval

        Flow:
        1. User message (optionally enriched with mechanics context)
        2. DM reasoning (no manuals in context)
        3. DM decides if rules needed → calls tools
        4. Tool results injected
        5. DM generates response with rules + narrative

        Args:
            user_message: Player's message
            mechanics_context: Optional mechanics results to include in the message
                             so the DM generates a mechanics-aware response in a single call
        """
        # Trim history if approaching context limit
        self._trim_conversation_history()

        # Build the message to send - include mechanics context if provided
        message_for_llm = user_message
        if mechanics_context:
            message_for_llm = (
                f"{user_message}\n\n"
                f"[The following game mechanics just occurred - incorporate these results "
                f"naturally into your narrative response:\n{mechanics_context}]"
            )

        # Add user message to history (store original message, not the enriched one)
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })

        # Build messages for API call - use enriched message for current turn
        api_messages = [
            {"role": "system", "content": self.system_prompt},
            *self.conversation_history[:-1],  # All history except current user message
            {"role": "user", "content": message_for_llm}  # Current message (possibly enriched)
        ]

        # Initial API call
        response = self.client.chat.completions.create(
            model=self.model,
            messages=api_messages,
            tools=self.tools,
            tool_choice="auto"
        )

        assistant_message = response.choices[0].message

        # Handle tool calls
        if assistant_message.tool_calls:
            # DM requested rules/rolls
            self.conversation_history.append({
                "role": "assistant",
                "content": assistant_message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in assistant_message.tool_calls
                ]
            })

            # Execute tools
            for tool_call in assistant_message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)

                print(f"🔧 DM calling tool: {function_name}({function_args})")

                # Call function
                if function_name in self.function_map:
                    result = self.function_map[function_name](**function_args)
                    self.conversation_history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result)
                    })

            # Get final response with tool results
            final_response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    *self.conversation_history
                ]
            )

            final_message = final_response.choices[0].message.content
            self.conversation_history.append({
                "role": "assistant",
                "content": final_message
            })

            return final_message

        else:
            # No tools needed, direct response
            response_text = assistant_message.content
            self.conversation_history.append({
                "role": "assistant",
                "content": response_text
            })

            return response_text

    def enhance_with_mechanics(self, original_response: str, mechanics_summary: str) -> str:
        """
        Enhance DM response with mechanical results from Command Agent

        Args:
            original_response: Initial narrative response from DM
            mechanics_summary: Formatted summary of mechanics that occurred

        Returns:
            Enhanced response incorporating mechanical outcomes
        """
        enhancement_prompt = f"""You previously said:
"{original_response}"

The following game mechanics just occurred:
{mechanics_summary}

Enhance your response to naturally incorporate these mechanical results into the narrative.
Keep it concise (1-2 sentences). Don't repeat yourself, just add the mechanical outcomes naturally.
Focus on the dramatic impact - how it affects the story.

Examples:
- If attack hit and killed enemy: "Your blade strikes true, piercing the goblin's heart. It collapses with a final gasp!"
- If attack missed: "Your swing goes wide as the goblin deftly dodges aside!"
- If critical hit: "Your rapier finds a gap in the armor with devastating precision!"
- If character created: "Your character sheet is ready - your adventure begins!"
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a D&D Dungeon Master enhancing narrative with mechanical outcomes. Be concise and dramatic."},
                    {"role": "user", "content": enhancement_prompt}
                ],
                temperature=0.7,
                max_tokens=200
            )

            enhancement = response.choices[0].message.content.strip()

            # Don't add to conversation history - this is a one-off enhancement
            return enhancement

        except Exception as e:
            print(f"Error enhancing response: {e}")
            # Fallback: return original with mechanics appended
            return f"{original_response}\n\n{mechanics_summary}"

    def reset_conversation(self):
        """Clear conversation history"""
        self.conversation_history = []

    def get_context_size(self) -> int:
        """Estimate current context size in tokens (rough)"""
        total_chars = sum(
            len(str(msg.get("content", "")))
            for msg in self.conversation_history
        )
        return total_chars // 4  # Rough estimate: 1 token ≈ 4 characters

    def _trim_conversation_history(self, max_tokens: int = 6000):
        """
        Trim oldest non-system messages when context approaches limit.

        Keeps the most recent messages while staying under the token budget.
        Always preserves at least the last 4 messages for context continuity.
        """
        current_size = self.get_context_size()
        if current_size <= max_tokens:
            return

        min_keep = 4  # Always keep at least last 4 messages
        while len(self.conversation_history) > min_keep and self.get_context_size() > max_tokens:
            # Remove oldest message (skip system messages if any got in)
            removed = self.conversation_history.pop(0)
            # If we removed a tool_calls message, also remove its tool responses
            if removed.get("tool_calls"):
                while (self.conversation_history and
                       self.conversation_history[0].get("role") == "tool"):
                    self.conversation_history.pop(0)
