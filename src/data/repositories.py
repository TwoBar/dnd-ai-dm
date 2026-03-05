#!/usr/bin/env python3
"""Data repositories for game state persistence"""

import json
import uuid
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path

from data.sqlite_db import GameStateDB


class SessionManager:
    """Manages game sessions"""

    def __init__(self, db: GameStateDB):
        self.db = db

    def create_session(self, name: str, description: str = None, user_id: str = None) -> str:
        """Create a new game session

        Returns:
            session_id (str): UUID of created session
        """
        session_id = str(uuid.uuid4())

        self.db.execute("""
            INSERT INTO sessions (id, name, description, user_id)
            VALUES (?, ?, ?, ?)
        """, (session_id, name, description, user_id))

        # Initialize combat state for session
        self.db.execute("""
            INSERT INTO combat_state (session_id)
            VALUES (?)
        """, (session_id,))

        return session_id

    def get_session(self, session_id: str) -> Optional[Dict]:
        """Get session by ID"""
        result = self.db.query("""
            SELECT * FROM sessions WHERE id = ?
        """, (session_id,))

        if result:
            # Update last_accessed
            self.db.execute("""
                UPDATE sessions
                SET last_accessed = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (session_id,))
            return result[0]
        return None

    def list_sessions(self, user_id: str = None, active_only: bool = True) -> List[Dict]:
        """List all sessions

        Args:
            user_id: Filter by user (None for all)
            active_only: Only return active sessions
        """
        query = "SELECT * FROM sessions WHERE 1=1"
        params = []

        if user_id is not None:
            query += " AND user_id = ?"
            params.append(user_id)

        if active_only:
            query += " AND is_active = 1"

        query += " ORDER BY last_accessed DESC"

        return self.db.query(query, tuple(params))

    def archive_session(self, session_id: str) -> bool:
        """Archive a session (mark inactive)"""
        self.db.execute("""
            UPDATE sessions
            SET is_active = 0, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (session_id,))
        return True

    def delete_session(self, session_id: str) -> bool:
        """Permanently delete a session (CASCADE deletes all related data)"""
        self.db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        return True

    def touch_session(self, session_id: str):
        """Update last_accessed timestamp"""
        self.db.execute("""
            UPDATE sessions
            SET last_accessed = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (session_id,))


class CharacterRepository:
    """CRUD operations for characters"""

    def __init__(self, db: GameStateDB):
        self.db = db

    def create(self, session_id: str, character_data: Dict) -> str:
        """Create a new character

        Args:
            session_id: Session ID
            character_data: Dict with character fields

        Returns:
            character_id (str): UUID of created character
        """
        char_id = str(uuid.uuid4())

        self.db.execute("""
            INSERT INTO characters (
                id, session_id, name, race, class_name, level, background,
                hp_current, hp_max, hp_temp, ac,
                ability_scores, skills, proficiencies, equipment,
                spells_known, spell_slots, conditions, initiative, is_draft
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            char_id,
            session_id,
            character_data.get('name', 'Unnamed'),
            character_data.get('race'),
            character_data.get('class_name'),
            character_data.get('level', 1),
            character_data.get('background'),
            character_data.get('hp_current', 0),
            character_data.get('hp_max', 0),
            character_data.get('hp_temp', 0),
            character_data.get('ac', 10),
            json.dumps(character_data.get('ability_scores', {})),
            json.dumps(character_data.get('skills', {})),
            json.dumps(character_data.get('proficiencies', [])),
            json.dumps(character_data.get('equipment', [])),
            json.dumps(character_data.get('spells_known', [])),
            json.dumps(character_data.get('spell_slots', {})),
            json.dumps(character_data.get('conditions', [])),
            character_data.get('initiative'),
            character_data.get('is_draft', 1)
        ))

        return char_id

    def get(self, character_id: str) -> Optional[Dict]:
        """Get character by ID"""
        result = self.db.query("SELECT * FROM characters WHERE id = ?", (character_id,))
        if result:
            return self._parse_character(result[0])
        return None

    def get_by_session(self, session_id: str) -> List[Dict]:
        """Get all characters in a session"""
        results = self.db.query("SELECT * FROM characters WHERE session_id = ?", (session_id,))
        return [self._parse_character(row) for row in results]

    def get_by_name(self, session_id: str, name: str) -> Optional[Dict]:
        """Get character by name within session"""
        result = self.db.query(
            "SELECT * FROM characters WHERE session_id = ? AND name = ?",
            (session_id, name)
        )
        if result:
            return self._parse_character(result[0])
        return None

    def update(self, character_id: str, updates: Dict) -> bool:
        """Update character fields

        Args:
            character_id: Character ID
            updates: Dict of fields to update
        """
        # Build dynamic UPDATE query
        set_clauses = []
        params = []

        for key, value in updates.items():
            if key in ['ability_scores', 'skills', 'proficiencies', 'equipment', 'spells_known', 'spell_slots', 'conditions']:
                set_clauses.append(f"{key} = ?")
                params.append(json.dumps(value))
            else:
                set_clauses.append(f"{key} = ?")
                params.append(value)

        set_clauses.append("updated_at = CURRENT_TIMESTAMP")
        params.append(character_id)

        query = f"UPDATE characters SET {', '.join(set_clauses)} WHERE id = ?"
        self.db.execute(query, tuple(params))
        return True

    def delete(self, character_id: str) -> bool:
        """Delete a character"""
        self.db.execute("DELETE FROM characters WHERE id = ?", (character_id,))
        return True

    def finalize(self, character_id: str) -> bool:
        """Mark character as finalized (not draft)"""
        self.db.execute("""
            UPDATE characters
            SET is_draft = 0, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (character_id,))
        return True

    def is_draft(self, character_id: str) -> bool:
        """Check if character is still in draft mode"""
        result = self.db.query("SELECT is_draft FROM characters WHERE id = ?", (character_id,))
        if result:
            return bool(result[0]['is_draft'])
        return False

    def _parse_character(self, row: Dict) -> Dict:
        """Parse character row, deserializing JSON fields"""
        char = dict(row)

        # Deserialize JSON fields
        for field in ['ability_scores', 'skills', 'proficiencies', 'equipment', 'spells_known', 'spell_slots', 'conditions']:
            if char.get(field):
                try:
                    char[field] = json.loads(char[field])
                except:
                    char[field] = {} if field in ['ability_scores', 'skills', 'spell_slots'] else []

        return char


class MonsterRepository:
    """CRUD operations for monsters"""

    def __init__(self, db: GameStateDB):
        self.db = db

    def create(self, session_id: str, monster_data: Dict) -> str:
        """Create a new monster"""
        monster_id = str(uuid.uuid4())

        self.db.execute("""
            INSERT INTO monsters (
                id, session_id, name, reference_id,
                hp_current, hp_max, ac, cr,
                abilities, traits, actions, conditions, initiative
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            monster_id,
            session_id,
            monster_data.get('name'),
            monster_data.get('reference_id'),
            monster_data.get('hp_current', 0),
            monster_data.get('hp_max', 0),
            monster_data.get('ac', 10),
            monster_data.get('cr', 0),
            json.dumps(monster_data.get('abilities', {})),
            json.dumps(monster_data.get('traits', [])),
            json.dumps(monster_data.get('actions', [])),
            json.dumps(monster_data.get('conditions', [])),
            monster_data.get('initiative')
        ))

        return monster_id

    def get_by_session(self, session_id: str) -> List[Dict]:
        """Get all monsters in a session"""
        results = self.db.query("SELECT * FROM monsters WHERE session_id = ?", (session_id,))
        return [self._parse_monster(row) for row in results]

    def get_by_name(self, session_id: str, name: str) -> Optional[Dict]:
        """Get monster by name within session"""
        result = self.db.query(
            "SELECT * FROM monsters WHERE session_id = ? AND name = ?",
            (session_id, name)
        )
        if result:
            return self._parse_monster(result[0])
        return None

    def update(self, monster_id: str, updates: Dict) -> bool:
        """Update monster fields"""
        set_clauses = []
        params = []

        for key, value in updates.items():
            if key in ['abilities', 'traits', 'actions', 'conditions']:
                set_clauses.append(f"{key} = ?")
                params.append(json.dumps(value))
            else:
                set_clauses.append(f"{key} = ?")
                params.append(value)

        set_clauses.append("updated_at = CURRENT_TIMESTAMP")
        params.append(monster_id)

        query = f"UPDATE monsters SET {', '.join(set_clauses)} WHERE id = ?"
        self.db.execute(query, tuple(params))
        return True

    def delete(self, monster_id: str) -> bool:
        """Delete a monster"""
        self.db.execute("DELETE FROM monsters WHERE id = ?", (monster_id,))
        return True

    def _parse_monster(self, row: Dict) -> Dict:
        """Parse monster row, deserializing JSON fields"""
        monster = dict(row)

        for field in ['abilities', 'traits', 'actions', 'conditions']:
            if monster.get(field):
                try:
                    monster[field] = json.loads(monster[field])
                except:
                    monster[field] = {} if field == 'abilities' else []

        return monster


