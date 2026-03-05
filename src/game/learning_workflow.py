"""
Self-Learning Workflow - Intent Pattern Learning System

Extends the base workflow with 3-agent learning system:
1. Intent Agent: Fast pattern matching
2. RAG Intent Agent: Search D&D rules for unclear intents
3. Pattern Generator Agent: Learn new patterns from discoveries

This creates a self-improving system that gets faster and smarter over time.

Flow:
┌──────────────────────────────────────────────────────────┐
│ Layer 1: Intent Agent (Regex) - <1ms                    │
│   ↓ (no match or low confidence)                        │
│ Layer 2: Intent Agent (LLM) - 50-200ms                  │
│   ↓ (confidence < 0.7)                                  │
│ Layer 3: RAG Intent Agent (Rules) - 200-500ms           │
│   ↓ (found in manual)                                   │
│ Layer 4: Pattern Generator (Learn) - ASYNC              │
│   → Stores pattern for future use                       │
└──────────────────────────────────────────────────────────┘
"""

import asyncio
import time
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor

from game.workflow import WorkflowOrchestrator, WorkflowContext, WorkflowResult
from agent.intent_agent import IntentAgent, Intent
from agent.rag_intent_agent import RAGIntentAgent
from agent.pattern_generator_agent import PatternGeneratorAgent, LearnedPattern


