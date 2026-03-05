#!/usr/bin/env python3
"""D&D AI Dungeon Master - Main entry point"""
import sys
from pathlib import Path

# Ensure project root is in path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from config import REFERENCE_DB_PATH, GAME_STATE_DB_PATH, VECTOR_DB_DIR, OPENAI_API_KEY, AGENT_PROVIDER
from data.sqlite_db import ReferenceDB, GameStateDB
from data.entity_manager import EntityManager


def check_setup():
    """Check if the system is properly set up"""
    issues = []

    # Check API key based on provider
    if AGENT_PROVIDER == "openai" and not OPENAI_API_KEY:
        issues.append("OPENAI_API_KEY not set in .env file (required for agent_provider=openai)")

    # Check if atomic entity database exists
    if not REFERENCE_DB_PATH.exists():
        issues.append(f"Reference database not found. Run: python scripts/bootstrap_atomic.py")

    return issues


def test_dice():
    """Test dice rolling system"""
    from game.dice import roll, d20, d6

    print("\n🎲 Testing Dice System")
    print("=" * 50)

    # Test basic rolls
    print("\nBasic rolls:")
    print(f"  2d6+3: {roll('2d6+3')}")
    print(f"  1d20: {d20()}")
    print(f"  3d6: {roll('3d6')}")

    # Test advantage/disadvantage
    print("\nAdvantage/Disadvantage:")
    print(f"  1d20 (advantage): {d20(advantage=True)}")
    print(f"  1d20 (disadvantage): {d20(disadvantage=True)}")

    # Test keep highest
    print("\nKeep highest (ability score rolling):")
    print(f"  4d6kh3: {roll('4d6kh3')}")


