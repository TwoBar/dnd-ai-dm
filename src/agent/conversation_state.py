"""
Conversation State Manager - Track iterative reasoning state across conversation turns

Manages conversation state for multi-turn parameter collection and reasoning.
Each session has its own conversation state that persists across turns.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any

from agent.intent_agent import Intent


@dataclass
class ConversationState:
    """
    Tracks iterative reasoning state across conversation turns.

    Stores full reasoning context so next iteration can build on
    previous understanding.
    """
    session_id: str

    # Current intent being refined
    pending_intent: Optional[Intent] = None

    # What we're waiting for from the player
    awaiting_parameters: List[str] = field(default_factory=list)

    # Parameters extracted so far (accumulates across turns)
    extracted_parameters: Dict[str, Any] = field(default_factory=dict)

    # Reasoning trace from previous cycles
    reasoning_trace: List[str] = field(default_factory=list)

    # Cached RAG results from previous cycle (for re-evaluation)
    cached_rag_results: Optional[List] = None

    # Cached applicable skills from previous cycle
    cached_applicable_skills: Optional[List] = None

    # Pattern proposal (for learning loop)
    pending_pattern_proposal: Optional[Dict] = None

    # Context for pending multiple-choice question
    # Stores question details and valid options for context-aware extraction
    pending_question: Optional[Dict] = None

    # Number of messages exchanged in this pending conversation
    attempt_count: int = 0

    # Max attempts before auto-clearing (prevents infinite loops)
    max_attempts: int = 3

    # When this conversation started
    started_at: datetime = field(default_factory=datetime.now)

    # Timeout (if player doesn't respond, clear state)
    timeout_seconds: int = 300  # 5 minutes

    def is_expired(self) -> bool:
        """Check if conversation has timed out or exceeded max attempts"""
        elapsed = (datetime.now() - self.started_at).seconds
        if elapsed > self.timeout_seconds:
            return True
        if self.attempt_count >= self.max_attempts:
            return True
        return False

    def increment_attempts(self):
        """Increment the attempt counter for this pending conversation."""
        self.attempt_count += 1

    def add_parameter(self, param_name: str, value: Any):
        """
        Add a parameter from player's response.

        Args:
            param_name: Name of the parameter
            value: Value provided by player
        """
        self.extracted_parameters[param_name] = value

        # Remove from awaiting list if present
        if param_name in self.awaiting_parameters:
            self.awaiting_parameters.remove(param_name)

    def is_complete(self) -> bool:
        """Check if all awaited parameters are fulfilled"""
        return len(self.awaiting_parameters) == 0

    def clear(self):
        """Reset conversation state"""
        self.pending_intent = None
        self.awaiting_parameters = []
        self.extracted_parameters = {}
        self.reasoning_trace = []
        self.cached_rag_results = None
        self.cached_applicable_skills = None
        self.pending_pattern_proposal = None
        self.pending_question = None
        self.attempt_count = 0
        self.started_at = datetime.now()

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return {
            'session_id': self.session_id,
            'pending_intent': self.pending_intent.to_dict() if self.pending_intent else None,
            'awaiting_parameters': self.awaiting_parameters,
            'extracted_parameters': self.extracted_parameters,
            'reasoning_trace': self.reasoning_trace[-5:],  # Last 5 traces
            'has_pending_pattern': bool(self.pending_pattern_proposal),
            'pending_question': self.pending_question,
            'started_at': self.started_at.isoformat(),
            'is_expired': self.is_expired()
        }


class ConversationStateManager:
    """
    Manages conversation states for all sessions.

    Provides session-isolated state management for the reasoning system.
    """

    def __init__(self):
        """Initialize conversation state manager"""
        self.states: Dict[str, ConversationState] = {}

    def get_or_create(self, session_id: str) -> ConversationState:
        """
        Get conversation state for a session, creating if needed.

        Args:
            session_id: Unique session identifier

        Returns:
            ConversationState for this session
        """
        if session_id not in self.states:
            self.states[session_id] = ConversationState(session_id=session_id)

        # Clean up expired state
        state = self.states[session_id]
        if state.is_expired():
            print(f"[ConversationState] Session {session_id} expired, clearing state")
            state.clear()

        return state

    def has_pending_conversation(self, session_id: str) -> bool:
        """
        Check if session has an ongoing conversation.

        Args:
            session_id: Session to check

        Returns:
            True if there's a pending conversation
        """
        if session_id not in self.states:
            return False

        state = self.states[session_id]
        return state.pending_intent is not None and not state.is_expired()

    def clear_session(self, session_id: str):
        """
        Clear conversation state for a session.

        Args:
            session_id: Session to clear
        """
        if session_id in self.states:
            self.states[session_id].clear()

    def get_all_sessions(self) -> List[str]:
        """Get list of all active sessions"""
        return list(self.states.keys())

    def cleanup_expired_sessions(self):
        """Remove expired sessions from memory"""
        expired = [
            session_id
            for session_id, state in self.states.items()
            if state.is_expired() and not state.pending_intent
        ]

        for session_id in expired:
            print(f"[ConversationState] Removing expired session: {session_id}")
            del self.states[session_id]

    def get_session_summary(self, session_id: str) -> Optional[Dict]:
        """
        Get a summary of the session's conversation state.

        Args:
            session_id: Session to summarize

        Returns:
            Dictionary with session summary, or None if not found
        """
        if session_id not in self.states:
            return None

        state = self.states[session_id]
        return state.to_dict()
