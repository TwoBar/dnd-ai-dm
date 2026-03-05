"""Entity Manager - Two-stage retrieval with caching"""
import json
from pathlib import Path
from typing import List, Dict, Optional, Any

from data.sqlite_db import SQLiteDB
from data.entities import Entity, Spell, Monster, Rule, Item, EntityCache
from data.vector_db import MultiVectorDBManager


class EntityManager:
    """Manages entities with two-stage retrieval: metadata filter → embedding similarity"""

    def __init__(self, db_path: Path, vector_db_path: Path):
        self.db = SQLiteDB(db_path)
        self.vector_db = MultiVectorDBManager(vector_db_path)
        self.cache = EntityCache(maxsize=100)
        self._init_entity_tables()

    def _init_entity_tables(self):
        """Initialize entity metadata tables"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # Main entities table with metadata
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS entities (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    tags TEXT,  -- JSON array
                    content TEXT,
                    metadata TEXT,  -- JSON object

                    -- Spell-specific
                    level INTEGER,
                    school TEXT,
                    classes TEXT,  -- JSON array
                    damage TEXT,
                    save TEXT,

                    -- Monster-specific
                    cr REAL,
                    size TEXT,
                    ac INTEGER,
                    hp TEXT,

                    -- Item-specific
                    rarity TEXT,
                    item_type TEXT,

                    -- Rule-specific
                    domain TEXT,
                    category TEXT,

                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Indexes for fast filtering (Stage 1)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_type ON entities(type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_name ON entities(name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_type_level ON entities(type, level)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_type_cr ON entities(type, cr)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_domain ON entities(domain)")

    def index_entity(self, entity: Entity):
        """
        Index an entity (two-stage):
        1. Store in SQLite with metadata
        2. Embed and store in vector DB
        """
        # Stage 1: Metadata in SQLite
        entity_dict = entity.to_dict()

        # Convert lists to JSON strings
        entity_dict['tags'] = json.dumps(entity_dict.get('tags', []))
        entity_dict['metadata'] = json.dumps(entity_dict.get('metadata', {}))

        if hasattr(entity, 'classes'):
            entity_dict['classes'] = json.dumps(entity.classes)

        # Insert or replace
        columns = list(entity_dict.keys())
        placeholders = ", ".join(["?"] * len(columns))
        column_names = ", ".join(columns)

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"INSERT OR REPLACE INTO entities ({column_names}) VALUES ({placeholders})",
                [entity_dict[col] for col in columns]
            )

        # Stage 2: Embedding in vector DB
        self.vector_db.index_documents(
            category=entity.type + "s",  # spells, monsters, rules, items
            documents=[entity.content],
            metadatas=[{
                "id": entity.id,
                "name": entity.name,
                "type": entity.type,
                "tags": json.dumps(entity.tags)
            }],
            ids=[entity.id]
        )

    def get_entity(
        self,
        entity_type: str,
        name: Optional[str] = None,
        entity_id: Optional[str] = None,
        use_cache: bool = True
    ) -> Optional[Entity]:
        """
        Get a specific entity by name or ID

        Uses cache first, then database
        """
        # Check cache first
        cache_key = entity_id or f"{entity_type}:{name}"
        if use_cache:
            cached = self.cache.get(cache_key)
            if cached:
                return cached

        # Query database
        if entity_id:
            query = "SELECT * FROM entities WHERE id = ?"
            params = (entity_id,)
        else:
            query = "SELECT * FROM entities WHERE type = ? AND name = ?"
            params = (entity_type, name)

        result = self.db.query_one(query, params)

        if result:
            entity = self._row_to_entity(result)
            if use_cache:
                self.cache.put(cache_key, entity)
            return entity

        return None

    def search_entities(
        self,
        entity_type: str,
        query: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        use_embedding: bool = True,
        limit: int = 5
    ) -> List[Entity]:
        """
        Two-stage retrieval:

        Stage 1: Filter by metadata (cheap, fast)
        Stage 2: Embedding similarity (only on filtered results)

        Args:
            entity_type: "spell", "monster", "rule", "item"
            query: Natural language query for embedding search
            filters: Metadata filters (level, cr, tags, domain, etc.)
            use_embedding: Whether to use embedding similarity (Stage 2)
            limit: Max results

        Examples:
            # Exact metadata lookup (Stage 1 only)
            search_entities("spell", filters={"name": "Fireball"})

            # Filtered + semantic search (both stages)
            search_entities(
                "spell",
                query="damage fire spell",
                filters={"level": 3},
                use_embedding=True
            )
        """
        # Stage 1: Metadata filtering (SQL)
        where_clauses = [f"type = '{entity_type}'"]
        params = []

        if filters:
            for key, value in filters.items():
                if key == "tags":
                    # JSON contains
                    where_clauses.append(f"tags LIKE ?")
                    params.append(f'%"{value}"%')
                elif key == "level" or key == "cr":
                    where_clauses.append(f"{key} = ?")
                    params.append(value)
                elif key == "name":
                    where_clauses.append(f"name LIKE ?")
                    params.append(f"%{value}%")
                elif key == "domain" or key == "category":
                    where_clauses.append(f"{key} = ?")
                    params.append(value)

        where_sql = " AND ".join(where_clauses)
        sql_query = f"SELECT id, name, tags FROM entities WHERE {where_sql}"

        candidates = self.db.query(sql_query, tuple(params))

        print(f"Stage 1 (metadata filter): {len(candidates)} candidates")

        # If no query or not using embedding, return metadata results
        if not query or not use_embedding:
            # Fetch full entities
            entity_ids = [c['id'] for c in candidates[:limit]]
            return [
                self.get_entity(entity_type, entity_id=eid)
                for eid in entity_ids
            ]

        # Stage 2: Embedding similarity (only on candidates)
        if len(candidates) == 0:
            return []

        # If very few candidates (< 3), skip embedding
        if len(candidates) <= 2:
            entity_ids = [c['id'] for c in candidates]
            return [
                self.get_entity(entity_type, entity_id=eid)
                for eid in entity_ids
            ]

        # Use vector search within filtered set
        vector_results = self.vector_db.search(
            category=entity_type + "s",
            query=query,
            n_results=min(limit, len(candidates))
        )

        print(f"Stage 2 (embedding): {len(vector_results['ids'])} results")

        # Return entities in ranked order
        entities = []
        for result_id in vector_results['ids']:
            entity = self.get_entity(entity_type, entity_id=result_id)
            if entity:
                entities.append(entity)

        return entities

    def get_spell(self, name: str = None, **filters) -> Optional[Spell]:
        """Get a specific spell (convenience method)"""
        if name:
            filters['name'] = name
        results = self.search_entities("spell", filters=filters, use_embedding=False, limit=1)
        return results[0] if results else None

    def search_spells(self, query: str, level: int = None, school: str = None) -> List[Spell]:
        """Search spells with optional filters"""
        filters = {}
        if level is not None:
            filters['level'] = level
        if school:
            filters['school'] = school

        return self.search_entities("spell", query=query, filters=filters)

    def get_monster(self, name: str = None, **filters) -> Optional[Monster]:
        """Get a specific monster"""
        if name:
            filters['name'] = name
        results = self.search_entities("monster", filters=filters, use_embedding=False, limit=1)
        return results[0] if results else None

    def search_monsters(self, query: str, cr: float = None, size: str = None) -> List[Monster]:
        """Search monsters with optional filters"""
        filters = {}
        if cr is not None:
            filters['cr'] = cr
        if size:
            filters['size'] = size

        return self.search_entities("monster", query=query, filters=filters)

    def get_rule(self, name: str = None, domain: str = None) -> Optional[Rule]:
        """Get a specific rule"""
        filters = {}
        if name:
            filters['name'] = name
        if domain:
            filters['domain'] = domain

        results = self.search_entities("rule", filters=filters, use_embedding=False, limit=1)
        return results[0] if results else None

    def search_rules(self, query: str, domain: str = None) -> List[Rule]:
        """Search rules"""
        filters = {}
        if domain:
            filters['domain'] = domain

        return self.search_entities("rule", query=query, filters=filters)

    def cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return self.cache.stats()

    def _row_to_entity(self, row: Dict) -> Entity:
        """Convert database row to Entity object"""
        entity_type = row['type']

        # Deserialize JSON fields
        tags = json.loads(row.get('tags', '[]'))
        metadata = json.loads(row.get('metadata', '{}'))

        # Create appropriate entity type
        if entity_type == "spell":
            classes = json.loads(row.get('classes', '[]'))
            return Spell(
                id=row['id'],
                type=row['type'],
                name=row['name'],
                tags=tags,
                content=row.get('content', ''),
                metadata=metadata,
                level=row.get('level', 0),
                school=row.get('school', ''),
                classes=classes,
                casting_time=metadata.get('casting_time', ''),
                range=metadata.get('range', ''),
                components=metadata.get('components', ''),
                duration=metadata.get('duration', ''),
                description=row.get('content', ''),
                damage=row.get('damage'),
                save=row.get('save')
            )

        elif entity_type == "monster":
            return Monster(
                id=row['id'],
                type=row['type'],
                name=row['name'],
                tags=tags,
                content=row.get('content', ''),
                metadata=metadata,
                cr=row.get('cr', 0),
                size=row.get('size', 'Medium'),
                type_alignment=metadata.get('type_alignment', ''),
                ac=row.get('ac', 10),
                hp=row.get('hp', '0'),
                speed=metadata.get('speed', '30 ft.'),
                abilities={},
                traits=[],
                actions=[]
            )

        elif entity_type == "rule":
            return Rule(
                id=row['id'],
                type=row['type'],
                name=row['name'],
                tags=tags,
                content=row.get('content', ''),
                metadata=metadata,
                domain=row.get('domain', 'general'),
                category=row.get('category', 'mechanic')
            )

        elif entity_type == "item":
            return Item(
                id=row['id'],
                type=row['type'],
                name=row['name'],
                tags=tags,
                content=row.get('content', ''),
                metadata=metadata,
                rarity=row.get('rarity', 'Common'),
                attunement=metadata.get('attunement', False),
                item_type=row.get('item_type', 'wondrous')
            )

        # Fallback to base Entity
        return Entity(
            id=row['id'],
            type=row['type'],
            name=row['name'],
            tags=tags,
            content=row.get('content', ''),
            metadata=metadata
        )
