#!/usr/bin/env python3
"""
Integration Test - Learning Workflow System

Tests the complete integrated system:
1. Intent Detection (regex + LLM)
2. RAG Intent Lookup
3. Pattern Generation
4. Learning Workflow
5. Web Server Integration

Usage:
    export OPENAI_API_KEY=your_key
    python scripts/test_integration.py
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from ui.game_state import GameState
from agent.dm_agent_v2 import DMAgentV2
from agent.command_agent import CommandAgent
from ui.workflow_init import initialize_workflow
from agent.intent_agent import ActionType


def print_section(title: str):
    """Print section header"""
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print('=' * 70)


def print_result(test_name: str, passed: bool, message: str = ""):
    """Print test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"  {status} - {test_name}")
    if message:
        print(f"       {message}")


def test_workflow_initialization():
    """Test 1: Workflow system initializes correctly"""
    print_section("Test 1: Workflow Initialization")

    try:
        game_state = GameState()
        dm_agent = DMAgentV2()
        command_agent = CommandAgent(game_state)

        workflow = initialize_workflow(
            game_state=game_state,
            command_agent=command_agent,
            dm_agent=dm_agent,
            enable_learning=True,
            auto_approve_patterns=False
        )

        if workflow is None:
            print_result("Workflow initialization", False, "Workflow returned None")
            return None, None, None, None

        print_result("Workflow initialization", True)
        return workflow, game_state, dm_agent, command_agent

    except Exception as e:
        print_result("Workflow initialization", False, str(e))
        import traceback
        traceback.print_exc()
        return None, None, None, None


def test_intent_detection(workflow):
    """Test 2: Intent detection works"""
    print_section("Test 2: Intent Detection")

    test_cases = [
        ("I attack the goblin with my sword", ActionType.ATTACK, "regex"),
        ("I cast Fireball at the orcs", ActionType.SPELL_CAST, "regex"),
        ("I try to sneak past the guard", ActionType.SKILL_CHECK, "regex or llm"),
        ("I want to check for traps", ActionType.SKILL_CHECK, "llm"),
        ("I look around the room", ActionType.UNCLEAR, "any"),
    ]

    passed = 0
    failed = 0

    for message, expected_action, expected_method in test_cases:
        try:
            intent = workflow.intent_agent.detect(message)

            # Check action type
            action_match = intent.action_type == expected_action
            method_match = expected_method == "any" or expected_method in intent.detection_method

            if action_match and method_match:
                print_result(
                    f'"{message[:40]}..."',
                    True,
                    f"{intent.action_type.value} (conf: {intent.confidence:.2f}, method: {intent.detection_method})"
                )
                passed += 1
            else:
                print_result(
                    f'"{message[:40]}..."',
                    False,
                    f"Expected {expected_action.value}, got {intent.action_type.value}"
                )
                failed += 1

        except Exception as e:
            print_result(f'"{message[:40]}..."', False, str(e))
            failed += 1

    print(f"\n  Summary: {passed} passed, {failed} failed")
    return passed, failed


def test_workflow_execution(workflow, game_state):
    """Test 3: Full workflow execution (Intent → Mechanics → Narrative)"""
    print_section("Test 3: Workflow Execution")

    test_messages = [
        "I attack the goblin",
        "I try to persuade the guard",
        "What do I see?",
    ]

    passed = 0
    failed = 0

    for message in test_messages:
        try:
            print(f"\n  Testing: \"{message}\"")

            # Process message
            result = workflow.process_message(
                user_message=message,
                session_id='test_session',
                message_history=[]
            )

            if result.success:
                print_result(
                    "Workflow execution",
                    True,
                    f"Completed in {result.metrics['total']:.2f}s"
                )

                # Check phases completed
                print(f"       Intent:    {result.metrics['intent_detection']:.2f}s ({result.intent.detection_method})")
                print(f"       Mechanics: {result.metrics['mechanics_execution']:.2f}s")
                print(f"       Narrative: {result.metrics['narrative_generation']:.2f}s")

                if result.mechanics_summary:
                    print(f"       Mechanics: {result.mechanics_summary[:60]}...")

                passed += 1
            else:
                print_result("Workflow execution", False, result.error)
                failed += 1

        except Exception as e:
            print_result("Workflow execution", False, str(e))
            failed += 1

    print(f"\n  Summary: {passed} passed, {failed} failed")
    return passed, failed