def chat_mode():
    """Simple chat interface with DM using V2 architecture"""
    from agent.dm_agent_v2 import DMAgentV2
    from tools.entity_tools import get_cache_stats

    print("\n💬 Chat Mode - D&D AI Dungeon Master V2")
    print("=" * 50)
    print("\n🎯 Two-Stage Retrieval Architecture:")
    print("  Stage 1: Metadata filtering (SQL)")
    print("  Stage 2: Embedding similarity (Vector DB)")
    print("\nType your messages to interact with the DM.")
    print("\nCommands:")
    print("  /quit - Exit chat")
    print("  /reset - Reset conversation")
    print("  /test - Test dice rolling")
    print("  /stats - Show cache statistics")
    print("\nStarting session...")

    try:
        dm = DMAgentV2()
        print("✅ DM initialized!")
        print("✨ DM uses tool-based retrieval (rules on-demand, not passive context)")
        print("\n" + "=" * 50)

        while True:
            try:
                user_input = input("\n🧙 You: ").strip()

                if not user_input:
                    continue

                # Handle commands
                if user_input.lower() == "/quit":
                    print("\n👋 Goodbye! Thanks for playing!")
                    # Show final stats
                    stats = get_cache_stats()
                    print("\n📊 Final Cache Statistics:")
                    for key, value in stats.items():
                        print(f"  • {key}: {value}")
                    break
                elif user_input.lower() == "/reset":
                    dm.reset_conversation()
                    print("🔄 Conversation reset!")
                    continue
                elif user_input.lower() == "/test":
                    test_dice()
                    continue
                elif user_input.lower() == "/stats":
                    stats = get_cache_stats()
                    print("\n📊 Cache Statistics:")
                    for key, value in stats.items():
                        print(f"  • {key}: {value}")
                    continue

                # Send message to DM
                response = dm.chat(user_input)

                # Print DM response
                print(f"\n🎲 DM: {response}")

                # Show context size estimate
                context_size = dm.get_context_size()
                if context_size > 1000:
                    print(f"   (Context: ~{context_size} tokens)")

            except KeyboardInterrupt:
                print("\n\n👋 Goodbye! Thanks for playing!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
                print("Type /quit to exit or continue chatting...")

    except Exception as e:
        print(f"\n❌ Failed to initialize DM: {e}")
        print("\nMake sure you've:")
        print("  1. Set OPENAI_API_KEY in .env")
        print("  2. Run: python scripts/bootstrap_atomic.py")
        print("  3. Installed dependencies: pip install -r requirements.txt")


def main():
    """Main entry point"""
    print("🎲 D&D AI Dungeon Master V2")
    print("=" * 50)

    # Check setup
    issues = check_setup()
    if issues:
        print("\n❌ Setup issues found:")
        for issue in issues:
            print(f"  • {issue}")
        print("\n📖 Setup instructions:")
        print("  1. Copy .env.example to .env")
        print("  2. Add your OPENAI_API_KEY to .env")
        print("  3. Run: python scripts/bootstrap_atomic.py")

        # Offer to run bootstrap
        run_bootstrap = input("\nRun bootstrap now? (y/n): ").strip().lower()
        if run_bootstrap == "y":
            print("\n🔄 Running atomic bootstrap...")
            import subprocess
            result = subprocess.run(
                [sys.executable, str(project_root / "scripts" / "bootstrap_atomic.py")],
                cwd=str(project_root)
            )
            if result.returncode == 0:
                print("\n✅ Bootstrap complete! Restarting...")
            else:
                print("\n❌ Bootstrap failed. Please check the errors above.")
                sys.exit(1)
        else:
            sys.exit(1)

    print("✅ System ready!")

    # Initialize game state database
    try:
        from data.sqlite_db import GameStateDB
        game_state_db = GameStateDB(GAME_STATE_DB_PATH)
        print("✅ Game state database initialized")
    except Exception as e:
        print(f"⚠️  Could not initialize game state database: {e}")
        print("  Persistence features may not work correctly")

    # Initialize entity manager to show stats
    try:
        entity_manager = EntityManager(REFERENCE_DB_PATH, VECTOR_DB_DIR)

        # Get entity counts
        entity_counts = entity_manager.db.query("""
            SELECT type, COUNT(*) as count
            FROM entities
            GROUP BY type
            ORDER BY type
        """)

        print(f"\n📚 Atomic Entities Indexed:")
        total_entities = 0
        for row in entity_counts:
            print(f"  • {row['type'].capitalize()}s: {row['count']}")
            total_entities += row['count']
        print(f"  • Total: {total_entities}")

    except Exception as e:
        print(f"\n⚠️  Could not load entity stats: {e}")

    print("\n🏗️  Architecture V3:")
    print("  ✅ Atomic entities (Spell, Monster, Rule, Item)")
    print("  ✅ Two-stage retrieval (metadata → embedding)")
    print("  ✅ LRU entity caching (100 entries)")
    print("  ✅ Tool-based rule injection (on-demand)")
    print("  ✅ Vector DB with OpenAI embeddings (text-embedding-3-small)")
    print("  ✅ Dice rolling system with advantage/disadvantage")
    print("  ✅ Multi-agent system (DM + Command Agent)")
    print("  ✅ Session persistence (SQLite)")
    print("  ✅ Full conversation/combat history")
    print("  ✅ DM Agent V2 with OpenAI/ChatGPT")

    print("\n🎮 Available Modes:")
    print("  1. Web UI - Modern web interface (RECOMMENDED)")
    print("  2. Terminal UI - Rich terminal interface")
    print("  3. Chat Mode - Simple chat interface")
    print("  4. Test Dice - Test dice rolling system")
    print("  5. Exit")

    while True:
        choice = input("\nSelect mode (1-5): ").strip()

        if choice == "1":
            try:
                from ui.web_server import main as web_main
                print("\n🌐 Starting Web UI...")
                print("\n📱 Open your browser to: http://localhost:5001")
                print("Press Ctrl+C to stop\n")
                web_main()
            except Exception as e:
                print(f"\n❌ Error starting web UI: {e}")
                import traceback
                traceback.print_exc()
            break
        elif choice == "2":
            try:
                from ui.interactive_dm import InteractiveDM
                print("\n🎮 Starting Terminal UI...")
                dm = InteractiveDM()
                dm.run()
            except Exception as e:
                print(f"\n❌ Error starting terminal UI: {e}")
                print("Falling back to chat mode...")
                chat_mode()
            break
        elif choice == "3":
            chat_mode()
            break
        elif choice == "4":
            test_dice()
        elif choice == "5":
            print("\n👋 Goodbye!")
            break
        else:
            print("Invalid choice. Please enter 1-5.")


if __name__ == "__main__":
    main()
