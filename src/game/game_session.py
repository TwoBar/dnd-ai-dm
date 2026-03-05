"""
Game Session Management
Encapsulates a single game session with all required state and agents.
"""

import logging
import os
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from domain.game_state import GameState, Character
from agent.dm_agent_v2 import DMAgentV2
from agent.intent_agent import IntentAgent
from game.spatial.spatial_agent import SpatialAgent, EntityPlacement, BoundingBox
from game.spatial.spatial_translator import SpatialTranslator
from game.workflow import WorkflowOrchestrator

logger = logging.getLogger(__name__)


def _get_db_path() -> str:
    """Get path to the shared game_state.db."""
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    return os.path.join(project_root, 'data', 'game_state.db')


def _db_query(query: str, params: tuple = ()) -> list:
    """Execute a SELECT and return list of dicts."""
    import sqlite3
    conn = sqlite3.connect(_get_db_path())
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _db_execute(query: str, params: tuple = ()):
    """Execute an INSERT/UPDATE/DELETE."""
    import sqlite3
    conn = sqlite3.connect(_get_db_path())
    try:
        conn.execute(query, params)
        conn.commit()
    finally:
        conn.close()


def _ensure_world_session():
    """Ensure the 'world' pseudo-session exists for shared entities."""
    try:
        existing = _db_query("SELECT id FROM sessions WHERE id = 'world'")
        if not existing:
            _db_execute("""
                INSERT OR IGNORE INTO sessions (id, name, status, created_at, updated_at, last_played_at)
                VALUES ('world', 'Shared World', 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """)
    except Exception as e:
        logger.warning("Failed to ensure world session: %s", e)


def _ensure_world_locations(spatial_agent):
    """Create shared world locations and furniture idempotently.

    Uses session_id='world' for locations and furniture so they are
    visible to all sessions. Only called once; subsequent calls are no-ops
    because create_location returns False for duplicates and place_entity
    silently skips existing entity IDs.
    """
    _ensure_world_session()

    # Create tavern location (10m x 10m, MEDIUM scale) — idempotent
    existing = spatial_agent.get_location("tavern_main")
    if not existing:
        spatial_agent.create_location(
            session_id='world',
            location_id="tavern_main",
            name="The Prancing Pony - Main Hall",
            location_type="tavern_interior",
            bbox=BoundingBox(
                x_min=0, y_min=0, z_min=0,
                x_max=10, y_max=10, z_max=3
            ),
            scale_band='M',
            parent_location_id=None
        )

    # Place tavern features (furniture, etc.) — use 'world' session_id
    features = [
        {'id': 'bar_counter', 'sprite': '\U0001f37a', 'x': 5.0, 'y': 9.0, 'name': 'Bar Counter', 'volume': 2.0},
        {'id': 'table_1', 'sprite': '\U0001fa91', 'x': 2.0, 'y': 2.0, 'name': 'Corner Table', 'volume': 0.5},
        {'id': 'table_2', 'sprite': '\U0001fa91', 'x': 8.0, 'y': 2.0, 'name': 'Window Table', 'volume': 0.5},
        {'id': 'table_3', 'sprite': '\U0001fa91', 'x': 5.0, 'y': 5.0, 'name': 'Center Table', 'volume': 0.5},
        {'id': 'fireplace', 'sprite': '\U0001f525', 'x': 0.5, 'y': 5.0, 'name': 'Fireplace', 'volume': 1.0},
        {'id': 'entrance', 'sprite': '\U0001f6aa', 'x': 5.0, 'y': 0.5, 'name': 'Entrance', 'volume': 0.1},
    ]

    for feature in features:
        # Try to place entity (skip if already exists)
        try:
            spatial_agent.place_entity(
                session_id='world',
                entity_id=feature['id'],
                location_id='tavern_main',
                placement=EntityPlacement(
                    entity_id=feature['id'],
                    entity_name=feature['name'],
                    x=feature['x'],
                    y=feature['y'],
                    z=0.0,
                    volume_m3=feature['volume'],
                    is_blocking=(feature['id'] != 'entrance')
                ),
                furniture_id=feature['id'],
                sprite_id=feature['sprite'],
                description=feature['name']
            )
        except Exception as e:
            # Entity might already exist, skip
            logger.debug("Skipping feature %s: %s", feature['id'], e)

    logger.info("World locations ensured (tavern_main + %d features)", len(features))


