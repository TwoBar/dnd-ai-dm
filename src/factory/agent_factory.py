"""
Agent Factory - Creates all agents with proper dependency wiring.

Replaces the initialization logic from ui/workflow_init.py.
"""
import os
from pathlib import Path
from typing import Optional

from agent.intent_agent import IntentAgent
from agent.rag_intent_agent import RAGIntentAgent
from agent.pattern_generator_agent import PatternGeneratorAgent
from agent.command import CommandAgent
from agent.dm_agent_v2 import DMAgentV2
from data.entity_manager import EntityManager

from agent.rag_query_service import RAGQueryService
from agent.skill_query_service import SkillQueryService
from agent.parameter_extractor import ParameterExtractor
from agent.feasibility_validator import FeasibilityValidator
from agent.conversation_state import ConversationStateManager
from agent.reasoning import ReasoningAgent


def _get_data_paths():
    """Get standard data paths."""
    base_path = Path(__file__).parent.parent.parent
    return {
        'db_path': base_path / 'data' / 'reference.db',
        'vector_db_path': base_path / 'data' / 'vector_dbs',
        'pattern_db_path': base_path / 'data' / 'learned_patterns.db',
    }


def create_intent_agent(openai_api_key: Optional[str] = None) -> IntentAgent:
    """Create an IntentAgent."""
    openai_api_key = openai_api_key or os.getenv('OPENAI_API_KEY')
    return IntentAgent(openai_api_key=openai_api_key)


def create_entity_manager() -> EntityManager:
    """Create an EntityManager with standard paths."""
    paths = _get_data_paths()
    paths['vector_db_path'].mkdir(exist_ok=True)

    if not paths['db_path'].exists():
        print(f"[Factory] Warning: Reference database not found at {paths['db_path']}")

    return EntityManager(
        db_path=paths['db_path'],
        vector_db_path=paths['vector_db_path']
    )


def create_rag_intent_agent(
    entity_manager: EntityManager,
    openai_api_key: Optional[str] = None
) -> RAGIntentAgent:
    """Create a RAGIntentAgent."""
    openai_api_key = openai_api_key or os.getenv('OPENAI_API_KEY')
    return RAGIntentAgent(
        entity_manager=entity_manager,
        openai_api_key=openai_api_key,
        confidence_threshold=0.7
    )


def create_pattern_generator() -> PatternGeneratorAgent:
    """Create a PatternGeneratorAgent."""
    paths = _get_data_paths()
    paths['pattern_db_path'].parent.mkdir(exist_ok=True)
    return PatternGeneratorAgent(database_path=str(paths['pattern_db_path']))


def create_reasoning_agent(
    rag_intent_agent: RAGIntentAgent,
    entity_manager: EntityManager,
    pattern_generator: PatternGeneratorAgent,
    openai_api_key: Optional[str] = None
) -> ReasoningAgent:
    """Create a ReasoningAgent with all sub-dependencies."""
    openai_api_key = openai_api_key or os.getenv('OPENAI_API_KEY')

    rag_query_service = RAGQueryService(
        rag_agent=rag_intent_agent,
        entity_manager=entity_manager
    )

    skill_query_service = SkillQueryService()

    param_extractor = ParameterExtractor(openai_api_key=openai_api_key)

    feasibility_validator = FeasibilityValidator(rag_query=rag_query_service)

    conversation_manager = ConversationStateManager()

    return ReasoningAgent(
        rag_query=rag_query_service,
        skill_query=skill_query_service,
        param_extractor=param_extractor,
        validator=feasibility_validator,
        conversation_manager=conversation_manager,
        pattern_generator=pattern_generator
    )


def create_command_agent(game_state, formula_service=None, spatial_agent=None) -> CommandAgent:
    """Create a CommandAgent."""
    return CommandAgent(
        game_state=game_state,
        formula_service=formula_service,
        spatial_agent=spatial_agent
    )


def create_dm_agent() -> DMAgentV2:
    """Create a DMAgentV2."""
    return DMAgentV2()
