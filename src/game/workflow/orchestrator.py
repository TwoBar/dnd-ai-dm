"""
Workflow Orchestrator - Slim delegation hub.

Coordinates agent execution in correct order:
1. Intent Detection
2. Reasoning Loop (if available)
3. Spatial Translation
4. Mechanics Execution
5. Narrative Generation

Delegates all heavy lifting to phase modules, formatters, and map builder.
"""
import logging
import time
import math
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

from agent.intent_agent import IntentAgent, Intent, ActionType
from agent.command import CommandAgent
from agent.dm_agent_v2 import DMAgentV2
from domain.game_state import GameState

from game.workflow.context import WorkflowContext, WorkflowResult, WorkflowState
from game.workflow.formatters import format_mechanics_summary
from game.workflow.map_builder import build_map_state


class WorkflowOrchestrator:
    """
    Orchestrates the correct execution order of agents.

    CRITICAL: Ensures mechanics execute BEFORE narrative generation.
    """

    def __init__(
        self,
        intent_agent: IntentAgent,
        command_agent: CommandAgent,
        dm_agent: DMAgentV2,
        game_state: GameState,
        spatial_agent=None,
        spatial_translator=None,
        reasoning_agent=None
    ):
        self.intent_agent = intent_agent
        self.command_agent = command_agent
        self.dm_agent = dm_agent
        self.game_state = game_state
        self.spatial_agent = spatial_agent
        self.spatial_translator = spatial_translator
        self.reasoning_agent = reasoning_agent

    def process_message(
        self, user_message: str, session_id: str, message_history: List[Dict]
    ) -> WorkflowResult:
        """Process user message through the complete workflow."""
        context = WorkflowContext(user_message=user_message, session_id=session_id)

        try:
            # PHASE 0.5: Check pending conversation
            pending_intent = self._check_pending_conversation(session_id)

            # PHASE 1: Intent detection
            context.current_state = WorkflowState.DETECTING_INTENT
            if pending_intent:
                intent = pending_intent
            else:
                intent = self._detect_intent(user_message, context, message_history)
            context.intent = intent
            context.add_timing_marker(WorkflowState.DETECTING_INTENT)

            # PHASE 1.05: Handle unclear intent
            if intent.action_type == ActionType.UNCLEAR:
                return self._handle_unclear(intent, context)

            # PHASE 1.1: Reasoning loop
            reasoning_result = self._run_reasoning(intent, user_message, message_history, session_id, context)
            if reasoning_result:
                if reasoning_result.decision == 'clarify':
                    return self._format_clarify_result(reasoning_result, intent, context)
                elif reasoning_result.decision == 'reject':
                    return self._format_reject_result(reasoning_result, intent, context)
                elif reasoning_result.decision == 'execute':
                    final_intent = reasoning_result.final_intent
                    if reasoning_result.extracted_params:
                        final_intent.extracted_parameters = reasoning_result.extracted_params
                    context.intent = final_intent
                    intent = final_intent
                    if reasoning_result.reasoning_trace:
                        context.reasoning_trace = reasoning_result.reasoning_trace

            # PHASE 1.5: Spatial translation
            if self.spatial_agent and self.spatial_translator:
                self._translate_spatial_references(intent, context)

            # PHASE 2: Mechanics execution
            mechanics_result = None
            if intent.requires_mechanics():
                context.current_state = WorkflowState.EXECUTING_MECHANICS
                mechanics_result = self._execute_mechanics(intent, user_message, message_history, context)
                context.add_timing_marker(WorkflowState.EXECUTING_MECHANICS)

                # Rebuild map state after movement so UI gets updated positions
                if intent.action_type == ActionType.MOVEMENT and self.spatial_agent:
                    location_id = (context.spatial_context or {}).get('location_id', 'tavern_main')
                    context.map_state = build_map_state(self.spatial_agent, session_id, location_id)

            # PHASE 2.5: Place new character
            if context.game_state_changes.get('character_created') and self.spatial_agent:
                self._place_new_character_in_spatial_system(intent, context, session_id)

            # PHASE 3: Narrative generation
            context.current_state = WorkflowState.GENERATING_NARRATIVE
            dm_response = self._generate_narrative(user_message, intent, mechanics_result, context)
            context.dm_response = dm_response
            context.add_timing_marker(WorkflowState.GENERATING_NARRATIVE)

            # PHASE 4: Prepare result
            context.current_state = WorkflowState.BROADCASTING
            self._clear_conversation_state_if_done(session_id, mechanics_result, intent)

            return WorkflowResult(
                success=True,
                dm_response=dm_response,
                intent=intent,
                mechanics_summary=format_mechanics_summary(mechanics_result),
                game_state_changes=context.game_state_changes,
                context=context,
                map_state=context.map_state
            )

        except Exception as e:
            context.current_state = WorkflowState.ERROR
            logger.error("Workflow error: %s", e, exc_info=True)
            self._clear_conversation_state_on_error(session_id)

            return WorkflowResult(
                success=False,
                dm_response="I encountered an error processing your request.",
                intent=context.intent,
                mechanics_summary="",
                game_state_changes={},
                context=context,
                error=str(e),
                map_state=context.map_state
            )

    # ========================================================================
    # PHASE IMPLEMENTATIONS
    # ========================================================================

    def _check_pending_conversation(self, session_id: str) -> Optional[Intent]:
        if not self.reasoning_agent:
            return None
        conv_state = self.reasoning_agent.conversation_manager.get_or_create(session_id)
        if conv_state.pending_intent and not conv_state.is_expired():
            conv_state.increment_attempts()
            logger.info("Resuming pending conversation for %s (attempt %d/%d)",
                        conv_state.pending_intent.action_type.value,
                        conv_state.attempt_count, conv_state.max_attempts)
            return conv_state.pending_intent
        # If expired (timeout or max attempts), clear and treat as fresh
        if conv_state.pending_intent and conv_state.is_expired():
            logger.info("Pending conversation expired for session %s (attempts=%d), clearing",
                        session_id, conv_state.attempt_count)
            conv_state.clear()
        return None

    def _detect_intent(self, user_message, context, message_history):
        intent_context = {
            'in_combat': self.game_state.in_combat,
            'current_creature': None,
        }
        if self.game_state.characters:
            intent_context['character_exists'] = True
            intent_context['player_characters'] = [c.name for c in self.game_state.characters]
        if self.spatial_agent and hasattr(context, 'session_id'):
            actor_entity = self._resolve_actor(
                Intent(action_type=ActionType.NARRATIVE_ONLY, confidence=0.0),
                context.session_id
            )
            if actor_entity:
                nearby = self.spatial_agent.get_entities_near(
                    location_id=actor_entity['location_id'],
                    x=actor_entity['x'], y=actor_entity['y'], radius=15.0
                )
                scene_entities = []
                for e in nearby:
                    if e.get('id') == actor_entity.get('id'):
                        continue  # Skip self
                    # Determine entity type
                    etype = 'feature'
                    if e.get('creature_id'):
                        eid = e.get('id', '')
                        if eid.startswith('pc_'):
                            etype = 'player'
                        elif eid.startswith('monster_'):
                            etype = 'monster'
                        else:
                            etype = 'npc'
                    dist = ((e['x'] - actor_entity['x'])**2 + (e['y'] - actor_entity['y'])**2)**0.5
                    scene_entities.append({
                        'name': e.get('entity_name', 'unknown'),
                        'type': etype,
                        'distance': round(dist, 1)
                    })
                intent_context['scene_entities'] = scene_entities
                intent_context['current_location'] = actor_entity.get('location_id')

        intent = self.intent_agent.detect(user_message, intent_context, message_history=message_history)
        logger.info("Intent detected: %s (confidence: %.2f, method: %s)",
                    intent.action_type.value, intent.confidence, intent.detection_method)
        return intent

    def _run_reasoning(self, intent, user_message, message_history, session_id, context):
        if not self.reasoning_agent:
            return None
        return self.reasoning_agent.reason(
            initial_intent=intent,
            user_message=user_message,
            conversation_history=message_history,
            session_id=session_id,
            context=self._build_reasoning_context(context)
        )

    def _execute_mechanics(self, intent, user_message, message_history, context):
        from agent.skill_query_service import ACTION_TOOL_REGISTRY
        logger.info("Executing mechanics for %s", intent.action_type.value)

        actor = self._resolve_actor(intent, context.session_id)
        tool_name = ACTION_TOOL_REGISTRY.get(intent.action_type)

        if intent.action_type == ActionType.MOVEMENT and self.spatial_agent and not actor:
            # No actor found for movement — return error action
            logger.warning("Movement failed: no actor found for session %s", context.session_id)
            actions = [{
                'action': 'move_character',
                'status': 'error',
                'success': False,
                'error': 'No character found to move. Create a character first.',
            }]
            return {
                'actions': actions,
                'dice_rolls': context.dice_rolls,
                'game_state_changes': context.game_state_changes,
            }

        if intent.action_type == ActionType.MOVEMENT and self.spatial_agent and actor:
            # Spatial movement — use resolved actor
            from tools.movement_tools import move_character
            character_name = actor['creature_id']
            movement_params = {}
            if intent.extracted_parameters:
                movement_params = {k: v for k, v in intent.extracted_parameters.items()
                                   if k in {'direction', 'distance', 'target_location'}}
            if context.spatial_translation and 'target_position' in context.spatial_translation:
                target_pos = context.spatial_translation['target_position']
                movement_params['target_x'] = target_pos[0]
                movement_params['target_y'] = target_pos[1]
            tool_result = move_character(
                character_name=character_name, spatial_agent=self.spatial_agent,
                session_id=context.session_id, game_state=self.game_state, **movement_params
            )
            if tool_result:
                if 'tool' in tool_result and 'action' not in tool_result:
                    tool_result['action'] = tool_result['tool']
                status = tool_result.get('status')
                tool_result['success'] = status in ('success', 'narrative')
                actions = [tool_result]
            else:
                actions = None
        elif tool_name and intent.extracted_parameters and self.command_agent:
            # Registry-mapped tool with pre-extracted params
            logger.info("Registry: %s -> %s", intent.action_type.value, tool_name)
            tool_result = self.command_agent._execute_tool({
                'name': tool_name, 'arguments': intent.extracted_parameters
            })
            if tool_result:
                if 'tool' in tool_result and 'action' not in tool_result:
                    tool_result['action'] = tool_result['tool']
                if tool_result.get('status') == 'success':
                    tool_result['success'] = True
                actions = [tool_result]
            else:
                actions = None
        elif self.command_agent:
            # Fallback: LLM-based tool selection (for unmapped/complex actions)
            actions = self.command_agent.process(
                user_message=user_message, dm_response="", chat_history=message_history
            )
        else:
            actions = None

        if actions:
            context.mechanics_actions = actions
            for action in actions:
                if 'dice_rolls' in action:
                    context.dice_rolls.extend(action['dice_rolls'])
                if action.get('success'):
                    action_type = action.get('action')
                    if action_type in ['apply_damage', 'heal_character']:
                        context.game_state_changes['hp_changed'] = True
                    elif action_type in ['finalize_character', 'draft_character']:
                        context.game_state_changes['character_created'] = True
            logger.info("Executed %d mechanics actions", len(actions))
            return {
                'actions': actions,
                'dice_rolls': context.dice_rolls,
                'game_state_changes': context.game_state_changes
            }
        return None

    def _generate_narrative(self, user_message, intent, mechanics_result, context):
        logger.info("Generating narrative (mechanics: %s)", mechanics_result is not None)

        # Build character context so the DM knows the party's state
        char_context = self._build_character_context()

        if mechanics_result:
            mechanics_summary = format_mechanics_summary(mechanics_result)
            if intent.action_type == ActionType.CHARACTER_CREATION:
                return self._generate_character_welcome(mechanics_result, mechanics_summary)
            full_context = mechanics_summary
            if char_context:
                full_context = f"{char_context}\n\n{mechanics_summary}"
            return self.dm_agent.chat(user_message, mechanics_context=full_context)
        else:
            context_parts = []
            if char_context:
                context_parts.append(char_context)
            spatial_text = self._build_spatial_context_text(context)
            if spatial_text:
                context_parts.append(f"[Spatial Context: {spatial_text}]")
            if context_parts:
                enriched = f"{user_message}\n\n{''.join(context_parts)}"
                return self.dm_agent.chat(enriched)
            return self.dm_agent.chat(user_message)

    def _build_character_context(self) -> str:
        """Build a summary of the party's characters for the DM."""
        if not self.game_state or not self.game_state.characters:
            return ""
        lines = ["[Party Status:"]
        for char in self.game_state.characters:
            parts = [f"  {char.name}: Lvl {char.level}"]
            if char.race:
                parts.append(char.race)
            parts.append(f"{char.class_name}")
            parts.append(f"| HP {char.hp}/{char.max_hp}, AC {char.ac}")
            if char.conditions:
                parts.append(f"| Conditions: {', '.join(char.conditions)}")
            line = ' '.join(parts)
            lines.append(line)
            if char.spells_known:
                spell_names = [s.replace('-', ' ').title() for s in char.spells_known]
                lines.append(f"    Spells: {', '.join(spell_names)}")
            if char.spell_slots:
                slots = ', '.join(f"Lvl {k}: {v}" for k, v in sorted(char.spell_slots.items()))
                lines.append(f"    Spell slots: {slots}")
        lines.append("]")
        return '\n'.join(lines)

    def _generate_character_welcome(self, mechanics_result, mechanics_summary):
        actions = mechanics_result.get('actions', [])
        char_name = 'Unknown'
        char_details = ''
        for action in actions:
            if action.get('action') == 'draft_character' and action.get('success'):
                char_name = action.get('name', 'Unknown')
                char_details = action.get('details', '')
                break
        welcome_prompt = (
            f"The player just completed character creation. Their character is:\n"
            f"{char_details if char_details else f'{char_name}, a new adventurer'}\n\n"
            f"Welcome them to the game world warmly! Describe their starting location "
            f"(The Prancing Pony tavern in Bree), set the scene, and ask what they'd like to do."
        )
        dm_welcome = self.dm_agent.chat(welcome_prompt)
        return f"{mechanics_summary}\n\n{dm_welcome}"

    # ========================================================================
    # SPATIAL HELPERS
    # ========================================================================

    def _translate_spatial_references(self, intent, context):
        if not self.spatial_agent or not self.spatial_translator:
            return
        actor_entity = self._resolve_actor(intent, context.session_id)
        if not actor_entity:
            return
        actor_pos = (actor_entity['x'], actor_entity['y'])
        location_id = actor_entity.get('location_id', 'tavern_main')
        location_info = self.spatial_agent.get_location(location_id)
        location_name = location_info.get('name', location_id) if location_info else location_id
        location_desc = location_info.get('description', '') if location_info else ''

        nearby_entities = self.spatial_agent.get_entities_near(
            location_id=location_id, x=actor_pos[0], y=actor_pos[1], radius=10.0
        )
        context.spatial_context = {
            'actor_position': actor_pos,
            'actor_entity_id': actor_entity.get('id', actor_entity.get('entity_id', 'unknown')),
            'location_id': location_id, 'location_name': location_name,
            'location_description': location_desc,
            'nearby_entities': nearby_entities, 'nearby_count': len(nearby_entities)
        }
        context.map_state = build_map_state(self.spatial_agent, context.session_id, location_id)

        if intent.target:
            spatial_ref = self.spatial_translator.translate_target(
                natural_language=intent.target, current_location_id=location_id,
                observer_position=actor_pos, session_id=context.session_id
            )
            if spatial_ref:
                context.spatial_translation = {
                    'target_entity_id': spatial_ref.entity_id,
                    'target_position': spatial_ref.position,
                    'distance': spatial_ref.distance,
                    'reference_type': spatial_ref.reference_type,
                    'confidence': spatial_ref.confidence
                }

        # For MOVEMENT, also translate target_location from extracted_parameters
        if not context.spatial_translation and intent.action_type == ActionType.MOVEMENT:
            target_loc = (intent.extracted_parameters or {}).get('target_location')
            if target_loc:
                spatial_ref = self.spatial_translator.translate_target(
                    natural_language=target_loc,
                    current_location_id=location_id,
                    observer_position=actor_pos,
                    session_id=context.session_id
                )
                if spatial_ref and spatial_ref.position:
                    context.spatial_translation = {
                        'target_entity_id': spatial_ref.entity_id,
                        'target_position': spatial_ref.position,
                        'distance': spatial_ref.distance,
                        'reference_type': spatial_ref.reference_type,
                        'confidence': spatial_ref.confidence
                    }

    def _resolve_actor(self, intent: Intent, session_id: str):
        """Resolve which spatial entity performs this action.

        Priority cascade:
        1. Explicitly named in intent.actor — "move Grok to..."
        2. Combat current_turn — whose turn in initiative
        3. Single-PC default — if only one character, use it
        4. None — ambiguous, reasoning should ask "which character?"
        """
        if not self.spatial_agent:
            return None

        # 1. Explicit actor from intent
        if intent.actor:
            entity = self.spatial_agent.get_entity_by_creature_id(intent.actor)
            if entity and entity.get('session_id') == session_id:
                return entity
            # Case-insensitive match against known characters
            for char in self.game_state.characters:
                if char.name.lower() == intent.actor.lower():
                    entity = self.spatial_agent.get_entity_by_creature_id(char.name)
                    if entity and entity.get('session_id') == session_id:
                        return entity

        # 2. Combat turn (covers both PC and monster turns)
        if self.game_state.in_combat and self.game_state.current_turn:
            entity = self.spatial_agent.get_entity_by_creature_id(
                self.game_state.current_turn
            )
            if entity and entity.get('session_id') == session_id:
                return entity

        # 3. Single-PC default (unambiguous — most common case)
        if len(self.game_state.characters) == 1:
            entity = self.spatial_agent.get_entity_by_creature_id(
                self.game_state.characters[0].name
            )
            if entity and entity.get('session_id') == session_id:
                return entity

        # 4. Multi-PC, no combat, no explicit name — try any PC in session
        for char in self.game_state.characters:
            entity = self.spatial_agent.get_entity_by_creature_id(char.name)
            if entity and entity.get('session_id') == session_id:
                return entity

        return None

    def _place_new_character_in_spatial_system(self, intent, context, session_id):
        if not self.spatial_agent:
            return
        character_name = None
        if intent.extracted_parameters:
            character_name = intent.extracted_parameters.get('name')
        if not character_name and context.mechanics_actions:
            for action in context.mechanics_actions:
                if action.get('action') in ['draft_character', 'finalize_character']:
                    character_name = action.get('name')
                    break
        if not character_name:
            return

        character = self.game_state.get_character(character_name)
        if not character:
            return
        existing = self.spatial_agent.get_entity_by_creature_id(character_name)
        if existing and existing.get('session_id') == session_id:
            return  # Already placed in this session

        from game.spatial.spatial_agent import EntityPlacement
        entity_id = f"pc_{character_name.lower().replace(' ', '_')}_{session_id[:8]}"

        # Offset spawn position based on session hash to avoid overlap
        import hashlib
        session_hash = int(hashlib.md5(session_id.encode()).hexdigest()[:4], 16)
        spawn_x = 4.0 + (session_hash % 3)        # 4-6 range (near center)
        spawn_y = 1.5 + (session_hash % 5) * 0.3   # 1.5-2.7 range (near entrance)

        placement = EntityPlacement(
            entity_id=entity_id, entity_name=character_name,
            x=spawn_x, y=spawn_y, z=0.0, volume_m3=0.065,
            footprint_width=0.5, footprint_depth=0.5,
            height=1.7, orientation_degrees=0, is_blocking=True
        )
        success = self.spatial_agent.place_entity(
            session_id=session_id, entity_id=entity_id, location_id='tavern_main',
            placement=placement, creature_id=character_name, sprite_id='player',
            description=f"{character.race} {character.class_name}"
        )
        if success:
            context.map_state = build_map_state(self.spatial_agent, session_id, 'tavern_main')

    # ========================================================================
    # REASONING/FORMATTING HELPERS
    # ========================================================================

    def _build_reasoning_context(self, context):
        reasoning_context = {'session_id': context.session_id, 'user_message': context.user_message}
        if context.spatial_context:
            nearby = context.spatial_context.get('nearby_entities', [])
            reasoning_context['nearby_enemies'] = [
                {'name': e.get('entity_metadata', {}).get('name', 'unknown'),
                 'distance': self._calculate_distance(
                     context.spatial_context.get('actor_position'), (e.get('x'), e.get('y')))}
                for e in nearby if e.get('entity_metadata', {}).get('type') in ['monster', 'npc']
            ]
            reasoning_context['location'] = context.spatial_context.get('location_id')
        if context.spatial_translation:
            reasoning_context['spatial_translation'] = context.spatial_translation
        if self.game_state:
            current_actor = self._get_current_actor()
            if current_actor:
                reasoning_context['weapon_range'] = getattr(current_actor, 'weapon_range', 1.5)
                reasoning_context['movement_speed'] = getattr(current_actor, 'movement_speed', 9.0)
                reasoning_context['spell_slots'] = getattr(current_actor, 'spell_slots', None) or {}
                reasoning_context['spells_known'] = getattr(current_actor, 'spells_known', None) or []
                reasoning_context['caster_class'] = getattr(current_actor, 'class_name', '')
                reasoning_context['equipped_weapons'] = getattr(current_actor, 'equipped_weapons', [])
            reasoning_context['in_combat'] = self.game_state.in_combat
        return reasoning_context

    def _get_current_actor(self):
        if not self.game_state:
            return None
        if self.game_state.in_combat and self.game_state.current_turn:
            char = self.game_state.get_character(self.game_state.current_turn)
            if char:
                return char
        if self.game_state.characters:
            return self.game_state.characters[0]
        return None

    def _calculate_distance(self, pos1, pos2):
        if not pos1 or not pos2:
            return 0.0
        return math.sqrt((pos2[0] - pos1[0])**2 + (pos2[1] - pos1[1])**2)

    def _build_spatial_context_text(self, context):
        if not context.spatial_context:
            return ""
        parts = []
        loc_name = context.spatial_context.get('location_name')
        if loc_name:
            parts.append(f"Currently in: {loc_name}")
        nearby = context.spatial_context.get('nearby_entities', [])
        if nearby:
            descs = []
            for e in nearby[:5]:
                meta = e.get('entity_metadata', {})
                descs.append(f"{meta.get('name', 'unknown')} ({meta.get('type', 'entity')})")
            parts.append(f"Nearby: {', '.join(descs)}")
        return " | ".join(parts) if parts else ""

    def _handle_unclear(self, intent, context):
        response = (
            "I'm having trouble understanding what you want to do.\n\n"
            "Could you try rephrasing? For example:\n"
            "- **Attack**: \"I attack the goblin\"\n"
            "- **Spell**: \"I cast fireball at the orcs\"\n"
            "- **Skill**: \"I try to sneak past\"\n"
            "- **Movement**: \"I move north\"\n"
            "- **Character creation**: \"I want to create a wizard\"\n"
            "- **Roll dice**: \"1d20+5\"\n"
        )
        return WorkflowResult(
            success=False, dm_response=response, intent=intent,
            mechanics_summary="", game_state_changes={}, context=context,
            error="Intent detection unavailable", map_state=None
        )

    def _format_clarify_result(self, reasoning_result, intent, context):
        response = ""
        if reasoning_result.reasoning_trace:
            trace = " → ".join(reasoning_result.reasoning_trace[-3:])
            logger.debug("Reasoning trace: %s", trace)
        response += reasoning_result.clarification_question
        if reasoning_result.suggestions:
            response += "\n\n**Options:**\n"
            for i, s in enumerate(reasoning_result.suggestions, 1):
                response += f"{i}. {s}\n"
        if reasoning_result.is_learning:
            response += "\n\n💡 *If you confirm, I'll learn this action for future use!*"
        return WorkflowResult(
            success=True, dm_response=response, intent=intent,
            mechanics_summary="", game_state_changes={}, context=context, map_state=None
        )

    def _format_reject_result(self, reasoning_result, intent, context):
        response = f"❌ {reasoning_result.rejection_reason}"
        if reasoning_result.alternatives:
            response += "\n\n💡 **You could instead:**\n"
            for i, alt in enumerate(reasoning_result.alternatives, 1):
                response += f"{i}. {alt}\n"
        return WorkflowResult(
            success=False, dm_response=response, intent=intent,
            mechanics_summary="", game_state_changes={}, context=context,
            error="Action rejected: " + reasoning_result.rejection_reason, map_state=None
        )

    def _clear_conversation_state_if_done(self, session_id, mechanics_result, intent):
        if not self.reasoning_agent:
            return
        conv_state = self.reasoning_agent.conversation_manager.get_or_create(session_id)
        if conv_state.pending_intent and (mechanics_result or not intent.requires_mechanics()):
            conv_state.clear()

    def _clear_conversation_state_on_error(self, session_id):
        if not self.reasoning_agent:
            return
        try:
            conv_state = self.reasoning_agent.conversation_manager.get_or_create(session_id)
            if conv_state.pending_intent:
                conv_state.clear()
        except Exception:
            pass

    def get_performance_metrics(self, context: WorkflowContext) -> Dict:
        latencies = context.get_phase_latencies_ms()
        return {
            'workflow_id': context.workflow_id,
            'total_latency_ms': latencies['total'],
            'phase_latencies': latencies,
            'intent_method': context.intent.detection_method if context.intent else None,
            'mechanics_executed': len(context.mechanics_actions),
            'dice_rolled': len(context.dice_rolls)
        }