@dataclass
class SessionConfig:
    """Configuration for a game session"""
    enable_learning: bool = False
    auto_approve_patterns: bool = False
    enable_spatial: bool = True
    default_location: str = "tavern"


class GameSession:
    """
    Encapsulates a single game session with all required state.

    This class manages:
    - Game state (characters, monsters, combat)
    - Message history
    - Agents (DM, Intent, Spatial)
    - Workflow orchestrator
    - Spatial environment
    """

    def __init__(self, session_id: str, config: Optional[SessionConfig] = None):
        self.session_id = session_id
        self.config = config or SessionConfig()
        self.created_at = datetime.now()
        self.message_history: List[Dict] = []

        # Initialize game state
        self.game_state = GameState()

        # Ensure session_game_characters table exists (for persistence)
        self._ensure_persistence_tables()

        # Create session record in database (needed for spatial foreign keys)
        self._create_session_record()

        # Initialize agents
        logger.info(f"[Session {session_id}] Initializing agents...")
        self.dm_agent = DMAgentV2()
        self.intent_agent = IntentAgent()

        # Initialize command agent for mechanics execution
        from agent.command_agent import CommandAgent
        self.command_agent = CommandAgent(game_state=self.game_state)

        # Initialize spatial agent if enabled
        self.spatial_agent: Optional[SpatialAgent] = None
        self.spatial_translator: Optional[SpatialTranslator] = None
        if self.config.enable_spatial:
            try:
                # Database paths
                import os
                project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
                ref_db_path = os.path.join(project_root, 'data', 'reference.db')
                game_db_path = os.path.join(project_root, 'data', 'game_state.db')

                self.spatial_agent = SpatialAgent(
                    reference_db_path=ref_db_path,
                    game_state_db_path=game_db_path
                )
                self.spatial_translator = SpatialTranslator(self.spatial_agent)
                # Wire spatial agent into command agent for dead monster cleanup (ISSUE 9)
                self.command_agent.spatial_agent = self.spatial_agent
                logger.info(f"[Session {session_id}] ✅ Spatial agent initialized")
                self._setup_default_location()
            except Exception as e:
                logger.error(f"[Session {session_id}] ⚠️  Failed to initialize spatial agent: {e}")
                import traceback
                traceback.print_exc()
                self.spatial_agent = None
                self.spatial_translator = None

        # Initialize workflow orchestrator with reasoning system
        try:
            from ui.workflow_init import initialize_workflow
            self.workflow = initialize_workflow(
                game_state=self.game_state,
                command_agent=self.command_agent,
                dm_agent=self.dm_agent,
                enable_learning=self.config.enable_learning,
                auto_approve_patterns=self.config.auto_approve_patterns,
                spatial_agent=self.spatial_agent,
                spatial_translator=self.spatial_translator
            )
            logger.info(f"[Session {session_id}] ✅ Workflow orchestrator initialized")
        except Exception as e:
            logger.error(f"[Session {session_id}] ⚠️  Failed to initialize workflow: {e}")
            self.workflow = None
            raise RuntimeError(f"Failed to initialize workflow for session {session_id}: {e}")

    def _ensure_persistence_tables(self):
        """Create tables needed for session persistence if they don't exist."""
        try:
            _db_execute("""
                CREATE TABLE IF NOT EXISTS session_game_characters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    class_name TEXT,
                    level INTEGER DEFAULT 1,
                    hp INTEGER DEFAULT 0,
                    max_hp INTEGER DEFAULT 0,
                    ac INTEGER DEFAULT 10,
                    race TEXT,
                    ability_scores TEXT,
                    background TEXT,
                    is_draft INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(session_id, name)
                )
            """)
        except Exception as e:
            logger.warning("Failed to create persistence tables: %s", e)

    def _create_session_record(self):
        """Create session record in database if it doesn't exist.

        Uses the REAL sessions table schema: status, last_played_at.
        """
        try:
            existing = _db_query("SELECT id FROM sessions WHERE id = ?", (self.session_id,))
            if not existing:
                now = self.created_at.isoformat()
                _db_execute("""
                    INSERT INTO sessions (id, name, status, created_at, updated_at, last_played_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (self.session_id, f"Session {self.session_id[:8]}", 'active', now, now, now))
                logger.info("[Session %s] Created session record in database", self.session_id)
        except Exception as e:
            logger.error("[Session %s] Failed to create session record: %s", self.session_id, e)

    def _setup_default_location(self):
        """Set up the default tavern location with emoji sprites.

        Uses idempotent operations so multiple sessions can call this safely.
        Location and furniture use session_id='world' (shared across sessions).
        Only creature entities (PCs, monsters) use real session_ids.
        """
        if not self.spatial_agent:
            return

        try:
            _ensure_world_locations(self.spatial_agent)
            logger.info(f"[Session {self.session_id}] World locations ensured")
        except Exception as e:
            logger.error(f"[Session {self.session_id}] Failed to set up default location: {e}")

    def add_player_character(self, character_data: Dict) -> bool:
        """
        Add a player character to the session and place in spatial world.

        Args:
            character_data: Character data dict from character creation

        Returns:
            True if successful, False otherwise
        """
        try:
            # Add to game state
            # TODO: This will depend on how character creation works
            # For now, just log
            logger.info(f"[Session {self.session_id}] Adding character: {character_data.get('name', 'Unknown')}")

            # Place in spatial world (near entrance)
            if self.spatial_agent:
                char_name = character_data.get('name', 'Player')
                entity_id = f"pc_{char_name.lower()}"

                self.spatial_agent.place_entity(
                    session_id=self.session_id,
                    entity_id=entity_id,
                    location_id='tavern_main',
                    placement=EntityPlacement(
                        entity_id=entity_id,
                        entity_name=char_name,
                        x=5.0,  # Center of room
                        y=2.0,  # Near entrance
                        z=0.0,
                        volume_m3=0.1,  # Small character footprint
                        is_blocking=True
                    ),
                    creature_id=char_name,  # Set creature_id so get_entity_by_creature_id works
                    sprite_id='🧙',  # Default player sprite
                    description=f"Player character: {char_name}"
                )
                logger.info(f"[Session {self.session_id}] ✅ Character placed in tavern")

            return True

        except Exception as e:
            logger.error(f"[Session {self.session_id}] Failed to add character: {e}")
            return False

    def spawn_monster(self, monster_name: str, position: Optional[tuple] = None) -> bool:
        """
        Spawn a monster in the current location.

        Args:
            monster_name: Name of the monster type (e.g., "goblin")
            position: Optional (x, y) position. If not provided, uses random position.

        Returns:
            True if successful, False otherwise
        """
        try:
            # TODO: Load monster stats from reference database
            # For now, use placeholder
            monster_sprites = {
                'goblin': '👹',
                'orc': '👺',
                'dragon': '🐉',
                'skeleton': '💀',
                'wolf': '🐺',
                'spider': '🕷️'
            }

            sprite = monster_sprites.get(monster_name.lower(), '👾')

            # Use provided position or default
            x, y = position if position else (7.0, 7.0)

            if self.spatial_agent:
                entity_id = f"monster_{monster_name.lower()}_{int(datetime.now().timestamp() * 1000)}"
                monster_display_name = monster_name.capitalize()

                self.spatial_agent.place_entity(
                    session_id=self.session_id,
                    entity_id=entity_id,
                    location_id='tavern_main',
                    placement=EntityPlacement(
                        entity_id=entity_id,
                        entity_name=monster_display_name,
                        x=x,
                        y=y,
                        z=0.0,
                        volume_m3=0.5,  # Medium creature
                        is_blocking=True
                    ),
                    sprite_id=sprite,
                    description=f"{monster_display_name} (HP: 20, AC: 13)"
                )

                logger.info(f"[Session {self.session_id}] ✅ Spawned {monster_name} at ({x}, {y})")
                return True

            return False

        except Exception as e:
            logger.error(f"[Session {self.session_id}] Failed to spawn monster: {e}")
            return False

    def get_spatial_context(self, entity_id: Optional[str] = None) -> Optional[Dict]:
        """
        Get spatial context for an entity (or current location).

        Args:
            entity_id: Entity to get context for (defaults to first player character)

        Returns:
            Spatial context dict with nearby entities, location info, etc.
        """
        if not self.spatial_agent:
            return None

        try:
            # Get entity position
            if not entity_id:
                # Find first player character
                entities = self.spatial_agent.get_entities_in_location(location_id='tavern_main', scale_filter=False)
                player_entities = [e for e in entities if e.get('entity_metadata', {}).get('type') == 'player_character']
                if not player_entities:
                    return None
                entity_data = player_entities[0]
            else:
                entity_data = [e for e in self.spatial_agent.get_entities_in_location(location_id='tavern_main', scale_filter=False) if e['entity_id'] == player_entity_id]
                if not entity_data:
                    return None
                entity_data = entity_data[0]

            # Get nearby entities (within 10m)
            nearby = self.spatial_agent.get_entities_near(
                location_id='tavern_main',
                x=entity_data['x'],
                y=entity_data['y'],
                radius=10.0
            )

            # Separate by type
            nearby_monsters = [e for e in nearby if e.get('entity_metadata', {}).get('type') == 'monster']
            nearby_features = [e for e in nearby if e.get('entity_metadata', {}).get('type') == 'feature']

            # Calculate distances and sort
            for entity in nearby_monsters + nearby_features:
                dx = entity['x'] - entity_data['x']
                dy = entity['y'] - entity_data['y']
                entity['distance'] = (dx**2 + dy**2) ** 0.5

            nearby_monsters.sort(key=lambda e: e['distance'])

            return {
                'entity_id': entity_id,
                'position': {'x': entity_data['x'], 'y': entity_data['y'], 'z': entity_data.get('z', 0)},
                'location_id': entity_data.get('location_id', 'tavern_main'),
                'nearby_monsters': nearby_monsters,
                'nearby_features': nearby_features,
                'scale_band': 'M',
                'tile_size': 1.0  # meters
            }

        except Exception as e:
            logger.error(f"[Session {self.session_id}] Failed to get spatial context: {e}")
            return None

    def process_message(self, user_message: str) -> Dict:
        """
        Process a user message through the workflow.

        Args:
            user_message: The user's input message

        Returns:
            Result dict with dm_response, dice_rolls, mechanics_summary, spatial_state
        """
        if not self.workflow:
            raise RuntimeError(f"Session {self.session_id} has no workflow orchestrator")

        try:
            # Process through workflow (workflow builds its own spatial context internally)
            workflow_result = self.workflow.process_message(
                user_message=user_message,
                session_id=self.session_id,
                message_history=self.message_history
            )

            # Convert WorkflowResult to dict for easier handling
            result = {
                'success': workflow_result.success,
                'dm_response': workflow_result.dm_response,
                'mechanics_summary': workflow_result.mechanics_summary,
                'game_state_changes': workflow_result.game_state_changes,
                'intent': workflow_result.intent.to_dict() if workflow_result.intent else None,
                'metrics': workflow_result.context.get_phase_latencies_ms()
            }

            # Use map_state from workflow if available (includes walls, connections, etc.)
            if workflow_result.map_state:
                print(f"[GameSession] Using workflow map_state with {len(workflow_result.map_state.get('entities', []))} entities")
                result['map_state'] = workflow_result.map_state

            # Add to message history
            self.message_history.append({
                'role': 'user',
                'content': user_message,
                'timestamp': datetime.now().isoformat()
            })

            self.message_history.append({
                'role': 'assistant',
                'content': result['dm_response'],
                'timestamp': datetime.now().isoformat(),
                'dice_rolls': workflow_result.context.dice_rolls,
                'mechanics': result['mechanics_summary']
            })

            # Persist messages to DB (real schema: message_type, sequence)
            try:
                self._persist_message('player', user_message, 'user')
                self._persist_message('dm', result['dm_response'], 'dm')
            except Exception as e:
                logger.warning("[Session %s] Failed to persist messages: %s", self.session_id, e)

            # Persist characters if any changed
            if result.get('game_state_changes', {}).get('character_created') or \
               result.get('game_state_changes', {}).get('hp_changed'):
                try:
                    self._persist_characters()
                except Exception as e:
                    logger.warning("[Session %s] Failed to persist characters: %s", self.session_id, e)

            # Touch session last_played_at (real schema column)
            try:
                _db_execute(
                    "UPDATE sessions SET last_played_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (self.session_id,)
                )
            except Exception:
                pass

            return result

        except Exception as e:
            logger.error(f"[Session {self.session_id}] Error processing message: {e}")
            import traceback
            traceback.print_exc()
            raise

    def _persist_message(self, speaker: str, message: str, msg_type: str):
        """Persist a single message to the real messages table."""
        # Real schema: id INTEGER, session_id, speaker, message, message_type, sequence, created_at
        seq_rows = _db_query(
            "SELECT COALESCE(MAX(sequence), 0) + 1 as next_seq FROM messages WHERE session_id = ?",
            (self.session_id,)
        )
        next_seq = seq_rows[0]['next_seq'] if seq_rows else 1
        _db_execute("""
            INSERT INTO messages (session_id, speaker, message, message_type, sequence)
            VALUES (?, ?, ?, ?, ?)
        """, (self.session_id, speaker, message, msg_type, next_seq))

    def _persist_characters(self):
        """Upsert all characters from game_state to session_game_characters."""
        import json
        for char in self.game_state.characters:
            existing = _db_query(
                "SELECT id FROM session_game_characters WHERE session_id = ? AND name = ?",
                (self.session_id, char.name)
            )
            ability_json = json.dumps(char.ability_scores) if char.ability_scores else '{}'
            if existing:
                _db_execute("""
                    UPDATE session_game_characters
                    SET hp = ?, max_hp = ?, ac = ?, level = ?, class_name = ?,
                        race = ?, ability_scores = ?, background = ?,
                        is_draft = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE session_id = ? AND name = ?
                """, (char.hp, char.max_hp, char.ac, char.level, char.class_name,
                      char.race, ability_json, char.background,
                      1 if char.is_draft else 0, self.session_id, char.name))
            else:
                _db_execute("""
                    INSERT INTO session_game_characters
                        (session_id, name, class_name, level, hp, max_hp, ac, race,
                         ability_scores, background, is_draft)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (self.session_id, char.name, char.class_name or 'Unknown',
                      char.level, char.hp, char.max_hp, char.ac, char.race,
                      ability_json, char.background, 1 if char.is_draft else 0))
        logger.info("[Session %s] Persisted %d character(s)", self.session_id, len(self.game_state.characters))

    @classmethod
    def recover(cls, session_id: str, config: Optional[SessionConfig] = None) -> 'GameSession':
        """Recover an existing session from database.

        Loads characters and message history from the DB, rebuilds agents
        and workflow, but skips tavern setup (spatial entities already exist).
        """
        # Verify session exists in DB
        existing = _db_query("SELECT id FROM sessions WHERE id = ?", (session_id,))
        if not existing:
            raise RuntimeError(f"Session {session_id} not found in database")

        session = cls.__new__(cls)
        session.session_id = session_id
        session.config = config or SessionConfig()
        session.created_at = datetime.now()
        session.message_history = []

        # Init game state
        session.game_state = GameState()

        # Ensure persistence tables exist
        session._ensure_persistence_tables()

        # Restore characters from session_game_characters
        import json
        char_rows = _db_query(
            "SELECT * FROM session_game_characters WHERE session_id = ?",
            (session_id,)
        )
        for row in char_rows:
            ability_scores = None
            if row.get('ability_scores'):
                try:
                    ability_scores = json.loads(row['ability_scores'])
                except (json.JSONDecodeError, TypeError):
                    ability_scores = None

            # Load spells from character_spells table
            spells_known = None
            spell_slots = None
            try:
                creature_id = f"creature:{row['name'].lower()}-session-{session_id[:8]}"
                spell_rows = _db_query(
                    "SELECT spell_id FROM character_spells WHERE character_id = ?",
                    (creature_id,)
                )
                if spell_rows:
                    spells_known = [r['spell_id'].replace('spell:', '') for r in spell_rows]

                # Load spell slots from characters table
                char_data = _db_query(
                    "SELECT spell_slots FROM characters WHERE creature_id = ?",
                    (creature_id,)
                )
                if char_data and char_data[0].get('spell_slots'):
                    raw_slots = char_data[0]['spell_slots']
                    if isinstance(raw_slots, str):
                        raw_slots = json.loads(raw_slots)
                    # Convert string keys to int: {"1": {"max": 3, ...}} → {1: 3}
                    if isinstance(raw_slots, dict):
                        spell_slots = {}
                        for k, v in raw_slots.items():
                            level = int(k)
                            if isinstance(v, dict):
                                spell_slots[level] = v.get('max', v.get('current', v.get('total', 0)))
                            else:
                                spell_slots[level] = int(v)
            except Exception as e:
                logger.debug("Could not load spells for %s: %s", row['name'], e)

            # If no spell data from DB, compute defaults from class/level
            if spell_slots is None and row.get('class_name'):
                try:
                    from agent.command.character_tools import _get_spell_slots, _get_default_spells
                    spell_slots = _get_spell_slots(row.get('class_name', ''), row.get('level', 1)) or None
                    if spells_known is None:
                        spells_known = _get_default_spells(row.get('class_name', ''), row.get('level', 1)) or None
                except Exception:
                    pass

            character = Character(
                name=row['name'],
                class_name=row.get('class_name', 'Unknown'),
                level=row.get('level', 1),
                hp=row.get('hp', 0),
                max_hp=row.get('max_hp', 0),
                ac=row.get('ac', 10),
                race=row.get('race'),
                ability_scores=ability_scores,
                background=row.get('background'),
                is_draft=bool(row.get('is_draft')),
                spell_slots=spell_slots,
                spells_known=spells_known,
            )
            session.game_state.add_character(character)

        # Restore message history (real schema: message_type, sequence)
        messages = _db_query(
            "SELECT speaker, message, created_at FROM messages WHERE session_id = ? ORDER BY sequence ASC",
            (session_id,)
        )
        session.message_history = [
            {
                'role': m['speaker'],
                'content': m['message'],
                'timestamp': m.get('created_at', ''),
            }
            for m in messages
        ]

        logger.info(
            "[Session %s] Recovered %d characters, %d messages from DB",
            session_id, len(session.game_state.characters), len(session.message_history)
        )

        # Initialize agents (same as __init__)
        session.dm_agent = DMAgentV2()
        session.intent_agent = IntentAgent()

        from agent.command_agent import CommandAgent
        session.command_agent = CommandAgent(game_state=session.game_state)

        # Initialize spatial agent (skip tavern setup — entities already in DB)
        session.spatial_agent = None
        session.spatial_translator = None
        if session.config.enable_spatial:
            try:
                project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
                ref_db_path = os.path.join(project_root, 'data', 'reference.db')
                game_db_path = os.path.join(project_root, 'data', 'game_state.db')

                session.spatial_agent = SpatialAgent(
                    reference_db_path=ref_db_path,
                    game_state_db_path=game_db_path
                )
                session.spatial_translator = SpatialTranslator(session.spatial_agent)
                session.command_agent.spatial_agent = session.spatial_agent
                logger.info("[Session %s] Spatial agent initialized (recovery, no tavern setup)", session_id)
            except Exception as e:
                logger.error("[Session %s] Failed to initialize spatial agent during recovery: %s", session_id, e)
                session.spatial_agent = None
                session.spatial_translator = None

        # Initialize workflow orchestrator
        try:
            from ui.workflow_init import initialize_workflow
            session.workflow = initialize_workflow(
                game_state=session.game_state,
                command_agent=session.command_agent,
                dm_agent=session.dm_agent,
                enable_learning=session.config.enable_learning,
                auto_approve_patterns=session.config.auto_approve_patterns,
                spatial_agent=session.spatial_agent,
                spatial_translator=session.spatial_translator,
            )
            logger.info("[Session %s] Workflow orchestrator initialized (recovery)", session_id)
        except Exception as e:
            logger.error("[Session %s] Failed to initialize workflow during recovery: %s", session_id, e)
            session.workflow = None
            raise RuntimeError(f"Failed to recover session {session_id}: {e}")

        return session

    def cleanup(self):
        """Clean up session resources"""
        logger.info(f"[Session {self.session_id}] Cleaning up session...")

        # Clean up spatial agent resources
        if self.spatial_agent:
            try:
                # Remove session locations
                # TODO: Add cleanup method to SpatialAgent if needed
                pass
            except Exception as e:
                logger.error(f"[Session {self.session_id}] Error cleaning up spatial agent: {e}")

        logger.info(f"[Session {self.session_id}] ✅ Session cleaned up")
