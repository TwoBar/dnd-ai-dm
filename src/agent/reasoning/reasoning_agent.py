"""
Reasoning Agent - Core iterative reasoning loop.

Implements a 5-step loop:
1. Consult RAG for domain knowledge
2. Consult skills for execution capabilities
3. Extract parameters from full conversation
4. Validate feasibility
5. Decide: execute, clarify, or reject

Delegates question generation, learning, and improvised actions
to sub-modules.
"""
from typing import Dict, List, Optional

from agent.intent_agent import Intent, ActionType
from agent.rag_query_service import RAGQueryService
from agent.skill_query_service import SkillQueryService
from agent.parameter_extractor import ParameterExtractor
from agent.feasibility_validator import FeasibilityValidator
from agent.conversation_state import ConversationStateManager
from agent.reasoning_types import ReasoningCycleResult

from agent.reasoning.question_generator import (
    generate_question_with_rag,
    extract_option_keywords,
    normalize_option_value,
)
from agent.reasoning.learning_handler import handle_unknown_action
from agent.reasoning.improvised_action import (
    adjudicate_improvised_action,
    ImprovisedMechanics,
)


class ReasoningAgent:
    """
    Implements iterative reasoning loop.

    Continuously consults RAG + skills, extracts parameters, validates,
    and decides whether to execute, clarify, or reject.
    """

    def __init__(
        self,
        rag_query: RAGQueryService,
        skill_query: SkillQueryService,
        param_extractor: ParameterExtractor,
        validator: FeasibilityValidator,
        conversation_manager: ConversationStateManager,
        pattern_generator=None
    ):
        self.rag_query = rag_query
        self.skill_query = skill_query
        self.param_extractor = param_extractor
        self.validator = validator
        self.conversation_manager = conversation_manager
        self.pattern_generator = pattern_generator

    def reason(
        self,
        initial_intent: Intent,
        user_message: str,
        conversation_history: List[Dict],
        session_id: str,
        context: Optional[Dict] = None
    ) -> ReasoningCycleResult:
        """
        Iterative reasoning loop.

        Returns:
            ReasoningCycleResult with decision: 'execute', 'clarify', or 'reject'
        """
        context = context or {}
        reasoning_trace = []
        reasoning_trace.append(
            f"Initial intent: {initial_intent.action_type.value} "
            f"(confidence: {initial_intent.confidence:.2f})"
        )

        conv_state = self.conversation_manager.get_or_create(session_id)

        # Narrative-only intents bypass skill system
        narrative_only_actions = [
            ActionType.NARRATIVE_ONLY,
            ActionType.CONVERSATION,
            ActionType.INVESTIGATION,
        ]

        if initial_intent.action_type in narrative_only_actions:
            reasoning_trace.append("Narrative-only intent - bypassing skill system")
            return ReasoningCycleResult(
                decision='execute',
                confidence=initial_intent.confidence,
                reasoning_trace=reasoning_trace,
                final_intent=initial_intent,
                extracted_params={}
            )

        # STEP 1: Consult RAG
        reasoning_trace.append("Step 1: Consulting RAG for domain knowledge...")

        action_possibilities = self.rag_query.query_possible_actions(
            user_message=user_message, context=context
        )
        reasoning_trace.append(f"RAG found {len(action_possibilities)} possible actions")

        if action_possibilities and action_possibilities[0].confidence > initial_intent.confidence:
            reasoning_trace.append(
                f"RAG suggests: {action_possibilities[0].action_name} "
                f"(confidence: {action_possibilities[0].confidence:.2f})"
            )

        requirements = self.rag_query.query_action_requirements(
            action_type=initial_intent.action_type,
            action_name=initial_intent.spell_name or initial_intent.action_type.value,
            context=context
        )
        reasoning_trace.append(f"RAG says required params: {requirements.required_params}")

        # STEP 2: Consult Skills
        reasoning_trace.append("Step 2: Consulting skill system...")

        applicable_skills = self.skill_query.query_applicable_skills(
            action_type=initial_intent.action_type,
            user_message=user_message,
            context=context
        )
        reasoning_trace.append(f"Found {len(applicable_skills)} applicable skills")

        if not applicable_skills:
            reasoning_trace.append("No skills can execute this action")

            if action_possibilities and action_possibilities[0].confidence > 0.5:
                reasoning_trace.append("Attempting to learn from RAG...")
                return handle_unknown_action(
                    user_message=user_message,
                    initial_intent=initial_intent,
                    action_possibilities=action_possibilities,
                    reasoning_trace=reasoning_trace,
                    session_id=session_id,
                    rag_query=self.rag_query,
                    conversation_manager=self.conversation_manager
                )
            else:
                return ReasoningCycleResult(
                    decision='reject',
                    confidence=1.0,
                    reasoning_trace=reasoning_trace,
                    rejection_reason="No available skill can perform this action and no similar D&D rules were found.",
                    alternatives=["Try a different action", "Check /help for available commands",
                                  "Describe what you're trying to accomplish"]
                )

        chosen_skill = applicable_skills[0]
        reasoning_trace.append(
            f"Chose skill: {chosen_skill.skill_name} (confidence: {chosen_skill.confidence:.2f})"
        )

        # STEP 3: Extract Parameters
        reasoning_trace.append("Step 3: Extracting parameters from conversation...")

        extracted_params = self.param_extractor.extract_from_conversation(
            conversation_history=conversation_history,
            current_message=user_message,
            action_type=initial_intent.action_type,
            context=context,
            previously_extracted=conv_state.extracted_parameters,
            pending_question=conv_state.pending_question
        )
        reasoning_trace.append(f"Extracted parameters: {list(extracted_params.keys())}")

        if conv_state.pending_question:
            param = conv_state.pending_question.get('parameter')
            if param and param in extracted_params:
                print(f"[Reasoning] Cleared pending question for '{param}'")
                conv_state.pending_question = None

        # STEP 3.5: Dynamic Requirements for Character Creation
        missing_requirements = None
        if initial_intent.action_type == ActionType.CHARACTER_CREATION:
            reasoning_trace.append("Step 3.5: Querying RAG for dynamic character creation requirements...")
            try:
                from agent.character_requirements_rag import CharacterRequirementsRAG
                char_rag = CharacterRequirementsRAG(self.rag_query)
                missing_requirements = char_rag.get_missing_requirements(extracted_params)

                if missing_requirements:
                    missing_params = [req.parameter for req in missing_requirements]
                    reasoning_trace.append(f"RAG-determined missing params: {missing_params}")
                else:
                    missing_params = []
                    reasoning_trace.append("RAG: All required parameters collected")
            except Exception as e:
                print(f"[Reasoning] RAG character requirements failed: {e}, falling back to skill params")
                missing_params = [
                    param for param in chosen_skill.required_params
                    if param not in extracted_params
                ]
        else:
            missing_params = [
                param for param in chosen_skill.required_params
                if param not in extracted_params
            ]

        if missing_params:
            reasoning_trace.append(f"Missing required parameters: {missing_params}")

        # STEP 4: Validate Feasibility
        if not missing_params:
            reasoning_trace.append("Step 4: All parameters present, validating feasibility...")

            validation = self.validator.validate_action(
                intent=initial_intent,
                extracted_params=extracted_params,
                context=context
            )

            if not validation.is_valid:
                reasoning_trace.append(f"Validation failed: {validation.reason}")
                return ReasoningCycleResult(
                    decision='reject',
                    confidence=1.0,
                    reasoning_trace=reasoning_trace,
                    rejection_reason=validation.reason,
                    alternatives=validation.suggestions,
                    rule_references=[validation.rule_reference] if validation.rule_reference else []
                )

            reasoning_trace.append("All parameters present and action is feasible")
            return ReasoningCycleResult(
                decision='execute',
                confidence=0.95,
                reasoning_trace=reasoning_trace,
                final_intent=initial_intent,
                extracted_params=extracted_params
            )

        # STEP 5: Need Clarification
        reasoning_trace.append(f"Step 5: Need clarification for: {missing_params[0]}")

        conv_state.pending_intent = initial_intent
        conv_state.awaiting_parameters = missing_params
        conv_state.extracted_parameters = extracted_params

        context_with_params = {**context, 'extracted_parameters': extracted_params}

        requirement_details = None
        if initial_intent.action_type == ActionType.CHARACTER_CREATION and missing_requirements:
            for req in missing_requirements:
                if req.parameter == missing_params[0]:
                    requirement_details = req
                    context_with_params['requirement'] = {
                        'description': req.description,
                        'rule_reference': req.rule_reference,
                        'depends_on': req.depends_on
                    }
                    break

        question, suggestions = generate_question_with_rag(
            param_name=missing_params[0],
            action_type=initial_intent.action_type,
            requirements=requirements,
            context=context_with_params,
            rag_query=self.rag_query,
            requirement_details=requirement_details
        )

        if suggestions:
            question_context = {
                "parameter": missing_params[0],
                "question_type": "multiple_choice",
                "options": [
                    {
                        "label": sugg,
                        "keywords": extract_option_keywords(sugg),
                        "value": normalize_option_value(sugg, missing_params[0]),
                        "number": i + 1
                    }
                    for i, sugg in enumerate(suggestions)
                ]
            }
            conv_state.pending_question = question_context
            print(f"[Reasoning] Stored question context for '{missing_params[0]}' with {len(suggestions)} options")
        else:
            conv_state.pending_question = None

        return ReasoningCycleResult(
            decision='clarify',
            confidence=0.7,
            reasoning_trace=reasoning_trace,
            clarification_question=question,
            suggestions=suggestions
        )

    def adjudicate_improvised_action(self, action: str, context: Dict) -> ImprovisedMechanics:
        """Delegate to improvised action module."""
        return adjudicate_improvised_action(action, context, self.rag_query)
