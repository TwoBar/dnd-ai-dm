"""
Command Agent - Slim dispatch hub for game mechanics.

Observes messages, gets tool calls from LLM, dispatches to tool modules.
"""
import json
from typing import Dict, List, Optional, Any
from openai import OpenAI
from config import OPENAI_API_KEY

from agent.command.tool_definitions import get_tool_definitions
from agent.command.character_tools import (
    tool_draft_character, tool_update_draft_character, tool_finalize_character
)
from agent.command.combat_tools import (
    tool_create_monster, tool_apply_damage, tool_heal_character,
    tool_start_combat, tool_set_initiative, tool_add_condition, tool_remove_condition
)
from agent.command.dice_tools import tool_roll_dice
from tools.spell_tools import cast_spell


class CommandAgent:
    """
    Silent meta-agent that observes all messages and executes game mechanics.

    NEVER responds to players directly - only calls tools.
    """

    def __init__(self, game_state, formula_service=None, spatial_agent=None):
        """Initialize the Command Agent.

        Args:
            game_state: GameState instance to manage
            formula_service: Optional FormulaService for dynamic formula calculations
            spatial_agent: Optional SpatialAgent for removing dead monsters (ISSUE 9)
        """
        self.game_state = game_state
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.model = "gpt-4o"
        self.formula_service = formula_service
        self.spatial_agent = spatial_agent
        self.custom_modifiers = {}
        self.custom_rules = {}

    def process(self, user_message: str, dm_response: str = "", chat_history: List[Dict] = None) -> List[Dict]:
        """Process a message exchange and execute appropriate commands."""
        chat_history = chat_history or []
        context = self._build_context(user_message, dm_response, chat_history)
        tool_calls = self._get_tool_calls(context)

        actions = []
        for tool_call in tool_calls:
            action = self._execute_tool(tool_call)
            if action:
                actions.append(action)

        return actions

    def _build_context(self, user_message: str, dm_response: str, chat_history: List[Dict]) -> str:
        """Build context string for the agent."""
        context = "=== Recent Conversation ===\n"

        for msg in chat_history[-10:]:
            speaker = msg.get('speaker', 'Unknown')
            message = msg.get('message', '')
            context += f"{speaker}: {message}\n"

        context += f"\nPlayer: {user_message}\n"
        if dm_response:
            context += f"DM: {dm_response}\n"

        context += "\n=== Current Game State ===\n"
        context += f"Characters: {len(self.game_state.characters)}\n"
        for char in self.game_state.characters:
            context += f"  - {char.name} (Lvl {char.level} {char.class_name}): HP {char.hp}/{char.max_hp}, AC {char.ac}\n"

        context += f"Monsters: {len(self.game_state.monsters)}\n"
        for monster in self.game_state.monsters:
            context += f"  - {monster.name}: HP {monster.hp}/{monster.max_hp}, AC {monster.ac}\n"

        context += f"Combat Active: {self.game_state.in_combat}\n"

        return context

    def _get_tool_calls(self, context: str) -> List[Dict]:
        """Get tool calls from OpenAI based on context."""
        system_prompt = """You are a silent meta-agent that manages D&D 5E game mechanics.

You observe player messages and execute game mechanics. You NEVER respond with text to players.

Your ONLY job is to call the appropriate tools when game mechanics are needed.
Note: The DM response may not be available yet (mechanics execute before narrative).

## When to Act (BE CONSERVATIVE!)

**Character Creation - BE SMART about timing:**
- User says "create a character" -> WAIT (don't create yet, DM will ask for details)
- User provides race + class (e.g., "Tiefling paladin") -> WAIT, gather more info
- User provides DETAILED build (class, race, stats method, skills) -> CREATE with available info
- User says "rest is up to you", "finalize", "let's go", "sounds good" -> CREATE if enough info
- User says "change name to X" or "call them X" -> update_draft_character with new name

**Combat:**
- DM mentions monster appearing -> create_monster
- Combat starts -> start_combat
- User says "I attack" -> roll attack (1d20 + mods), if hit roll damage, apply_damage
- User/DM mentions damage -> apply_damage
- User/DM mentions healing -> heal_character

**Dice Rolling:**
- User says "I roll" or "roll for" -> roll_dice
- Attack declared -> roll attack + damage automatically

**Conditions:**
- Mentioned in narrative -> add_condition or remove_condition

## Important Rules

1. NEVER respond with text - only call tools
2. BE CONSERVATIVE - wait for confirmation before creating characters
3. If uncertain, don't act (better to miss than to act wrongly)

Call the appropriate tools based on what you observe."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": context}
                ],
                tools=get_tool_definitions(),
                tool_choice="auto"
            )

            tool_calls = []
            if response.choices[0].message.tool_calls:
                for tool_call in response.choices[0].message.tool_calls:
                    tool_calls.append({
                        'name': tool_call.function.name,
                        'arguments': json.loads(tool_call.function.arguments)
                    })

            return tool_calls

        except Exception as e:
            print(f"Error getting tool calls: {e}")
            return []

    def _execute_tool(self, tool_call: Dict) -> Optional[Dict]:
        """Execute a single tool call and return the action taken."""
        tool_name = tool_call['name']
        args = tool_call['arguments']

        try:
            if tool_name == "draft_character":
                supported_params = {'name', 'race', 'class_name', 'level', 'ability_scores', 'background'}
                filtered_args = {k: v for k, v in args.items() if k in supported_params}
                return tool_draft_character(self.game_state, **filtered_args)
            elif tool_name == "update_draft_character":
                return tool_update_draft_character(self.game_state, **args)
            elif tool_name == "finalize_character":
                return tool_finalize_character(self.game_state, **args)
            elif tool_name == "roll_dice":
                return tool_roll_dice(self.game_state, **args)
            elif tool_name == "create_monster":
                return tool_create_monster(self.game_state, **args)
            elif tool_name == "apply_damage":
                return tool_apply_damage(self.game_state, spatial_agent=self.spatial_agent, **args)
            elif tool_name == "heal_character":
                return tool_heal_character(self.game_state, **args)
            elif tool_name == "start_combat":
                return tool_start_combat(self.game_state)
            elif tool_name == "set_initiative":
                return tool_set_initiative(self.game_state, **args)
            elif tool_name == "add_condition":
                return tool_add_condition(self.game_state, **args)
            elif tool_name == "remove_condition":
                return tool_remove_condition(self.game_state, **args)
            elif tool_name == "cast_spell":
                return cast_spell(
                    game_state=self.game_state,
                    spatial_agent=self.spatial_agent,
                    **args
                )
            else:
                print(f"Unknown tool: {tool_name}")
                return None

        except Exception as e:
            print(f"Error executing {tool_name}: {e}")
            return {'tool': tool_name, 'status': 'error', 'error': str(e)}

    def calculate_formula(self, formula_name: str, entity_id: str, entity_type: str = "character") -> Optional[Any]:
        """Calculate a formula value for an entity using FormulaService."""
        if not self.formula_service:
            print("[CommandAgent] FormulaService not initialized - using legacy calculations")
            return None

        try:
            result = self.formula_service.execute_for_entity(
                formula_name=formula_name,
                entity_id=entity_id,
                entity_type=entity_type
            )

            print(f"[Formula] {formula_name} = {result.value} for {entity_id}")
            if result.modifiers_applied:
                print(f"[Formula] Applied modifiers: {[m.source for m in result.modifiers_applied]}")

            return result.value
        except Exception as e:
            print(f"[CommandAgent] Formula calculation failed: {e}")
            return None