def test_rag_intent_fallback(workflow):
    """Test 4: RAG intent lookup for unclear intents"""
    print_section("Test 4: RAG Intent Fallback")

    # These messages should trigger RAG lookup
    unclear_messages = [
        "I try to grapple the bandit",
        "I attempt to shove the guard",
        "I want to disarm the knight",
    ]

    passed = 0
    failed = 0

    for message in unclear_messages:
        try:
            print(f"\n  Testing RAG for: \"{message}\"")

            # Detect intent (may trigger RAG)
            from game.workflow import WorkflowContext
            context = WorkflowContext(user_message=message, session_id='test')

            intent = workflow._detect_intent(message, context)

            # Check if confidence improved
            if intent.confidence >= 0.7:
                print_result(
                    "RAG clarification",
                    True,
                    f"Intent: {intent.action_type.value} (conf: {intent.confidence:.2f}, method: {intent.detection_method})"
                )
                passed += 1
            else:
                print_result(
                    "RAG clarification",
                    False,
                    f"Low confidence: {intent.confidence:.2f}"
                )
                failed += 1

        except Exception as e:
            print_result("RAG clarification", False, str(e))
            failed += 1

    print(f"\n  Summary: {passed} passed, {failed} failed")
    return passed, failed


def test_pattern_learning(workflow):
    """Test 5: Pattern generation and storage"""
    print_section("Test 5: Pattern Learning")

    try:
        # Get initial pattern count
        initial_active = len(workflow.pattern_gen.get_active_patterns())
        initial_pending = len(workflow.pattern_gen.get_pending_patterns())

        print(f"  Initial state:")
        print(f"    Active patterns:  {initial_active}")
        print(f"    Pending patterns: {initial_pending}")

        # Manually trigger pattern learning with a test proposal
        test_proposal = {
            'name': 'test_grapple_pattern',
            'action_type': 'skill_check',
            'trigger_phrases': ['grapple', 'grab'],
            'example_message': 'I try to grapple the guard',
            'detected_skill': 'athletics',
            'rule_references': [
                {
                    'source': 'PHB',
                    'section': 'Grappling',
                    'text': 'When you want to grab a creature or wrestle with it, you can use the Attack action to make a special melee attack, a grapple.'
                }
            ],
            'confidence': 0.85,
            'mechanics_summary': 'Contested Athletics check',
            'proposed_regex': r'\b(grapple|grab)\s+',
            'requires_validation': True,
            'status': 'pending_review'
        }

        print(f"\n  Generating test pattern...")
        pattern = workflow.pattern_gen.generate_pattern(
            proposal=test_proposal,
            auto_approve=False
        )

        if pattern:
            print_result("Pattern generation", True, f"Generated: {pattern.name}")
            print(f"       Status: {pattern.status}")
            print(f"       Confidence: {pattern.confidence:.2f}")
            print(f"       Regex patterns: {len(pattern.regex_patterns)}")

            # Check if stored
            new_pending = len(workflow.pattern_gen.get_pending_patterns())
            if new_pending > initial_pending:
                print_result("Pattern storage", True, "Pattern stored in database")
            else:
                print_result("Pattern storage", False, "Pattern not found in database")

            return True
        else:
            print_result("Pattern generation", False, "Pattern validation failed")
            return False

    except Exception as e:
        print_result("Pattern learning", False, str(e))
        import traceback
        traceback.print_exc()
        return False


