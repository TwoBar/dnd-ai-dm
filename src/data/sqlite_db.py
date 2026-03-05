"""SQLite database management"""
import sqlite3
import json
from typing import Any, Dict, List, Optional
from pathlib import Path
from contextlib import contextmanager


class SQLiteDB:
    """SQLite database wrapper with utility methods"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Access columns by name
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def _init_db(self):
        """Initialize database with basic schema"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Create metadata table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS _metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Store schema version
            cursor.execute("""
                INSERT OR IGNORE INTO _metadata (key, value)
                VALUES ('schema_version', '1.0')
            """)

    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute a SQL query"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor

    def query(self, query: str, params: tuple = ()) -> List[Dict]:
        """Execute a SELECT query and return results as dictionaries"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            columns = [col[0] for col in cursor.description] if cursor.description else []
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def query_one(self, query: str, params: tuple = ()) -> Optional[Dict]:
        """Execute a SELECT query and return first result"""
        results = self.query(query, params)
        return results[0] if results else None

    def insert(self, table: str, data: Dict[str, Any]) -> int:
        """Insert a row and return the last insert rowid"""
        columns = list(data.keys())
        placeholders = ", ".join(["?"] * len(columns))
        column_names = ", ".join(columns)
        values = [self._serialize_value(data[col]) for col in columns]

        query = f"INSERT INTO {table} ({column_names}) VALUES ({placeholders})"

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, values)
            return cursor.lastrowid

    def update(self, table: str, data: Dict[str, Any], where: str, where_params: tuple = ()) -> int:
        """Update rows and return number of affected rows"""
        set_clause = ", ".join([f"{col} = ?" for col in data.keys()])
        values = [self._serialize_value(val) for val in data.values()]

        query = f"UPDATE {table} SET {set_clause} WHERE {where}"

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, values + list(where_params))
            return cursor.rowcount

    def delete(self, table: str, where: str, where_params: tuple = ()) -> int:
        """Delete rows and return number of affected rows"""
        query = f"DELETE FROM {table} WHERE {where}"

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, where_params)
            return cursor.rowcount

    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists"""
        result = self.query_one(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        )
        return result is not None

    def create_table_from_sample(self, table_name: str, sample_data: Dict[str, Any]):
        """Dynamically create a table based on sample data"""
        if self.table_exists(table_name):
            return

        columns = []
        for key, value in sample_data.items():
            if isinstance(value, int):
                col_type = "INTEGER"
            elif isinstance(value, float):
                col_type = "REAL"
            elif isinstance(value, (dict, list)):
                col_type = "TEXT"  # Store as JSON
            else:
                col_type = "TEXT"

            columns.append(f"{key} {col_type}")

        columns_sql = ", ".join(columns)

        self.execute(f"""
            CREATE TABLE {table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                {columns_sql},
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    def _serialize_value(self, value: Any) -> Any:
        """Serialize complex types to JSON strings"""
        if isinstance(value, (dict, list)):
            return json.dumps(value)
        return value

    def _deserialize_value(self, value: Any, expected_type: type = None) -> Any:
        """Deserialize JSON strings back to objects"""
        if isinstance(value, str) and expected_type in (dict, list):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return value


class ReferenceDB(SQLiteDB):
    """Database for reference data (classes, races, cached entities)"""

    def __init__(self, db_path: Path):
        super().__init__(db_path)
        self._init_reference_tables()

    def _init_reference_tables(self):
        """Initialize reference data tables"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Classes table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS classes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    hit_die TEXT,
                    primary_ability TEXT,
                    saves TEXT,
                    proficiencies TEXT,
                    features TEXT,
                    spellcasting TEXT,
                    source_file TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Races table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS races (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    ability_score_increase TEXT,
                    size TEXT,
                    speed INTEGER,
                    traits TEXT,
                    languages TEXT,
                    source_file TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_classes_name ON classes(name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_races_name ON races(name)")


class GameStateDB(SQLiteDB):
    """Database for active game state"""

    def __init__(self, db_path: Path):
        super().__init__(db_path)
        self._init_game_tables()

    def _init_game_tables(self):
        """Initialize game state tables"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    last_accessed TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    is_active INTEGER DEFAULT 1,
                    user_id TEXT
                )
            """)

            # Characters table (enhanced schema)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS characters (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    race TEXT,
                    class_name TEXT NOT NULL,
                    level INTEGER NOT NULL DEFAULT 1,
                    background TEXT,
                    hp_current INTEGER NOT NULL,
                    hp_max INTEGER NOT NULL,
                    hp_temp INTEGER DEFAULT 0,
                    ac INTEGER NOT NULL,
                    ability_scores TEXT NOT NULL,
                    skills TEXT,
                    proficiencies TEXT,
                    equipment TEXT,
                    spells_known TEXT,
                    spell_slots TEXT,
                    conditions TEXT DEFAULT '[]',
                    initiative INTEGER,
                    is_draft INTEGER DEFAULT 1,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                )
            """)

            # Monsters table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS monsters (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    reference_id TEXT,
                    hp_current INTEGER NOT NULL,
                    hp_max INTEGER NOT NULL,
                    ac INTEGER NOT NULL,
                    cr REAL NOT NULL,
                    abilities TEXT,
                    traits TEXT,
                    actions TEXT,
                    conditions TEXT DEFAULT '[]',
                    initiative INTEGER,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                )
            """)

            # Combat state table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS combat_state (
                    session_id TEXT PRIMARY KEY,
                    is_active INTEGER DEFAULT 0,
                    round_number INTEGER DEFAULT 0,
                    current_turn TEXT,
                    initiative_order TEXT DEFAULT '[]',
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                )
            """)

            # Messages table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    speaker TEXT NOT NULL,
                    message TEXT NOT NULL,
                    type TEXT NOT NULL,
                    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    sequence_number INTEGER NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                )
            """)

            # Dice rolls table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS dice_rolls (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    notation TEXT NOT NULL,
                    result INTEGER NOT NULL,
                    roll_type TEXT,
                    description TEXT,
                    is_critical INTEGER DEFAULT 0,
                    is_fumble INTEGER DEFAULT 0,
                    advantage INTEGER DEFAULT 0,
                    actor TEXT,
                    target TEXT,
                    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    sequence_number INTEGER NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                )
            """)

            # Combat events table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS combat_events (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    action TEXT NOT NULL,
                    target TEXT,
                    result TEXT,
                    round_number INTEGER,
                    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    sequence_number INTEGER NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                )
            """)

            # Active modifiers table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS active_modifiers (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    modifier_type TEXT NOT NULL,
                    effects TEXT NOT NULL,
                    duration_type TEXT,
                    duration_value INTEGER,
                    remaining INTEGER,
                    source TEXT,
                    created_by TEXT,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                )
            """)

            # Create indexes
            # Note: user_id, is_active, last_accessed columns don't exist in current schema
            # cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)")
            # cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_active ON sessions(is_active)")
            # cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_last_accessed ON sessions(last_accessed)")

            # Note: characters table doesn't have session_id or name columns in current schema
            # cursor.execute("CREATE INDEX IF NOT EXISTS idx_characters_session ON characters(session_id)")
            # cursor.execute("CREATE INDEX IF NOT EXISTS idx_characters_name ON characters(session_id, name)")

            # Note: characters table uses 'state' not 'is_draft'
            # cursor.execute("CREATE INDEX IF NOT EXISTS idx_characters_draft ON characters(is_draft)")

            # Note: monsters table doesn't have session_id in current schema
            # cursor.execute("CREATE INDEX IF NOT EXISTS idx_monsters_session ON monsters(session_id)")
            # cursor.execute("CREATE INDEX IF NOT EXISTS idx_monsters_name ON monsters(session_id, name)")

            # Note: Commenting out indexes that reference non-existent columns
            # The current database schema may differ from what these indexes expect

            # cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id)")
            # cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_sequence ON messages(session_id, sequence_number)")
            # cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(session_id, timestamp)")

            # cursor.execute("CREATE INDEX IF NOT EXISTS idx_dice_session ON dice_rolls(session_id)")
            # cursor.execute("CREATE INDEX IF NOT EXISTS idx_dice_sequence ON dice_rolls(session_id, sequence_number)")
            # cursor.execute("CREATE INDEX IF NOT EXISTS idx_dice_timestamp ON dice_rolls(session_id, timestamp)")

            # cursor.execute("CREATE INDEX IF NOT EXISTS idx_combat_session ON combat_events(session_id)")
            # cursor.execute("CREATE INDEX IF NOT EXISTS idx_combat_sequence ON combat_events(session_id, sequence_number)")
            # cursor.execute("CREATE INDEX IF NOT EXISTS idx_combat_round ON combat_events(session_id, round_number)")

            # cursor.execute("CREATE INDEX IF NOT EXISTS idx_modifiers_session ON active_modifiers(session_id)")
            # cursor.execute("CREATE INDEX IF NOT EXISTS idx_modifiers_entity ON active_modifiers(session_id, entity_id)")
            # cursor.execute("CREATE INDEX IF NOT EXISTS idx_modifiers_expires ON active_modifiers(expires_at)")

    def get_entity_context(self, entity_id: str) -> Dict[str, Any]:
        """
        Get comprehensive entity context for formula execution

        This method fetches all relevant data about an entity (character or monster)
        and returns it in a format suitable for formula evaluation.

        Args:
            entity_id: Creature ID (e.g., "creature:uuid-123")

        Returns:
            Dictionary with entity stats and properties

        Raises:
            ValueError: If entity not found
        """
        # Try to fetch from creatures table first
        query = """
        SELECT
            c.id,
            c.name,
            c.creature_type,
            c.str, c.dex, c.con, c.int, c.wis, c.cha,
            c.hp, c.max_hp, c.temp_hp, c.ac,
            ch.total_level as level,
            ch.proficiency_bonus,
            ch.spell_slots,
            ch.class_resources
        FROM creatures c
        LEFT JOIN characters ch ON ch.creature_id = c.id
        WHERE c.id = ?
        """

        result = self.query_one(query, (entity_id,))

        if result:
            data = dict(result)

            # Parse JSON fields
            if data.get('spell_slots'):
                try:
                    data['spell_slots'] = json.loads(data['spell_slots'])
                except (json.JSONDecodeError, TypeError):
                    data['spell_slots'] = {}

            if data.get('class_resources'):
                try:
                    data['class_resources'] = json.loads(data['class_resources'])
                except (json.JSONDecodeError, TypeError):
                    data['class_resources'] = {}

            # Compute ability modifiers
            import math
            for ability in ['str', 'dex', 'con', 'int', 'wis', 'cha']:
                if ability in data:
                    score = data[ability] or 10
                    data[f'{ability}_mod'] = math.floor((score - 10) / 2)

            return data

        # Fallback: entity not found in creatures table
        # This handles compatibility with older schemas
        raise ValueError(f"Entity not found: {entity_id}")
