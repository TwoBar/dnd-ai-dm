"""
Reasoning Types - Dataclasses for the reasoning system

Shared types used by the reasoning agent and related components.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from agent.intent_agent import Intent
from agent.rag_intent_agent import RuleReference


@dataclass
class ReasoningCycleResult:
    """
    Result of one reasoning cycle.

    The reasoning agent returns this to indicate what decision was made
    and what the workflow should do next.
    """
    decision: str  # 'execute', 'clarify', 'reject'
    confidence: float
    reasoning_trace: List[str] = field(default_factory=list)

    # If decision == 'clarify':
    clarification_question: Optional[str] = None
    suggestions: List[str] = field(default_factory=list)
    is_learning: bool = False  # True if this is a learning clarification

    # If decision == 'reject':
    rejection_reason: Optional[str] = None
    alternatives: List[str] = field(default_factory=list)
    rule_references: List[RuleReference] = field(default_factory=list)

    # If decision == 'execute':
    final_intent: Optional[Intent] = None
    extracted_params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return {
            'decision': self.decision,
            'confidence': self.confidence,
            'reasoning_trace': self.reasoning_trace,
            'clarification_question': self.clarification_question,
            'suggestions': self.suggestions,
            'is_learning': self.is_learning,
            'rejection_reason': self.rejection_reason,
            'alternatives': self.alternatives,
            'has_rule_references': bool(self.rule_references),
            'extracted_params': self.extracted_params
        }