class LearningWorkflowOrchestrator(WorkflowOrchestrator):
    """
    Extended workflow with self-learning capabilities.

    Adds RAG lookup and pattern generation to the base workflow.
    """

    def __init__(
        self,
        intent_agent: IntentAgent,
        rag_intent_agent: RAGIntentAgent,
        pattern_generator_agent: PatternGeneratorAgent,
        command_agent,
        dm_agent,
        game_state,
        enable_learning: bool = True,
        auto_approve_patterns: bool = False,
        spatial_agent=None,
        spatial_translator=None,
        reasoning_agent=None
    ):
        """
        Initialize Learning Workflow Orchestrator.

        Args:
            intent_agent: Base intent agent
            rag_intent_agent: RAG-based intent lookup
            pattern_generator_agent: Pattern learning agent
            command_agent: Mechanics agent
            dm_agent: Narrative agent
            game_state: Game state
            enable_learning: If True, patterns are learned
            auto_approve_patterns: If True, patterns activate immediately
            spatial_agent: Optional spatial agent for position tracking
            spatial_translator: Optional translator for natural language → coordinates
            reasoning_agent: Optional reasoning agent for iterative clarification
        """
        super().__init__(
            intent_agent=intent_agent,
            command_agent=command_agent,
            dm_agent=dm_agent,
            game_state=game_state,
            spatial_agent=spatial_agent,
            spatial_translator=spatial_translator,
            reasoning_agent=reasoning_agent
        )

        self.rag_agent = rag_intent_agent
        self.pattern_gen = pattern_generator_agent
        self.enable_learning = enable_learning
        self.auto_approve = auto_approve_patterns

        # Thread pool for async pattern generation
        self.executor = ThreadPoolExecutor(max_workers=2)

        # Load active learned patterns into Intent Agent
        self._load_learned_patterns()

    def _load_learned_patterns(self):
        """Load active learned patterns into Intent Agent"""
        learned_patterns = self.pattern_gen.get_active_patterns()

        print(f"[Learning] Loaded {len(learned_patterns)} learned patterns")

        # Add patterns to Intent Agent
        # (This would require extending IntentAgent to accept dynamic patterns)
        # For now, we'll check them separately

        self.learned_patterns = learned_patterns

    def _detect_intent(
        self,
        user_message: str,
        context: WorkflowContext,
        message_history: Optional[List[Dict]] = None
    ) -> Intent:
        """
        Enhanced intent detection with RAG fallback and learning.

        Layers:
        1. Learned patterns (fast)
        2. Base intent detection (agentic LLM with conversation history)
        3. RAG lookup if uncertain
        4. Learn new pattern (async)
        """
        # Layer 1: Check learned patterns first
        intent = self._check_learned_patterns(user_message, context)
        if intent and intent.confidence >= 0.9:
            print(f"[Learning] Matched learned pattern: {intent.action_type.value}")
            return intent

        # Layer 2: Base intent detection with message history for semantic understanding
        intent = super()._detect_intent(user_message, context, message_history)

        # Layer 3: RAG lookup if uncertain
        if self.rag_agent.should_trigger_rag(intent):
            print(f"[Learning] Intent uncertain (conf: {intent.confidence:.2f}), triggering RAG lookup...")

            rag_result = self.rag_agent.lookup_intent(
                original_message=user_message,
                uncertain_intent=intent,
                context={'in_combat': self.game_state.in_combat}
            )

            # Use RAG-clarified intent
            if rag_result.intent and rag_result.confidence > intent.confidence:
                print(f"[Learning] RAG clarified intent: {rag_result.intent.action_type.value} "
                      f"(conf: {rag_result.confidence:.2f})")
                intent = rag_result.intent

                # Layer 4: Learn pattern (async, non-blocking)
                if self.enable_learning and rag_result.suggests_new_pattern:
                    self._learn_pattern_async(rag_result.pattern_proposal)

        return intent

    def _check_learned_patterns(
        self,
        user_message: str,
        context: WorkflowContext
    ) -> Optional[Intent]:
        """Check if message matches any learned patterns"""
        import re

        message_lower = user_message.lower()

        for pattern in self.learned_patterns:
            # Try each regex pattern
            for regex_pattern in pattern.regex_patterns:
                try:
                    pattern_str = regex_pattern
                    if pattern_str.startswith("r'"):
                        pattern_str = pattern_str[2:-1]

                    match = re.search(pattern_str, message_lower)
                    if match:
                        # Pattern matched!
                        target = match.group(match.lastindex) if match.lastindex else None

                        # Log usage
                        self.pattern_gen.log_pattern_usage(
                            pattern_id=pattern.pattern_id,
                            user_message=user_message,
                            matched=True,
                            executed=False  # Will be set later
                        )

                        return Intent(
                            action_type=pattern.action_type,
                            confidence=pattern.confidence,
                            target=target,
                            skill=pattern.skill,
                            original_message=user_message,
                            detection_method='learned_pattern'
                        )

                except re.error:
                    continue

        return None

    def _learn_pattern_async(self, pattern_proposal: Dict):
        """
        Learn a new pattern asynchronously (non-blocking).

        This runs in the background and doesn't delay the player's response.
        """
        print(f"[Learning] Starting async pattern learning: {pattern_proposal.get('name')}")

        # Submit to thread pool
        future = self.executor.submit(
            self._learn_pattern_sync,
            pattern_proposal
        )

        # Don't wait for result - let it complete in background
        future.add_done_callback(self._on_pattern_learned)

    def _learn_pattern_sync(self, pattern_proposal: Dict) -> Optional[LearnedPattern]:
        """Synchronous pattern learning (runs in background thread)"""
        try:
            pattern = self.pattern_gen.generate_pattern(
                proposal=pattern_proposal,
                auto_approve=self.auto_approve
            )

            if pattern:
                print(f"[Learning] Pattern generated: {pattern.name} ({pattern.status})")

                # Reload patterns if auto-approved
                if pattern.status == 'active':
                    self._load_learned_patterns()

            return pattern

        except Exception as e:
            print(f"[Learning] Pattern generation failed: {e}")
            return None

    def _on_pattern_learned(self, future):
        """Callback when pattern learning completes"""
        try:
            pattern = future.result()
            if pattern:
                if pattern.status == 'pending':
                    print(f"[Learning] Pattern '{pattern.name}' awaiting approval")
                    print(f"[Learning] Review at /admin/patterns or approve via pattern_gen.approve_pattern('{pattern.pattern_id}')")
                elif pattern.status == 'active':
                    print(f"[Learning] Pattern '{pattern.name}' activated and ready to use!")
        except Exception as e:
            print(f"[Learning] Pattern callback error: {e}")

    def get_learning_stats(self) -> Dict:
        """Get statistics about learned patterns"""
        active = self.pattern_gen.get_active_patterns()
        pending = self.pattern_gen.get_pending_patterns()

        total_activations = sum(p.activation_count for p in active if hasattr(p, 'activation_count'))
        total_successes = sum(p.success_count for p in active if hasattr(p, 'success_count'))

        return {
            'active_patterns': len(active),
            'pending_patterns': len(pending),
            'total_activations': total_activations,
            'total_successes': total_successes,
            'success_rate': total_successes / max(total_activations, 1),
            'learning_enabled': self.enable_learning,
            'auto_approve': self.auto_approve
        }
