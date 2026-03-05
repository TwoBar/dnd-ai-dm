"""
Learning handler for the reasoning agent.

Handles unknown actions by searching RAG for similar D&D rules
and proposing new patterns that the system can learn from.
"""
from typing import Dict, List

from agent.intent_agent import Intent
from agent.reasoning_types import ReasoningCycleResult


def handle_unknown_action(
    user_message: str,
    initial_intent: Intent,
    action_possibilities: List,
    reasoning_trace: List[str],
    session_id: str,
    rag_query,
    conversation_manager
) -> ReasoningCycleResult:
    """
    Handle unknown actions by learning from RAG.

    Triggered when no skills can handle the action but RAG found similar D&D rules.

    Process:
    1. Search RAG deeply for similar actions
    2. If found rules, propose new pattern
    3. Ask user to confirm interpretation
    4. If confirmed, learn pattern for future use
    """
    reasoning_trace.append("Unknown action, searching RAG for similar mechanics...")

    similar_rules = rag_query.entity_manager.search_rules(
        query=user_message
    )[:10]

    if not similar_rules:
        reasoning_trace.append("No similar rules found in RAG")
        return ReasoningCycleResult(
            decision='reject',
            confidence=1.0,
            reasoning_trace=reasoning_trace,
            rejection_reason="I don't recognize this action and couldn't find similar rules in the D&D manuals.",
            alternatives=[
                "Try describing the action differently",
                "Use /help to see available actions",
                "Describe what you're trying to accomplish"
            ]
        )

    reasoning_trace.append(f"Found {len(similar_rules)} similar rules in RAG")

    top_rules = similar_rules[:3]

    pattern_proposal = _generate_pattern_proposal(
        user_message=user_message,
        initial_intent=initial_intent,
        rag_rules=top_rules
    )

    reasoning_trace.append(f"Proposed new pattern: {pattern_proposal['name']}")

    question = _format_learning_clarification(
        user_message=user_message,
        pattern_proposal=pattern_proposal,
        rag_rules=top_rules
    )

    conv_state = conversation_manager.get_or_create(session_id)
    conv_state.pending_pattern_proposal = pattern_proposal

    return ReasoningCycleResult(
        decision='clarify',
        confidence=0.5,
        reasoning_trace=reasoning_trace,
        clarification_question=question,
        suggestions=["Yes, that's what I mean", "No, let me rephrase"],
        is_learning=True
    )


def _generate_pattern_proposal(
    user_message: str,
    initial_intent: Intent,
    rag_rules: List
) -> Dict:
    """Generate a pattern proposal based on RAG rules."""
    mechanics_summary = "\n".join([
        rule.content[:200]
        for rule in rag_rules
    ])

    return {
        'name': f"{initial_intent.action_type.value}_learned",
        'action_type': initial_intent.action_type.value,
        'trigger_phrases': [user_message.lower()[:50]],
        'example_message': user_message,
        'rule_references': [
            {
                'source': getattr(rule, 'metadata', {}).get('source', 'SRD'),
                'section': rule.name,
                'text': rule.content
            }
            for rule in rag_rules
        ],
        'mechanics_description': mechanics_summary,
        'confidence': 0.7,
        'status': 'pending',
        'requires_validation': True
    }


def _format_learning_clarification(
    user_message: str,
    pattern_proposal: Dict,
    rag_rules: List
) -> str:
    """Format a clarification question for learning."""
    question = f"I don't have a built-in action for '{user_message}', but I found these similar D&D mechanics:\n\n"

    for i, rule in enumerate(rag_rules[:2], 1):
        source = getattr(rule, 'metadata', {}).get('source', 'SRD')
        question += f"{i}. **{rule.name}** ({source})\n"
        snippet = rule.content[:150]
        question += f"   {snippet}...\n\n"

    question += "Is this what you're trying to do? If yes, I'll learn this action for next time!"

    return question