def test_learning_stats(workflow):
    """Test 6: Learning statistics"""
    print_section("Test 6: Learning Statistics")

    try:
        stats = workflow.get_learning_stats()

        print(f"  Learning stats retrieved:")
        print(f"    Active patterns:   {stats['active_patterns']}")
        print(f"    Pending patterns:  {stats['pending_patterns']}")
        print(f"    Total activations: {stats['total_activations']}")
        print(f"    Success rate:      {stats['success_rate']:.1%}")
        print(f"    Learning enabled:  {stats['learning_enabled']}")

        print_result("Learning statistics", True)
        return True

    except Exception as e:
        print_result("Learning statistics", False, str(e))
        return False


def test_performance(workflow):
    """Test 7: Performance benchmarks"""
    print_section("Test 7: Performance Benchmarks")

    test_cases = [
        ("I attack the goblin", "regex", 0.2),  # Should be <200ms
        ("I cast Magic Missile", "regex", 0.2),
        ("I try to persuade the guard", "llm", 1.0),  # May use LLM
    ]

    passed = 0
    failed = 0

    for message, expected_method, max_time in test_cases:
        try:
            import time
            start = time.time()

            intent = workflow.intent_agent.detect(message)

            elapsed = time.time() - start

            within_time = elapsed <= max_time
            print_result(
                f'"{message[:30]}..." ({elapsed*1000:.0f}ms)',
                within_time,
                f"Method: {intent.detection_method}"
            )

            if within_time:
                passed += 1
            else:
                failed += 1

        except Exception as e:
            print_result(f'"{message[:30]}..."', False, str(e))
            failed += 1

    print(f"\n  Summary: {passed} passed, {failed} failed")
    return passed, failed


def main():
    """Run all integration tests"""
    print("\n" + "=" * 70)
    print("  🧪 Learning Workflow System - Integration Tests")
    print("=" * 70)

    # Check API key
    if not os.getenv('OPENAI_API_KEY'):
        print("\n❌ OPENAI_API_KEY not set!")
        print("   Set it with: export OPENAI_API_KEY=your_key")
        sys.exit(1)

    total_passed = 0
    total_failed = 0

    # Test 1: Initialization
    workflow, game_state, dm_agent, command_agent = test_workflow_initialization()

    if not workflow:
        print("\n❌ Workflow initialization failed. Cannot proceed with tests.")
        sys.exit(1)

    total_passed += 1

    # Test 2: Intent Detection
    passed, failed = test_intent_detection(workflow)
    total_passed += passed
    total_failed += failed

    # Test 3: Workflow Execution
    passed, failed = test_workflow_execution(workflow, game_state)
    total_passed += passed
    total_failed += failed

    # Test 4: RAG Fallback
    passed, failed = test_rag_intent_fallback(workflow)
    total_passed += passed
    total_failed += failed

    # Test 5: Pattern Learning
    if test_pattern_learning(workflow):
        total_passed += 1
    else:
        total_failed += 1

    # Test 6: Learning Stats
    if test_learning_stats(workflow):
        total_passed += 1
    else:
        total_failed += 1

    # Test 7: Performance
    passed, failed = test_performance(workflow)
    total_passed += passed
    total_failed += failed

    # Final Report
    print_section("Test Summary")
    print(f"  Total Passed: {total_passed}")
    print(f"  Total Failed: {total_failed}")

    if total_failed == 0:
        print("\n  ✅ All tests passed! System is ready for deployment.")
        success_rate = 100.0
    else:
        success_rate = (total_passed / (total_passed + total_failed)) * 100
        print(f"\n  ⚠️  {total_failed} test(s) failed. Success rate: {success_rate:.1f}%")

        if success_rate >= 80:
            print("     System is mostly functional but needs attention.")
        else:
            print("     ❌ System has significant issues. Review failures above.")

    print("=" * 70 + "\n")

    # Cleanup
    if workflow and hasattr(workflow, 'executor'):
        workflow.executor.shutdown(wait=True)

    sys.exit(0 if total_failed == 0 else 1)


if __name__ == '__main__':
    main()
