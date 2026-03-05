#!/usr/bin/env python3
"""
Bootstrap Game State Database

Creates game_state.db from schema and optionally migrates data from old database.
"""

import sqlite3
from pathlib import Path

project_root = Path(__file__).parent.parent
GAME_STATE_DB_PATH = project_root / "data" / "game_state.db"
GAME_STATE_SCHEMA_PATH = project_root / "data" / "schemas" / "game_state_db.sql"
OLD_DB_PATH = project_root / "data" / "dnd_game.db"  # Old database if it exists


def create_database():
    """Create game_state.db from schema"""
    print("\n🏗️  Creating game_state.db...")

    # Read schema
    with open(GAME_STATE_SCHEMA_PATH, 'r') as f:
        schema_sql = f.read()

    # Create database
    conn = sqlite3.connect(GAME_STATE_DB_PATH)
    cursor = conn.cursor()

    # Execute schema
    cursor.executescript(schema_sql)
    conn.commit()
    conn.close()

    print(f"   ✓ Database created at {GAME_STATE_DB_PATH}")


def migrate_old_data():
    """Migrate data from old database if it exists"""
    if not OLD_DB_PATH.exists():
        print("\n📦 No old database found - starting fresh")
        return

    print(f"\n📦 Migrating data from {OLD_DB_PATH}...")

    old_conn = sqlite3.connect(OLD_DB_PATH)
    old_conn.row_factory = sqlite3.Row
    new_conn = sqlite3.connect(GAME_STATE_DB_PATH)

    try:
        # Migrate sessions
        sessions = old_conn.execute("SELECT * FROM sessions").fetchall()
        if sessions:
            print(f"   Migrating {len(sessions)} sessions...")
            for session in sessions:
                new_conn.execute("""
                    INSERT OR IGNORE INTO sessions (id, name, description, created_at)
                    VALUES (?, ?, ?, ?)
                """, (session['id'], session['name'], session.get('description', ''), session['created_at']))
            print(f"   ✓ Migrated {len(sessions)} sessions")

        # Migrate messages
        messages = old_conn.execute("SELECT * FROM messages ORDER BY created_at").fetchall()
        if messages:
            print(f"   Migrating {len(messages)} messages...")
            for msg in messages:
                new_conn.execute("""
                    INSERT OR IGNORE INTO messages (id, session_id, role, content, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (msg['id'], msg['session_id'], msg['role'], msg['content'], msg['created_at']))
            print(f"   ✓ Migrated {len(messages)} messages")

        # Migrate dice rolls
        try:
            dice_rolls = old_conn.execute("SELECT * FROM dice_rolls ORDER BY created_at").fetchall()
            if dice_rolls:
                print(f"   Migrating {len(dice_rolls)} dice rolls...")
                for roll in dice_rolls:
                    new_conn.execute("""
                        INSERT OR IGNORE INTO dice_rolls (id, session_id, message_id, notation, result, breakdown, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (roll['id'], roll['session_id'], roll.get('message_id'), roll['notation'],
                          roll['result'], roll.get('breakdown', ''), roll['created_at']))
                print(f"   ✓ Migrated {len(dice_rolls)} dice rolls")
        except sqlite3.OperationalError:
            print("   ⚠ No dice_rolls table in old database - skipping")

        new_conn.commit()
        print("\n✅ Migration complete!")

    except Exception as e:
        print(f"\n❌ Migration error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        old_conn.close()
        new_conn.close()


def main():
    """Main bootstrap function"""
    print("=" * 60)
    print("🎲 D&D AI DM - Bootstrap Game State Database")
    print("=" * 60)

    # Backup existing database if it exists
    if GAME_STATE_DB_PATH.exists():
        backup_path = GAME_STATE_DB_PATH.with_suffix('.db.backup')
        import shutil
        shutil.copy2(GAME_STATE_DB_PATH, backup_path)
        print(f"\n📦 Backed up existing database to {backup_path}")
        GAME_STATE_DB_PATH.unlink()

    # Create new database
    create_database()

    # Migrate old data
    migrate_old_data()

    print("\n" + "=" * 60)
    print("✅ Game state database bootstrap complete!")
    print("=" * 60)
    print(f"\nDatabase location: {GAME_STATE_DB_PATH}")
    print("\nReady for:")
    print("  • Character creation")
    print("  • Session management")
    print("  • Game state tracking")


if __name__ == '__main__':
    main()