class MessageRepository:
    """CRUD operations for messages"""

    def __init__(self, db: GameStateDB):
        self.db = db
        self._sequence_counters = {}  # session_id -> next_sequence

    def add(self, session_id: str, speaker: str, message: str, msg_type: str) -> str:
        """Add a message to the conversation"""
        msg_id = str(uuid.uuid4())

        # Get next sequence number for this session
        sequence = self._get_next_sequence(session_id)

        self.db.execute("""
            INSERT INTO messages (id, session_id, speaker, message, type, sequence_number)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (msg_id, session_id, speaker, message, msg_type, sequence))

        return msg_id

    def get_messages(self, session_id: str, limit: int = None, offset: int = 0) -> List[Dict]:
        """Get messages for a session"""
        query = """
            SELECT * FROM messages
            WHERE session_id = ?
            ORDER BY sequence_number ASC
        """
        params = [session_id]

        if limit:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])

        return self.db.query(query, tuple(params))

    def get_recent(self, session_id: str, n: int = 10) -> List[Dict]:
        """Get last N messages"""
        return self.db.query("""
            SELECT * FROM messages
            WHERE session_id = ?
            ORDER BY sequence_number DESC
            LIMIT ?
        """, (session_id, n))[::-1]  # Reverse to chronological order

    def get_count(self, session_id: str) -> int:
        """Get total message count"""
        result = self.db.query(
            "SELECT COUNT(*) as count FROM messages WHERE session_id = ?",
            (session_id,)
        )
        return result[0]['count'] if result else 0

    def _get_next_sequence(self, session_id: str) -> int:
        """Get next sequence number for session"""
        if session_id not in self._sequence_counters:
            # Get max sequence from database
            result = self.db.query("""
                SELECT MAX(sequence_number) as max_seq
                FROM messages
                WHERE session_id = ?
            """, (session_id,))

            max_seq = result[0]['max_seq'] if result and result[0]['max_seq'] else 0
            self._sequence_counters[session_id] = max_seq + 1

        seq = self._sequence_counters[session_id]
        self._sequence_counters[session_id] += 1
        return seq


class DiceRollRepository:
    """CRUD operations for dice rolls"""

    def __init__(self, db: GameStateDB):
        self.db = db
        self._sequence_counters = {}

    def add(self, session_id: str, roll_data: Dict) -> str:
        """Add a dice roll to the log"""
        roll_id = str(uuid.uuid4())
        sequence = self._get_next_sequence(session_id)

        self.db.execute("""
            INSERT INTO dice_rolls (
                id, session_id, notation, result, roll_type, description,
                is_critical, is_fumble, advantage, actor, target, sequence_number
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            roll_id,
            session_id,
            roll_data.get('notation'),
            roll_data.get('result'),
            roll_data.get('roll_type'),
            roll_data.get('description'),
            roll_data.get('is_critical', 0),
            roll_data.get('is_fumble', 0),
            roll_data.get('advantage', 0),
            roll_data.get('actor'),
            roll_data.get('target'),
            sequence
        ))

        return roll_id

    def get_recent(self, session_id: str, n: int = 10) -> List[Dict]:
        """Get last N dice rolls"""
        return self.db.query("""
            SELECT * FROM dice_rolls
            WHERE session_id = ?
            ORDER BY sequence_number DESC
            LIMIT ?
        """, (session_id, n))[::-1]

    def _get_next_sequence(self, session_id: str) -> int:
        """Get next sequence number"""
        if session_id not in self._sequence_counters:
            result = self.db.query("""
                SELECT MAX(sequence_number) as max_seq
                FROM dice_rolls
                WHERE session_id = ?
            """, (session_id,))

            max_seq = result[0]['max_seq'] if result and result[0]['max_seq'] else 0
            self._sequence_counters[session_id] = max_seq + 1

        seq = self._sequence_counters[session_id]
        self._sequence_counters[session_id] += 1
        return seq


