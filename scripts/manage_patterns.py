#!/usr/bin/env python3
"""
Pattern Management Utility

Interactive tool for reviewing, approving, and managing learned intent patterns.

Usage:
    python scripts/manage_patterns.py

Commands:
    list       - List all patterns
    pending    - Show pending patterns awaiting approval
    active     - Show active patterns
    review     - Review a specific pattern
    approve    - Approve a pending pattern
    reject     - Reject a pending pattern
    deactivate - Deactivate an active pattern
    stats      - Show pattern statistics
    test       - Test a pattern against messages
    help       - Show commands
    quit       - Exit
"""

import sys
from pathlib import Path
import json
from datetime import datetime
from typing import List

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from agent.pattern_generator_agent import PatternGeneratorAgent, LearnedPattern


class PatternManager:
    """Interactive pattern management interface"""

    def __init__(self, database_path: str):
        """
        Initialize Pattern Manager.

        Args:
            database_path: Path to learned_patterns.db
        """
        self.pattern_gen = PatternGeneratorAgent(database_path=database_path)
        print("📚 Pattern Management Utility")
        print("=" * 60)
        print(f"Database: {database_path}")
        print("Type 'help' for commands\n")

    def run(self):
        """Run interactive loop"""
        while True:
            try:
                command = input("patterns> ").strip().lower()

                if not command:
                    continue

                parts = command.split()
                cmd = parts[0]
                args = parts[1:] if len(parts) > 1 else []

                if cmd in ['quit', 'exit', 'q']:
                    print("Goodbye!")
                    break
                elif cmd == 'help':
                    self.show_help()
                elif cmd == 'list':
                    self.list_patterns(args)
                elif cmd == 'pending':
                    self.show_pending()
                elif cmd == 'active':
                    self.show_active()
                elif cmd == 'review':
                    self.review_pattern(args)
                elif cmd == 'approve':
                    self.approve_pattern(args)
                elif cmd == 'reject':
                    self.reject_pattern(args)
                elif cmd == 'deactivate':
                    self.deactivate_pattern(args)
                elif cmd == 'stats':
                    self.show_stats()
                elif cmd == 'test':
                    self.test_pattern(args)
                else:
                    print(f"Unknown command: {cmd}")
                    print("Type 'help' for available commands")

            except KeyboardInterrupt:
                print("\nInterrupted. Type 'quit' to exit.")
            except Exception as e:
                print(f"Error: {e}")

    def show_help(self):
        """Show available commands"""
        help_text = """
Available Commands:
------------------
  list [status]      - List all patterns (optionally filter by status)
  pending            - Show patterns awaiting approval
  active             - Show active patterns
  review <id>        - Review detailed info for a pattern
  approve <id>       - Approve a pending pattern
  reject <id>        - Reject a pending pattern
  deactivate <id>    - Deactivate an active pattern
  stats              - Show pattern statistics
  test <id> <msg>    - Test pattern against a message
  help               - Show this help
  quit               - Exit

Examples:
---------
  list               # Show all patterns
  list pending       # Show only pending patterns
  review learned_skill_check_1234567890
  approve learned_skill_check_1234567890
  test learned_skill_check_1234567890 "I try to grapple the guard"
"""
        print(help_text)

    def list_patterns(self, args: List[str]):
        """List patterns with optional status filter"""
        status_filter = args[0] if args else None

        # Get all patterns
        import sqlite3
        conn = sqlite3.connect(self.pattern_gen.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if status_filter:
            cursor.execute(
                "SELECT * FROM learned_patterns WHERE status = ? ORDER BY created_at DESC",
                (status_filter,)
            )
        else:
            cursor.execute("SELECT * FROM learned_patterns ORDER BY created_at DESC")

        rows = cursor.fetchall()
        conn.close()

        if not rows:
            print(f"No patterns found" + (f" with status '{status_filter}'" if status_filter else ""))
            return

        print(f"\n{'ID':<40} {'Name':<30} {'Action':<15} {'Status':<10} {'Conf':<6}")
        print("=" * 110)

        for row in rows:
            print(f"{row['pattern_id']:<40} {row['name']:<30} {row['action_type']:<15} {row['status']:<10} {row['confidence']:.2f}")

        print(f"\nTotal: {len(rows)} pattern(s)")

    def show_pending(self):
        """Show pending patterns awaiting approval"""
        patterns = self.pattern_gen.get_pending_patterns()

        if not patterns:
            print("No pending patterns.")
            return

        print(f"\n⏳ Pending Patterns ({len(patterns)})")
        print("=" * 60)

        for i, p in enumerate(patterns, 1):
            print(f"\n[{i}] {p.name}")
            print(f"    ID: {p.pattern_id}")
            print(f"    Action: {p.action_type.value}")
            print(f"    Skill: {p.skill.value if p.skill else 'N/A'}")
            print(f"    Confidence: {p.confidence:.2f}")
            print(f"    Created: {p.created_at}")
            print(f"    Examples: {p.example_messages[0] if p.example_messages else 'N/A'}")

        print(f"\nUse 'review <id>' for details")
        print(f"Use 'approve <id>' or 'reject <id>' to process")

    def show_active(self):
        """Show active patterns"""
        patterns = self.pattern_gen.get_active_patterns()

        if not patterns:
            print("No active patterns.")
            return

        print(f"\n✅ Active Patterns ({len(patterns)})")
        print("=" * 60)

        for i, p in enumerate(patterns, 1):
            # Get usage stats
            import sqlite3
            conn = sqlite3.connect(self.pattern_gen.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT activation_count, success_count, failure_count FROM learned_patterns WHERE pattern_id = ?",
                (p.pattern_id,)
            )
            row = cursor.fetchone()
            conn.close()

            activations = row[0] if row else 0
            successes = row[1] if row else 0
            failures = row[2] if row else 0
            success_rate = (successes / max(activations, 1)) * 100

            print(f"\n[{i}] {p.name}")
            print(f"    ID: {p.pattern_id}")
            print(f"    Action: {p.action_type.value}")
            print(f"    Confidence: {p.confidence:.2f}")
            print(f"    Activations: {activations}")
            print(f"    Success Rate: {success_rate:.1f}% ({successes}/{activations})")
            print(f"    Activated: {p.activated_at}")

        print(f"\nUse 'review <id>' for details")

    def review_pattern(self, args: List[str]):
        """Review detailed pattern information"""
        if not args:
            print("Usage: review <pattern_id>")
            return

        pattern_id = args[0]

        # Get pattern
        import sqlite3
        conn = sqlite3.connect(self.pattern_gen.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM learned_patterns WHERE pattern_id = ?", (pattern_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            print(f"Pattern not found: {pattern_id}")
            return

        # Parse JSON fields
        regex_patterns = json.loads(row['regex_patterns'])
        rule_refs = json.loads(row['rule_references']) if row['rule_references'] else []
        examples = json.loads(row['example_messages'])

        print(f"\n📋 Pattern Details")
        print("=" * 60)
        print(f"ID: {row['pattern_id']}")
        print(f"Name: {row['name']}")
        print(f"Status: {row['status']}")
        print(f"Action Type: {row['action_type']}")
        print(f"Skill: {row['skill'] if row['skill'] else 'N/A'}")
        print(f"Confidence: {row['confidence']:.2f}")
        print(f"Created: {row['created_at']}")
        print(f"Activated: {row['activated_at'] if row['activated_at'] else 'N/A'}")

        print(f"\n🎯 Regex Patterns:")
        for i, pattern in enumerate(regex_patterns, 1):
            print(f"  {i}. {pattern}")

        print(f"\n🎲 Execution Formula:")
        print(f"  {row['execution_formula']}")

        print(f"\n📚 Rule References:")
        if rule_refs:
            for ref in rule_refs:
                print(f"  - {ref.get('source')}: {ref.get('section')}")
                print(f"    {ref.get('text', '')[:100]}...")
        else:
            print("  None")

        print(f"\n💬 Example Messages:")
        for i, example in enumerate(examples, 1):
            print(f"  {i}. \"{example}\"")

        print(f"\n📊 Statistics:")
        print(f"  Activations: {row['activation_count']}")
        print(f"  Successes: {row['success_count']}")
        print(f"  Failures: {row['failure_count']}")
        if row['activation_count'] > 0:
            success_rate = (row['success_count'] / row['activation_count']) * 100
            print(f"  Success Rate: {success_rate:.1f}%")

    def approve_pattern(self, args: List[str]):
        """Approve a pending pattern"""
        if not args:
            print("Usage: approve <pattern_id>")
            return

        pattern_id = args[0]

        # Confirm
        response = input(f"Approve pattern '{pattern_id}'? (y/n): ").strip().lower()
        if response != 'y':
            print("Cancelled.")
            return

        success = self.pattern_gen.approve_pattern(pattern_id)

        if success:
            print(f"✅ Pattern approved and activated: {pattern_id}")
            print("   It will now be used for intent detection!")
        else:
            print(f"❌ Failed to approve pattern: {pattern_id}")
            print("   Pattern may not exist or already processed")

    def reject_pattern(self, args: List[str]):
        """Reject a pending pattern"""
        if not args:
            print("Usage: reject <pattern_id>")
            return

        pattern_id = args[0]

        # Get reason
        reason = input("Reason for rejection (optional): ").strip()

        # Confirm
        response = input(f"Reject pattern '{pattern_id}'? (y/n): ").strip().lower()
        if response != 'y':
            print("Cancelled.")
            return

        success = self.pattern_gen.reject_pattern(pattern_id, reason)

        if success:
            print(f"❌ Pattern rejected: {pattern_id}")
            print(f"   Reason: {reason if reason else 'Not specified'}")
        else:
            print(f"❌ Failed to reject pattern: {pattern_id}")

    def deactivate_pattern(self, args: List[str]):
        """Deactivate an active pattern"""
        if not args:
            print("Usage: deactivate <pattern_id>")
            return

        pattern_id = args[0]

        # Confirm
        response = input(f"Deactivate pattern '{pattern_id}'? (y/n): ").strip().lower()
        if response != 'y':
            print("Cancelled.")
            return

        # Update to rejected status
        success = self.pattern_gen.reject_pattern(pattern_id, "Deactivated by admin")

        if success:
            print(f"🔴 Pattern deactivated: {pattern_id}")
        else:
            print(f"❌ Failed to deactivate pattern: {pattern_id}")

    def show_stats(self):
        """Show pattern statistics"""
        import sqlite3
        conn = sqlite3.connect(self.pattern_gen.db_path)
        cursor = conn.cursor()

        # Count by status
        cursor.execute("SELECT status, COUNT(*) FROM learned_patterns GROUP BY status")
        status_counts = dict(cursor.fetchall())

        # Get total stats
        cursor.execute("""
            SELECT
                SUM(activation_count) as total_activations,
                SUM(success_count) as total_successes,
                SUM(failure_count) as total_failures
            FROM learned_patterns
            WHERE status = 'active'
        """)
        row = cursor.fetchone()
        total_activations = row[0] or 0
        total_successes = row[1] or 0
        total_failures = row[2] or 0

        conn.close()

        # Calculate rates
        success_rate = (total_successes / max(total_activations, 1)) * 100

        print(f"\n📊 Pattern Statistics")
        print("=" * 60)
        print(f"Total Patterns: {sum(status_counts.values())}")
        print(f"  Active:   {status_counts.get('active', 0)}")
        print(f"  Pending:  {status_counts.get('pending', 0)}")
        print(f"  Rejected: {status_counts.get('rejected', 0)}")
        print()
        print(f"Usage Statistics:")
        print(f"  Total Activations: {total_activations}")
        print(f"  Successful Uses:   {total_successes}")
        print(f"  Failed Uses:       {total_failures}")
        print(f"  Success Rate:      {success_rate:.1f}%")

    def test_pattern(self, args: List[str]):
        """Test a pattern against a message"""
        if len(args) < 2:
            print("Usage: test <pattern_id> <message>")
            print("Example: test learned_skill_check_123 \"I try to grapple the guard\"")
            return

        pattern_id = args[0]
        message = ' '.join(args[1:]).strip('"\'')

        # Get pattern
        import sqlite3
        conn = sqlite3.connect(self.pattern_gen.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM learned_patterns WHERE pattern_id = ?", (pattern_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            print(f"Pattern not found: {pattern_id}")
            return

        # Parse pattern
        from agent.intent_agent import ActionType, SkillType
        pattern = LearnedPattern(
            pattern_id=row['pattern_id'],
            name=row['name'],
            action_type=ActionType(row['action_type']),
            regex_patterns=json.loads(row['regex_patterns']),
            skill=SkillType(row['skill']) if row['skill'] else None,
            execution_formula=row['execution_formula'],
            rule_references=json.loads(row['rule_references']) if row['rule_references'] else [],
            example_messages=json.loads(row['example_messages']),
            confidence=row['confidence'],
            status=row['status'],
            created_at=row['created_at'],
            validated_at=row['validated_at'],
            activated_at=row['activated_at']
        )

        # Test match
        matched = self.pattern_gen._test_pattern_match(pattern, message)

        print(f"\n🧪 Pattern Test")
        print("=" * 60)
        print(f"Pattern: {pattern.name}")
        print(f"Message: \"{message}\"")
        print()
        print(f"Result: {'✅ MATCH' if matched else '❌ NO MATCH'}")

        if matched:
            print(f"\nThis pattern would detect:")
            print(f"  Action Type: {pattern.action_type.value}")
            print(f"  Skill: {pattern.skill.value if pattern.skill else 'N/A'}")
            print(f"  Confidence: {pattern.confidence:.2f}")


def main():
    """Main entry point"""
    # Get database path
    base_path = Path(__file__).parent.parent
    db_path = base_path / 'data' / 'learned_patterns.db'

    if not db_path.exists():
        print(f"⚠️  Database not found: {db_path}")
        print("Creating new database...")
        db_path.parent.mkdir(exist_ok=True)

    try:
        manager = PatternManager(str(db_path))
        manager.run()
    except KeyboardInterrupt:
        print("\nGoodbye!")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
