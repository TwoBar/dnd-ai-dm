"""
Workflow context and result types.

Shared data structures passed through all workflow phases.
"""
import time
from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


class WorkflowState(Enum):
    """States in the workflow state machine"""
    IDLE = "idle"
    DETECTING_INTENT = "detecting_intent"
    EXECUTING_MECHANICS = "executing_mechanics"
    GENERATING_NARRATIVE = "generating_narrative"
    BROADCASTING = "broadcasting"
    ERROR = "error"


@dataclass
class WorkflowContext:
    """Shared context across all workflow stages"""
    # Input
    user_message: str
    session_id: str

    # Detected intent
    intent: Optional[Any] = None

    # Spatial context
    spatial_context: Optional[Dict] = None
    spatial_translation: Optional[Dict] = None
    map_state: Optional[Dict] = None

    # Mechanics results
    mechanics_actions: List[Dict] = field(default_factory=list)
    dice_rolls: List[Dict] = field(default_factory=list)
    game_state_changes: Dict = field(default_factory=dict)

    # Narrative
    dm_response: str = ""

    # Reasoning
    reasoning_trace: List[str] = field(default_factory=list)

    # Timing
    started_at: float = field(default_factory=time.time)
    intent_detected_at: Optional[float] = None
    spatial_translated_at: Optional[float] = None
    mechanics_completed_at: Optional[float] = None
    narrative_completed_at: Optional[float] = None

    # Metadata
    workflow_id: str = field(default_factory=lambda: f"wf_{int(time.time()*1000)}")
    current_state: WorkflowState = WorkflowState.IDLE

    def add_timing_marker(self, state: WorkflowState):
        """Record timing for a workflow state"""
        now = time.time()
        if state == WorkflowState.DETECTING_INTENT:
            self.intent_detected_at = now
        elif state == WorkflowState.EXECUTING_MECHANICS:
            self.mechanics_completed_at = now
        elif state == WorkflowState.GENERATING_NARRATIVE:
            self.narrative_completed_at = now

    def get_total_latency_ms(self) -> float:
        """Get total workflow latency in milliseconds"""
        if self.narrative_completed_at:
            return (self.narrative_completed_at - self.started_at) * 1000
        return (time.time() - self.started_at) * 1000

    def get_phase_latencies_ms(self) -> Dict[str, float]:
        """Get latency for each phase"""
        latencies = {}
        if self.intent_detected_at:
            latencies['intent_detection'] = (self.intent_detected_at - self.started_at) * 1000
        if self.mechanics_completed_at and self.intent_detected_at:
            latencies['mechanics_execution'] = (self.mechanics_completed_at - self.intent_detected_at) * 1000
        if self.narrative_completed_at and self.mechanics_completed_at:
            latencies['narrative_generation'] = (self.narrative_completed_at - self.mechanics_completed_at) * 1000
        latencies['total'] = self.get_total_latency_ms()
        return latencies


@dataclass
class WorkflowResult:
    """Result of workflow execution"""
    success: bool
    dm_response: str
    intent: Optional[Any]
    mechanics_summary: str
    game_state_changes: Dict
    context: WorkflowContext
    error: Optional[str] = None
    map_state: Optional[Dict] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        result = {
            'success': self.success,
            'dm_response': self.dm_response,
            'intent': self.intent.to_dict() if self.intent else None,
            'mechanics_summary': self.mechanics_summary,
            'game_state_changes': self.game_state_changes,
            'workflow_id': self.context.workflow_id,
            'latencies_ms': self.context.get_phase_latencies_ms(),
            'error': self.error
        }
        if self.map_state:
            result['map_state'] = self.map_state
        return result