class CombatRepository:
    """Operations for combat state"""

    def __init__(self, db: GameStateDB):
        self.db = db

    def get_state(self, session_id: str) -> Optional[Dict]:
        """Get combat state for session"""
        result = self.db.query(
            "SELECT * FROM combat_state WHERE session_id = ?",
            (session_id,)
        )
        if result:
            state = dict(result[0])
            if state.get('initiative_order'):
                state['initiative_order'] = json.loads(state['initiative_order'])
            return state
        return None

    def update_state(self, session_id: str, updates: Dict) -> bool:
        """Update combat state"""
        set_clauses = []
        params = []

        for key, value in updates.items():
            if key == 'initiative_order':
                set_clauses.append(f"{key} = ?")
                params.append(json.dumps(value))
            else:
                set_clauses.append(f"{key} = ?")
                params.append(value)

        set_clauses.append("updated_at = CURRENT_TIMESTAMP")
        params.append(session_id)

        query = f"UPDATE combat_state SET {', '.join(set_clauses)} WHERE session_id = ?"
        self.db.execute(query, tuple(params))
        return True

    def start_combat(self, session_id: str) -> bool:
        """Mark combat as active"""
        return self.update_state(session_id, {
            'is_active': 1,
            'round_number': 1
        })

    def end_combat(self, session_id: str) -> bool:
        """Mark combat as inactive"""
        return self.update_state(session_id, {
            'is_active': 0,
            'round_number': 0,
            'current_turn': None,
            'initiative_order': []
        })
