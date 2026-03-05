"""
Workflow Factory - Creates workflow orchestrators with proper wiring.

Replaces the initialize_workflow() god-function from ui/workflow_init.py.
"""
import os
from typing import Optional

from game.learning_workflow import LearningWorkflowOrchestrator
from factory.agent_factory import (
    create_intent_agent,
    create_entity_manager,
    create_rag_intent_agent,
    create_pattern_generator,
    create_reasoning_agent,
)


def create_learning_workflow(
    game_state,
    command_agent,
    dm_agent,
    enable_learning: bool = True,
    auto_approve_patterns: bool = False,
    openai_api_key: Optional[str] = None,
    spatial_agent=None,
    spatial_translator=None
) -> Optional[LearningWorkflowOrchestrator]:
    """
    Create a LearningWorkflowOrchestrator with all agents properly wired.

    This replaces the initialize_workflow() function from ui/workflow_init.py.

    Args:
        game_state: GameState instance
        command_agent: CommandAgent instance
        dm_agent: DMAgent instance
        enable_learning: Enable pattern learning
        auto_approve_patterns: Auto-approve learned patterns
        openai_api_key: OpenAI API key (reads from env if not provided)
        spatial_agent: Optional spatial agent
        spatial_translator: Optional spatial translator

    Returns:
        LearningWorkflowOrchestrator if successful, None if disabled or failed
    """
    use_workflow = os.getenv('USE_WORKFLOW_ORCHESTRATOR', 'true').lower() == 'true'
    if not use_workflow:
        print("[Workflow] Workflow orchestrator disabled (USE_WORKFLOW_ORCHESTRATOR=false)")
        return None

    openai_api_key = openai_api_key or os.getenv('OPENAI_API_KEY')

    if not openai_api_key:
        print("[Workflow] Warning: No OpenAI API key found. LLM fallback disabled.")

    print("\n" + "=" * 60)
    print("Initializing Learning Workflow System")
    print("=" * 60)

    try:
        # Create agents
        print("\n[1/5] Initializing Intent Detection Agent...")
        intent_agent = create_intent_agent(openai_api_key)
        print("      Intent Agent ready")

        print("\n[2/5] Initializing Entity Manager (RAG)...")
        entity_manager = create_entity_manager()
        print("      Entity Manager ready")

        print("\n[3/5] Initializing RAG Intent Agent...")
        rag_intent_agent = create_rag_intent_agent(entity_manager, openai_api_key)
        print("      RAG Intent Agent ready")

        print("\n[4/5] Initializing Pattern Generator + Reasoning System...")
        pattern_generator = create_pattern_generator()
        reasoning_agent = create_reasoning_agent(
            rag_intent_agent, entity_manager, pattern_generator, openai_api_key
        )
        print("      Reasoning Agent ready (5-step iterative loop)")

        # Create orchestrator
        print("\n[5/5] Initializing Learning Workflow Orchestrator...")
        workflow = LearningWorkflowOrchestrator(
            intent_agent=intent_agent,
            rag_intent_agent=rag_intent_agent,
            pattern_generator_agent=pattern_generator,
            command_agent=command_agent,
            dm_agent=dm_agent,
            game_state=game_state,
            enable_learning=enable_learning,
            auto_approve_patterns=auto_approve_patterns,
            spatial_agent=spatial_agent,
            spatial_translator=spatial_translator,
            reasoning_agent=reasoning_agent
        )

        features = []
        if spatial_agent and spatial_translator:
            features.append("spatial integration")
        features.append("iterative reasoning")
        print(f"      Orchestrator ready (with {', '.join(features)})")

        # Print stats
        stats = workflow.get_learning_stats()
        print(f"\n  Active patterns: {stats['active_patterns']}, "
              f"Pending: {stats['pending_patterns']}, "
              f"Learning: {'on' if stats['learning_enabled'] else 'off'}")
        print("=" * 60 + "\n")

        return workflow

    except Exception as e:
        print(f"\nError initializing workflow: {e}")
        print("   Falling back to legacy flow")
        import traceback
        traceback.print_exc()
        return None


def get_workflow_stats(workflow) -> dict:
    """Get statistics about the workflow system."""
    if not workflow:
        return {'enabled': False, 'message': 'Workflow orchestrator not initialized'}

    stats = workflow.get_learning_stats()
    return {
        'enabled': True,
        'active_patterns': stats['active_patterns'],
        'pending_patterns': stats['pending_patterns'],
        'total_activations': stats['total_activations'],
        'total_successes': stats['total_successes'],
        'success_rate': stats['success_rate'],
        'learning_enabled': stats['learning_enabled'],
        'auto_approve': stats['auto_approve']
    }


def shutdown_workflow(workflow):
    """Gracefully shutdown the workflow system."""
    if not workflow:
        return

    print("\n[Workflow] Shutting down learning workflow system...")
    try:
        if hasattr(workflow, 'executor'):
            workflow.executor.shutdown(wait=True)
            print("[Workflow] Thread pool shutdown complete")
        print("[Workflow] Shutdown complete")
    except Exception as e:
        print(f"[Workflow] Error during shutdown: {e}")
