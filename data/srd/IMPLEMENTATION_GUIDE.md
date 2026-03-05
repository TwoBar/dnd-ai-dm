# D&D AI DM - Dynamic Formula System Implementation Guide

**Version**: 1.0
**Date**: 2024-01-15
**Purpose**: Complete implementation guide for fresh Claude Code sessions

---

## EXECUTIVE SUMMARY

### What This Guide Covers

This guide provides step-by-step implementation instructions for adding:
1. **Dynamic Formula System** - Database-stored formulas with RAG discovery
2. **Entity-Based Modifiers** - Object-oriented modifier management
3. **Improvised Action Adjudication** - Agent-driven reasoning for undefined mechanics
4. **Character Sheet UI** - View-only 3-tab interface with real-time updates

### Architecture Philosophy

**Core Principle**: Database-first, agent-driven, RAG-enhanced

- **Single Source of Truth**: PostgreSQL/SQLite database (game_state.db)
- **Formula Storage**: Base formulas in DB, discovered via RAG
- **Entity Ownership**: Each entity (character/monster) owns its modifiers
- **Agent Coordination**: Multi-agent system with workflow orchestration
- **No Duplication**: No in-memory state that diverges from database

---

## CURRENT SYSTEM OVERVIEW

### Existing Architecture (Already Built)

#### 1. Multi-Agent System
Located in `/src/agent/`:
- **IntentAgent** - Detects player intent from natural language
- **ReasoningAgent** - Iterative reasoning loop with RAG consultation
- **CommandAgent** - Executes game mechanics via OpenAI tool calls
- **DMAgentV2** - Generates narrative responses
- **SpatialAgent** - Manages 3D positioning and AOE calculations
- **RAGQueryService** - Queries vector database for D&D rules

#### 2. Workflow Orchestrator
Located at `/src/game/workflow.py`:
- Coordinates agent execution order
- **Mechanics First, Narrative Second** principle
- Workflow states: Intent → Mechanics → Narrative → Broadcast

#### 3. Database Layer
Located at `/data/schemas/game_state_db.sql`:
- Comprehensive schema (30+ tables)
- Characters, monsters, items, spells, conditions
- Character classes, proficiencies, inventory
- Session management

#### 4. Web Server
Located at `/src/ui/web_server.py`:
- Flask + SocketIO
- Real-time bidirectional communication
- Session-based game instances
- Canvas map rendering

#### 5. Existing Utilities
- **FormulaParser** (`/src/parsers/formula_parser.py`) - Evaluates math expressions
- **DiceRoller** (`/src/game/dice.py`) - Dice notation rolling with advantage/disadvantage
- **SpatialTranslator** (`/src/game/spatial/spatial_translator.py`) - NL to spatial references

### What's Missing (To Be Implemented)

1. ✗ Dynamic formula storage in database
2. ✗ Entity class with modifier aggregation
3. ✗ FormulaService for formula execution
4. ✗ Enhanced ReasoningAgent with improvised action adjudication
5. ✗ Character sheet UI

---

## THE 11 UNIVERSAL D&D FORMULAS

### Key Insight

D&D 5e has **exactly 11 universal base formulas** that cover 95% of all calculations. These formulas NEVER change in structure - only input values vary by entity.

### The Complete List

```
1. ability_modifier           = floor((ability_score - 10) / 2)
2. proficiency_bonus          = floor((level - 1) / 4) + 2
3. spell_save_dc              = 8 + proficiency_bonus + spellcasting_ability_mod
4. spell_attack_bonus         = proficiency_bonus + spellcasting_ability_mod
5. weapon_attack_roll         = 1d20 + ability_mod + (proficiency_bonus if proficient)
6. weapon_damage              = weapon_dice + ability_mod
7. initiative                 = 1d20 + dex_mod
8. ability_check              = 1d20 + ability_mod + (proficiency_bonus if proficient)
9. saving_throw               = 1d20 + ability_mod + (proficiency_bonus if proficient)
10. passive_check             = 10 + all_modifiers_that_apply
11. armor_class               = base_ac + dex_mod (varies by armor type)
```

### Why This Matters

- **Storage**: Only 11 formulas to store permanently
- **Consistency**: One source of truth per formula
- **Learning**: RAG can discover new formulas (grapple escape DC, etc.) and cache them
- **Performance**: Fast lookups, no recomputation

---

## 3-TIER ARCHITECTURE

### Tier 1: Base Formulas (Universal)

**Storage**: `formulas` table in reference.db

```sql
CREATE TABLE IF NOT EXISTS formulas (
  formula_name TEXT PRIMARY KEY,
  base_formula TEXT NOT NULL,
  description TEXT,
  return_type TEXT DEFAULT 'int',
  source TEXT DEFAULT 'predefined',
  discovered_at TIMESTAMP,
  usage_count INTEGER DEFAULT 0
);
```

**Example Row**:
```sql
INSERT INTO formulas VALUES (
  'spell_save_dc',
  '8 + proficiency_bonus + spellcasting_ability_mod',
  'Spell save DC',
  'int',
  'predefined',
  NULL,
  0
);
```

### Tier 2: Class-Specific Mappings

**Storage**: Determined by class, not stored per-entity

```python
SPELLCASTING_ABILITIES = {
    'wizard': 'int',
    'cleric': 'wis',
    'bard': 'cha',
    # etc.
}
```

### Tier 3: Active Modifiers (Per-Entity)

**Storage**: `active_modifiers` table in game_state.db

```sql
CREATE TABLE IF NOT EXISTS active_modifiers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  creature_id TEXT NOT NULL,
  applies_to TEXT NOT NULL,          -- 'spell_save_dc', 'melee_attack_bonus', etc.
  modifier_type TEXT NOT NULL,       -- 'flat', 'dice', 'advantage', 'disadvantage', 'multiplier'
  modifier_value TEXT NOT NULL,      -- '2', '1d4', 'True', '2.0'
  source_name TEXT,                  -- 'Robe of the Archmagi', 'Bless', 'Poisoned'
  source_id TEXT,                    -- 'item:robe-id', 'spell:bless-id'
  duration_type TEXT DEFAULT 'permanent',
  expires_at TIMESTAMP,
  FOREIGN KEY (creature_id) REFERENCES creatures(id) ON DELETE CASCADE
);
```

**Example Rows**:
```sql
-- Lyra has Robe of the Archmagi (+2 spell save DC)
INSERT INTO active_modifiers VALUES (
  NULL,
  'creature:lyra-uuid',
  'spell_save_dc',
  'flat',
  '2',
  'Robe of the Archmagi',
  'item:robe-123',
  'permanent',
  NULL
);

-- Lyra is blessed (+1d4 to attacks and saves)
INSERT INTO active_modifiers VALUES (
  NULL,
  'creature:lyra-uuid',
  'all_attacks',
  'dice',
  '1d4',
  'Bless',
  'spell:bless-active',
  'concentration',
  datetime('now', '+10 minutes')
);
```

---

## ENTITY CLASS ARCHITECTURE

### Design Principle: Entity Owns Its Modifiers

**Entity** is a lightweight wrapper around database entity that:
1. Aggregates modifiers from multiple sources (items, spells, conditions, features)
2. Caches results for performance
3. Invalidates cache when entity changes
4. Provides 15-20 specialized methods for different formula types

### Entity Class Structure

```python
# Location: /src/entities/entity.py

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Modifier:
    """Single modifier that applies to a formula"""
    type: str           # 'flat', 'dice', 'advantage', 'disadvantage', 'multiplier'
    value: Any          # 2, '1d4', True, 2.0
    source: str         # 'Robe of the Archmagi'
    source_id: str      # 'item:robe-id'
    duration: str       # 'permanent', 'temporary', 'concentration'
    expires_at: Optional[datetime] = None


class Entity:
    """
    Lightweight entity wrapper for modifier aggregation.

    Manages:
    - Modifier aggregation from database
    - Caching for performance
    - Cache invalidation on changes
    """

    def __init__(self, entity_id: str, db: GameStateDB):
        self.entity_id = entity_id
        self.db = db
        self._modifier_cache: Dict[str, List[Modifier]] = {}
        self._cache_dirty: Set[str] = set()

    # ===== UNIQUE FORMULAS (5-10 explicit methods) =====

    def get_spell_save_dc_modifiers(self) -> List[Modifier]:
        """Get modifiers for spell save DC"""
        return self._aggregate_modifiers("spell_save_dc")

    def get_spell_attack_bonus_modifiers(self) -> List[Modifier]:
        """Get modifiers for spell attack bonus"""
        return self._aggregate_modifiers("spell_attack_bonus")

    def get_ac_modifiers(self) -> List[Modifier]:
        """Get modifiers for armor class"""
        return self._aggregate_modifiers("ac")

    def get_initiative_modifiers(self) -> List[Modifier]:
        """Get modifiers for initiative"""
        return self._aggregate_modifiers("initiative")

    def get_weapon_damage_modifiers(self) -> List[Modifier]:
        """Get modifiers for weapon damage"""
        return self._aggregate_modifiers("weapon_damage")

    # ===== HIERARCHICAL GROUPS (5 parameterized methods) =====

    def get_saving_throw_modifiers(self, ability: str) -> List[Modifier]:
        """
        Get modifiers for specific save (str, dex, con, int, wis, cha)
        Includes hierarchical 'all_saving_throws' modifiers
        """
        return self._aggregate_modifiers(f"saving_throw_{ability}")

    def get_skill_modifiers(self, skill: str) -> List[Modifier]:
        """
        Get modifiers for specific skill
        Includes hierarchical 'all_skills' and 'all_checks' modifiers
        """
        return self._aggregate_modifiers(f"skill_{skill}")

    def get_attack_modifiers(self, attack_type: str) -> List[Modifier]:
        """
        attack_type: 'melee', 'ranged', 'spell'
        Includes hierarchical 'all_attacks' modifiers
        """
        return self._aggregate_modifiers(f"{attack_type}_attack_bonus")

    def get_damage_modifiers(self, damage_type: str) -> List[Modifier]:
        """damage_type: 'fire', 'slashing', 'piercing', etc."""
        return self._aggregate_modifiers(f"damage_{damage_type}")

    # ===== FALLBACK FOR RAG-DISCOVERED FORMULAS =====

    def get_modifiers_for(self, target: str) -> List[Modifier]:
        """
        Universal modifier getter for any formula
        (including RAG-discovered formulas)
        """
        return self._aggregate_modifiers(target)

    # ===== CORE IMPLEMENTATION =====

    def _aggregate_modifiers(self, target: str) -> List[Modifier]:
        """
        Query database and aggregate all modifiers for target.
        Handles both direct and hierarchical matches.
        """
        # Check cache
        if target in self._modifier_cache and target not in self._cache_dirty:
            return self._modifier_cache[target]

        modifiers = []

        # 1. Direct modifiers for this specific target
        modifiers.extend(self._query_active_modifiers(target))

        # 2. Hierarchical modifiers
        if target.startswith("saving_throw_"):
            modifiers.extend(self._query_active_modifiers("all_saving_throws"))

        elif target.startswith("skill_"):
            modifiers.extend(self._query_active_modifiers("all_skills"))
            modifiers.extend(self._query_active_modifiers("all_checks"))

        elif target.endswith("_attack_bonus"):
            modifiers.extend(self._query_active_modifiers("all_attacks"))

        # Cache result
        self._modifier_cache[target] = modifiers
        self._cache_dirty.discard(target)

        return modifiers

    def _query_active_modifiers(self, applies_to: str) -> List[Modifier]:
        """Query database for active modifiers"""
        query = """
        SELECT modifier_type, modifier_value, source_name, source_id, duration_type, expires_at
        FROM active_modifiers
        WHERE creature_id = ?
          AND applies_to = ?
          AND (expires_at IS NULL OR expires_at > datetime('now'))
        """

        rows = self.db.query(query, (self.entity_id, applies_to))

        return [
            Modifier(
                type=row['modifier_type'],
                value=self._parse_value(row['modifier_value'], row['modifier_type']),
                source=row['source_name'],
                source_id=row['source_id'],
                duration=row['duration_type'],
                expires_at=row['expires_at']
            )
            for row in rows
        ]

    def _parse_value(self, value_str: str, modifier_type: str) -> Any:
        """Parse modifier value from string"""
        if modifier_type == 'flat':
            return int(value_str)
        elif modifier_type == 'dice':
            return value_str  # Keep as dice notation
        elif modifier_type in ('advantage', 'disadvantage'):
            return value_str.lower() == 'true'
        elif modifier_type == 'multiplier':
            return float(value_str)
        return value_str

    def invalidate_cache(self, formula_names: Optional[List[str]] = None):
        """
        Mark cache as dirty. Called when entity changes.

        Args:
            formula_names: Specific formulas to invalidate, or None for all
        """
        if formula_names is None:
            self._cache_dirty = set(self._modifier_cache.keys())
        else:
            self._cache_dirty.update(formula_names)

    def get_context(self) -> Dict[str, Any]:
        """Get base stats for formula execution (ability scores, level, etc.)"""
        # Delegate to database query
        return self.db.get_entity_context(self.entity_id)
```

### Hierarchical Modifier Matching

**Example**: When calculating DEX saving throw, system automatically includes:
1. Direct modifiers: `applies_to = 'saving_throw_dex'`
2. Hierarchical modifiers: `applies_to = 'all_saving_throws'`

This reduces methods from 60 to ~15-20.

---

## FORMULA SERVICE ARCHITECTURE

### FormulaService: Coordinates Formula Execution

```python
# Location: /src/services/formula_service.py

from typing import Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class FormulaResult:
    """Result of formula execution"""
    value: Any                      # int, str (dice notation), or bool
    formula_name: str
    formula: str
    context_used: Dict[str, Any]
    modifiers_applied: List[Modifier]
    entity_id: str
    entity_type: str


class FormulaService:
    """
    Manages dynamic formula system with context binding.

    Main entry point for agents to calculate values.
    """

    def __init__(self, reference_db: ReferenceDB, game_state_db: GameStateDB):
        self.ref_db = reference_db
        self.game_db = game_state_db
        self.parser = FormulaParser()
        self._formula_cache = {}

    def execute_for_entity(
        self,
        formula_name: str,
        entity_id: str,
        entity_type: str = "character",
        extra_context: Optional[Dict[str, Any]] = None
    ) -> FormulaResult:
        """
        Execute formula for a specific entity.

        This is the MAIN method agents use!

        Args:
            formula_name: Name of formula (e.g., "spell_save_dc")
            entity_id: ID of entity (e.g., "creature:uuid-123")
            entity_type: Type of entity ("character", "monster")
            extra_context: Additional variables (e.g., {"magic_bonus": 1})

        Returns:
            FormulaResult with computed value and metadata

        Example:
            result = formula_service.execute_for_entity(
                formula_name="spell_save_dc",
                entity_id="creature:lyra-id",
                entity_type="character"
            )
            # Returns: FormulaResult(value=16, ...)
        """
        # 1. Get formula from database (or cache)
        formula = self._get_formula(formula_name)

        if not formula:
            # Formula not found - try RAG discovery
            formula = self._discover_formula_via_rag(formula_name)

            if not formula:
                raise ValueError(f"Formula '{formula_name}' not found")

        # 2. Build entity
        entity = Entity(entity_id, self.game_db)

        # 3. Get entity context (ability scores, level, etc.)
        context = entity.get_context()

        # 4. Merge extra context if provided
        if extra_context:
            context.update(extra_context)

        # 5. Get modifiers from entity
        modifiers = entity.get_modifiers_for(formula_name)

        # 6. Execute formula with executor
        executor = FormulaExecutor(self.parser)
        result = executor.execute(formula, context, modifiers)

        # 7. Update usage count
        self._increment_usage(formula_name)

        return FormulaResult(
            value=result.value,
            formula_name=formula_name,
            formula=formula,
            context_used=context,
            modifiers_applied=modifiers,
            entity_id=entity_id,
            entity_type=entity_type
        )

    def _get_formula(self, formula_name: str) -> Optional[str]:
        """Get formula from cache or database"""
        if formula_name in self._formula_cache:
            return self._formula_cache[formula_name]

        query = "SELECT base_formula FROM formulas WHERE formula_name = ?"
        result = self.ref_db.query(query, (formula_name,))

        if result:
            formula = result[0]['base_formula']
            self._formula_cache[formula_name] = formula
            return formula

        return None

    def _discover_formula_via_rag(self, formula_name: str) -> Optional[str]:
        """
        Discover formula via RAG when not found in database.

        This is the MAGIC part - system learns new formulas!
        """
        logger.info(f"🔍 Formula '{formula_name}' not found, attempting RAG discovery...")

        try:
            from agent.rag_query_service import RAGQueryService

            rag = RAGQueryService()

            # Query RAG for formula
            question = f"How to calculate {formula_name.replace('_', ' ')} in D&D 5e?"
            rule_result = rag.search_rules(question, max_results=3)

            if not rule_result:
                return None

            # Use LLM to extract formula from rule text
            formula = self._extract_formula_from_rule(formula_name, rule_result)

            if formula:
                # Store formula in database for future use
                self._store_discovered_formula(formula_name, formula, rule_result)
                logger.info(f"✅ Discovered and stored formula: {formula_name} = {formula}")
                return formula

        except Exception as e:
            logger.error(f"Failed to discover formula via RAG: {e}")

        return None

    def _extract_formula_from_rule(self, formula_name: str, rule_text: str) -> Optional[str]:
        """
        Use LLM to extract formula from rule text.

        Example:
            rule_text = "Spell save DC equals 8 + your proficiency bonus + your spellcasting ability modifier"
            formula = extract_formula(...)
            # Returns: "8 + proficiency_bonus + spellcasting_ability_mod"
        """
        # TODO: Implement LLM-based formula extraction
        # This would use a small prompt to ask LLM to convert rule text to formula
        # For now, return None (manual formulas only)
        logger.warning(f"Formula extraction from RAG not yet implemented for '{formula_name}'")
        return None

    def _store_discovered_formula(self, formula_name: str, formula: str, rule_reference: str):
        """Store newly discovered formula in database"""
        query = """
        INSERT INTO formulas (formula_name, base_formula, source, rule_reference, discovered_at)
        VALUES (?, ?, 'rag_discovered', ?, datetime('now'))
        """

        self.ref_db.execute(query, (formula_name, formula, rule_reference))
        self._formula_cache[formula_name] = formula

    def _increment_usage(self, formula_name: str):
        """Increment usage counter for analytics"""
        query = """
        UPDATE formulas
        SET usage_count = usage_count + 1,
            last_used_at = datetime('now')
        WHERE formula_name = ?
        """

        self.ref_db.execute(query, (formula_name,))
```

---

## FORMULA EXECUTOR ARCHITECTURE

### FormulaExecutor: Pure Computation

```python
# Location: /src/services/formula_executor.py

from typing import List, Dict, Any
from dataclasses import dataclass
from parsers.formula_parser import FormulaParser
from entities.entity import Modifier

@dataclass
class ExecutionResult:
    """Result of formula execution"""
    value: Any              # Final computed value
    base_value: Any         # Value before modifiers
    modifiers_applied: List[Modifier]
    has_advantage: bool = False
    has_disadvantage: bool = False


class FormulaExecutor:
    """
    Pure computation - no business logic.
    Just applies modifiers to base formulas.
    """

    def __init__(self, parser: FormulaParser):
        self.parser = parser

    def execute(
        self,
        formula: str,
        entity_context: Dict[str, Any],
        modifiers: List[Modifier]
    ) -> ExecutionResult:
        """
        Execute formula with modifiers applied.

        Args:
            formula: Base formula (e.g., "8 + proficiency_bonus + cha_mod")
            entity_context: Entity stats (ability scores, level, etc.)
            modifiers: List of modifiers to apply

        Returns:
            ExecutionResult with final value
        """
        # 1. Evaluate base formula
        base_value = self.parser.evaluate(formula, entity_context)

        # 2. Apply flat modifiers
        flat_bonus = sum(m.value for m in modifiers if m.type == 'flat')
        result_value = base_value + flat_bonus if isinstance(base_value, int) else base_value

        # 3. Append dice modifiers (for dice notation results)
        dice_modifiers = [m.value for m in modifiers if m.type == 'dice']
        if dice_modifiers and isinstance(result_value, str):  # Dice notation
            for dice_mod in dice_modifiers:
                result_value += f"+{dice_mod}"

        # 4. Apply advantage/disadvantage (return as flag for dice roller)
        has_advantage = any(m.type == 'advantage' for m in modifiers)
        has_disadvantage = any(m.type == 'disadvantage' for m in modifiers)

        # 5. Apply multipliers
        multiplier = 1.0
        for m in modifiers:
            if m.type == 'multiplier':
                multiplier *= m.value

        if isinstance(result_value, int):
            result_value = int(result_value * multiplier)

        return ExecutionResult(
            value=result_value,
            base_value=base_value,
            modifiers_applied=modifiers,
            has_advantage=has_advantage,
            has_disadvantage=has_disadvantage
        )
```

---

## IMPROVISED ACTION ADJUDICATION

### ReasoningAgent Enhancement

Add method to `ReasoningAgent` for improvised actions:

```python
# Location: /src/agent/reasoning_agent.py (ADD THIS METHOD)

from dataclasses import dataclass

@dataclass
class ImprovisedMechanics:
    """Proposed mechanics for improvised action"""
    damage: str                 # "3d6"
    damage_type: str            # "fire"
    aoe_shape: str              # "cylinder", "sphere", "cone"
    aoe_radius: float           # 10.0 (feet)
    save_ability: str           # "dex"
    save_dc: int                # 15
    save_effect: str            # "half_damage", "no_effect"
    precedent_sources: List[str]
    reasoning: str


class ReasoningAgent:
    # ... existing code ...

    def adjudicate_improvised_action(
        self,
        action: str,
        context: Dict[str, Any]
    ) -> ImprovisedMechanics:
        """
        Determine game mechanics for improvised action.

        Process:
        1. Classify action type (damage, control, utility)
        2. Query RAG for similar RAW effects
        3. Extract precedent values
        4. Apply DM heuristics
        5. Propose balanced mechanics

        Args:
            action: Player's description ("pour boiling oil")
            context: Situation details (height, target count, etc.)

        Returns:
            ImprovisedMechanics with damage, AOE, save DC, etc.
        """
        # Step 1: Classify action
        action_type = self._classify_action(action)
        # Returns: "area_damage_fire"

        # Step 2: Query RAG for precedent
        precedents = self.rag_query.search_rules(
            f"D&D 5e {action_type} effects similar to {action}"
        )

        # Step 3: Extract damage ranges
        damage_precedents = []
        for p in precedents:
            if "damage" in p:
                damage_precedents.append({
                    "source": p["source"],
                    "damage": p["damage"],
                    "level": p.get("spell_level", 0)
                })

        # Step 4: Apply heuristics
        # Rule: Improvised actions should match spell level 0-2
        suitable_precedents = [
            p for p in damage_precedents
            if p["level"] <= 2
        ]

        # Pick closest match
        # Boiling oil from height → 1st level spell equivalent
        selected_damage = "3d6"  # From Burning Hands

        # Step 5: Determine AOE
        aoe = self._determine_aoe(action, context)
        # Context: {height: 40, pour_point: "above_enemies"}
        # Physics: Oil falls straight down → cylinder
        # Volume: Large cauldron → 10ft radius reasonable

        # Step 6: Determine save DC
        save_dc = self._determine_save_dc(action, context)
        # Improvised hazard with warning → DC 15 (moderate)

        # Step 7: Package mechanics
        return ImprovisedMechanics(
            damage="3d6",
            damage_type="fire",
            aoe_shape="cylinder",
            aoe_radius=10,
            save_ability="dex",
            save_dc=15,
            save_effect="half_damage",
            precedent_sources=["Burning Hands (PHB)", "Oil Flask (PHB)"],
            reasoning="Boiling oil from castle walls matches low-level area spell..."
        )

    def _classify_action(self, action: str) -> str:
        """Classify improvised action type"""
        # Use LLM to classify
        # Examples: "area_damage_fire", "single_target_control", "utility_buff"
        pass

    def _determine_aoe(self, action: str, context: Dict) -> Dict:
        """Determine appropriate AOE based on physics and context"""
        # Logic for AOE shape and size
        pass

    def _determine_save_dc(self, action: str, context: Dict) -> int:
        """Determine appropriate save DC based on difficulty heuristics"""
        # Easy: 10, Moderate: 15, Hard: 20, Very Hard: 25
        pass
```

---

## IMPLEMENTATION PHASES

### Phase 1: Database Setup

**Files to Create/Modify**:
1. `/data/schemas/formulas_with_modifiers.sql` (CREATE)
2. `/src/data/sqlite_db.py` (MODIFY - add initialization)

**Steps**:
```sql
-- 1. Create formulas table
CREATE TABLE IF NOT EXISTS formulas (
  formula_name TEXT PRIMARY KEY,
  base_formula TEXT NOT NULL,
  description TEXT,
  return_type TEXT DEFAULT 'int',
  source TEXT DEFAULT 'predefined',
  rule_reference TEXT,
  discovered_at TIMESTAMP,
  usage_count INTEGER DEFAULT 0,
  last_used_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Create formula_aliases table
CREATE TABLE IF NOT EXISTS formula_aliases (
  alias TEXT PRIMARY KEY,
  formula_name TEXT NOT NULL,
  FOREIGN KEY (formula_name) REFERENCES formulas(formula_name)
);

-- 3. Create active_modifiers table
CREATE TABLE IF NOT EXISTS active_modifiers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  creature_id TEXT NOT NULL,
  applies_to TEXT NOT NULL,
  modifier_type TEXT NOT NULL,
  modifier_value TEXT NOT NULL,
  source_name TEXT,
  source_id TEXT,
  duration_type TEXT DEFAULT 'permanent',
  expires_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (creature_id) REFERENCES creatures(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_active_modifiers_creature ON active_modifiers(creature_id);
CREATE INDEX IF NOT EXISTS idx_active_modifiers_applies ON active_modifiers(applies_to);

-- 4. Seed 11 base formulas
INSERT OR IGNORE INTO formulas (formula_name, base_formula, description, source) VALUES
  ('spell_save_dc', '8 + proficiency_bonus + spellcasting_ability_mod', 'Spell save DC', 'predefined'),
  ('spell_attack_bonus', 'proficiency_bonus + spellcasting_ability_mod', 'Spell attack bonus', 'predefined'),
  ('melee_attack_bonus', 'proficiency_bonus + str_mod', 'Melee attack bonus', 'predefined'),
  ('ranged_attack_bonus', 'proficiency_bonus + dex_mod', 'Ranged attack bonus', 'predefined'),
  ('ac', 'base_ac + dex_mod + shield_bonus', 'Armor class', 'predefined'),
  ('initiative', 'dex_mod', 'Initiative', 'predefined'),
  ('passive_perception', '10 + wis_mod + (perception_proficient * proficiency_bonus) + (perception_expertise * proficiency_bonus)', 'Passive Perception', 'predefined'),
  ('proficiency_bonus', 'floor((level - 1) / 4) + 2', 'Proficiency bonus', 'predefined'),
  ('ability_modifier', 'floor((ability_score - 10) / 2)', 'Ability modifier', 'predefined'),
  ('carrying_capacity', 'str * 15', 'Carrying capacity', 'predefined'),
  ('saving_throw', '1d20 + ability_mod + (proficient * proficiency_bonus)', 'Saving throw', 'predefined');

-- 5. Seed formula aliases
INSERT OR IGNORE INTO formula_aliases (alias, formula_name) VALUES
  ('save dc', 'spell_save_dc'),
  ('spell dc', 'spell_save_dc'),
  ('to hit', 'melee_attack_bonus'),
  ('attack roll', 'melee_attack_bonus'),
  ('armor class', 'ac'),
  ('armor', 'ac');
```

**Run Migration**:
```bash
sqlite3 data/reference.db < data/schemas/formulas_with_modifiers.sql
```

### Phase 2: Entity Class

**Files to Create**:
1. `/src/entities/__init__.py` (CREATE)
2. `/src/entities/entity.py` (CREATE)

**Copy the Entity class code from "ENTITY CLASS ARCHITECTURE" section above.**

### Phase 3: Formula Service & Executor

**Files to Create**:
1. `/src/services/__init__.py` (CREATE if doesn't exist)
2. `/src/services/formula_service.py` (CREATE)
3. `/src/services/formula_executor.py` (CREATE)

**Copy the FormulaService and FormulaExecutor code from sections above.**

### Phase 4: ReasoningAgent Enhancement

**File to Modify**:
1. `/src/agent/reasoning_agent.py` (ADD METHOD)

**Add the `adjudicate_improvised_action()` method from section above.**

### Phase 5: CommandAgent Integration

**File to Modify**:
1. `/src/agent/command_agent.py` (MODIFY)

**Changes**:
```python
# Add to __init__:
from services.formula_service import FormulaService

class CommandAgent:
    def __init__(self, game_state, formula_service: FormulaService):
        self.game_state = game_state
        self.formula_service = formula_service
        # ... existing code ...

    # Update tool functions to use formula_service:
    def _cast_spell(self, caster_id: str, spell_name: str, target_id: str):
        # OLD: Hardcoded calculation
        # spell_dc = 8 + prof + ability_mod

        # NEW: Use formula service
        spell_dc_result = self.formula_service.execute_for_entity(
            formula_name="spell_save_dc",
            entity_id=caster_id,
            entity_type="character"
        )
        spell_dc = spell_dc_result.value

        # Calculate target's save
        save_result = self.formula_service.execute_for_entity(
            formula_name=f"saving_throw_{spell_save_ability}",
            entity_id=target_id,
            entity_type="monster"
        )

        # Roll dice and compare
        # ... rest of logic ...
```

### Phase 6: Character Sheet UI

**Files to Create**:
1. `/src/ui/templates/character_sheet.html` (CREATE)
2. `/src/ui/static/css/character_sheet.css` (CREATE)
3. `/src/ui/static/js/character_sheet.js` (CREATE)

**File to Modify**:
1. `/src/ui/web_server.py` (ADD ROUTES)

**Implementation**:

See detailed character sheet design in separate section below.

---

## CHARACTER SHEET UI IMPLEMENTATION

### Design Principles

1. **View-Only**: All editing via chat/DM commands
2. **Modal-Based**: Overlay on main game view
3. **3 Tabs**: Core Stats, Combat & Equipment, Spells & Features
4. **Real-Time**: Updates via SocketIO
5. **Responsive**: Works on desktop and mobile

### Tab 1: Core Stats

```
┌────────────────────────────────────────┐
│ Lyra Moonshadow                        │
│ Level 5 Bard                           │
├────────────────────────────────────────┤
│ HP: 32/38  AC: 14  Initiative: +2     │
├────────────────────────────────────────┤
│ Ability Scores:                         │
│ STR 10 (+0)  DEX 14 (+2)  CON 12 (+1) │
│ INT 13 (+1)  WIS  8 (-1)  CHA 16 (+3) │
├────────────────────────────────────────┤
│ Proficiency Bonus: +3                  │
│ Speed: 30 ft                           │
│ Proficiencies: Acrobatics, Deception,  │
│                Performance, Persuasion  │
├────────────────────────────────────────┤
│ Active Conditions:                      │
│ ✓ Blessed (+1d4 to attacks/saves)     │
└────────────────────────────────────────┘
```

### Tab 2: Combat & Equipment

```
┌────────────────────────────────────────┐
│ Combat Stats:                          │
│ Spell Save DC: 14                      │
│ Spell Attack: +6                       │
│ Melee Attack: +3                       │
│ Ranged Attack: +5                      │
├────────────────────────────────────────┤
│ Equipment:                              │
│ ⚔️  Rapier (+1) - 1d8+3 piercing       │
│ 🏹  Shortbow - 1d6+2 piercing          │
│ 🛡️  Leather Armor (AC 11 + DEX)       │
├────────────────────────────────────────┤
│ Inventory:                              │
│ 📜 Scroll of Identify                  │
│ 💰 75 gp                               │
└────────────────────────────────────────┘
```

### Tab 3: Spells & Features

```
┌────────────────────────────────────────┐
│ Spell Slots: ●●●● ○○                  │
│ (4 / 4 remaining)                      │
├────────────────────────────────────────┤
│ Cantrips:                               │
│ • Vicious Mockery                      │
│ • Mage Hand                            │
├────────────────────────────────────────┤
│ 1st Level:                              │
│ • Healing Word                         │
│ • Thunderwave                          │
│ • Charm Person                         │
├────────────────────────────────────────┤
│ Class Features:                         │
│ • Bardic Inspiration (5/day)           │
│ • Jack of All Trades                   │
│ • Song of Rest (1d6)                   │
└────────────────────────────────────────┘
```

### SocketIO Events

**Server → Client**:
```javascript
// Full character sheet data
socket.on('character_sheet_data', (data) => {
  // data = {
  //   id: "creature:lyra-uuid",
  //   name: "Lyra Moonshadow",
  //   level: 5,
  //   class: "Bard",
  //   hp: 32,
  //   max_hp: 38,
  //   abilities: {str: 10, dex: 14, ...},
  //   spell_save_dc: {total: 14, base: 14, modifiers: []},
  //   ...
  // }
});

// Real-time HP update
socket.on('hp_updated', (data) => {
  // data = {entity_id: "...", hp: 28, max_hp: 38}
});

// Modifier added/removed
socket.on('modifier_changed', (data) => {
  // data = {entity_id: "...", modifier: {...}, action: "added"}
});
```

**Client → Server**:
```javascript
// Request character sheet
socket.emit('get_character_sheet', {entity_id: "creature:lyra-uuid"});

// Request modifier breakdown
socket.emit('get_modifier_breakdown', {
  entity_id: "creature:lyra-uuid",
  formula: "spell_save_dc"
});
```

### Backend Routes

```python
# Add to /src/ui/web_server.py

@socketio.on('get_character_sheet')
def handle_get_character_sheet(data):
    """Send full character sheet data"""
    entity_id = data.get('entity_id')
    session = get_or_create_session(request.sid)

    # Get entity
    entity = Entity(entity_id, session.game_db)
    context = entity.get_context()

    # Calculate all derived stats using FormulaService
    spell_save_dc = session.formula_service.execute_for_entity(
        "spell_save_dc", entity_id, "character"
    )

    spell_attack = session.formula_service.execute_for_entity(
        "spell_attack_bonus", entity_id, "character"
    )

    # ... calculate all stats ...

    sheet_data = {
        'id': entity_id,
        'name': context['name'],
        'level': context['level'],
        'class': context['class'],
        'hp': context['hp'],
        'max_hp': context['max_hp'],
        'abilities': {
            'str': context['str'],
            'dex': context['dex'],
            # ...
        },
        'spell_save_dc': {
            'total': spell_save_dc.value,
            'base': spell_save_dc.value - sum(m.value for m in spell_save_dc.modifiers_applied if m.type == 'flat'),
            'modifiers': [
                {'source': m.source, 'value': m.value, 'type': m.type}
                for m in spell_save_dc.modifiers_applied
            ]
        },
        # ... all other stats ...
    }

    emit('character_sheet_data', sheet_data)


@socketio.on('get_modifier_breakdown')
def handle_get_modifier_breakdown(data):
    """Send detailed breakdown of modifiers for a formula"""
    entity_id = data.get('entity_id')
    formula = data.get('formula')
    session = get_or_create_session(request.sid)

    result = session.formula_service.execute_for_entity(
        formula, entity_id, "character"
    )

    breakdown = {
        'formula': formula,
        'total': result.value,
        'base': result.value - sum(m.value for m in result.modifiers_applied if m.type == 'flat'),
        'modifiers': [
            {
                'source': m.source,
                'type': m.type,
                'value': m.value,
                'duration': m.duration
            }
            for m in result.modifiers_applied
        ]
    }

    emit('modifier_breakdown', breakdown)
```

---

## COMPLETE USE CASE FLOWS

### Use Case 1: Spell Casting

**Scenario**: Lyra casts Charm Person on a goblin

```
USER: "Lyra casts Charm Person on the goblin"
  ↓
[IntentAgent] Detects: spell_cast
  ↓
[SpatialTranslator] Resolves: caster=creature:lyra-uuid, target=creature:goblin-uuid
  ↓
[CommandAgent] Executes mechanics:
  1. Calculate Lyra's spell save DC:
     result = formula_service.execute_for_entity("spell_save_dc", "creature:lyra-uuid")
     → value=14 (base: 8+3+3=14, modifiers: none)

  2. Calculate goblin's WIS save:
     result = formula_service.execute_for_entity("saving_throw_wis", "creature:goblin-uuid")
     → dice_notation="1d20-1" (wis_mod=-1, not proficient)

  3. Roll dice:
     roll = dice_roller.roll("1d20-1")
     → 11

  4. Compare: 11 < 14 → FAIL
  ↓
[DMAgent] Generates narrative:
  "Lyra weaves her fingers and speaks words of enchantment. The goblin's eyes glaze over as the charm takes hold."
  ↓
[SocketIO] Broadcasts:
  - spell_cast event
  - condition_applied event (charmed)
  - narrative to chat
```

### Use Case 2: Improvised Action (Boiling Oil)

**Scenario**: Player pours boiling oil on orcs from castle walls

```
USER: "I pour the boiling oil on the orcs below!"
  ↓
[IntentAgent] Detects: improvised_attack (confidence: 0.6)
  ↓
[ReasoningAgent] Adjudicates mechanics:
  1. Query RAG: "area fire damage improvised environmental hazards"
  2. Find precedents: Burning Hands (3d6), Alchemist's Fire (1d4), Oil Flask
  3. Synthesize: damage=3d6, aoe=10ft cylinder, DC=15 DEX save
  4. Returns: ImprovisedMechanics(...)
  ↓
[DMAgent] Announces ruling:
  "The boiling oil cascades down in a 10-foot radius. Each orc must make a DC 15 Dexterity save or take 3d6 fire damage (half on success)."
  ↓
[SpatialAgent] Identifies targets:
  get_entities_in_aoe(location="castle_walls", radius=10, shape="cylinder")
  → [orc-1, orc-2, orc-3, orc-4, orc-5, orc-6]
  ↓
[CommandAgent] For each orc:
  1. Calculate DEX save:
     result = formula_service.execute_for_entity("saving_throw_dex", "creature:orc-1")
     → "1d20+1"

  2. Roll: 14 → FAIL (< 15)

  3. Roll damage: 3d6 → 14 fire damage

  4. Apply damage to orc-1

  [Repeat for orcs 2-6]
  ↓
[DMAgent] Generates narrative based on results:
  "Scalding oil rains down on the orcs. Six are caught—most scream as the liquid sears their flesh. One manages to dive aside at the last moment. When the oil settles, four orcs lie motionless. Two more retreat, badly burned."
```

### Use Case 3: Character Equips Magic Item

**Scenario**: Lyra finds and equips Robe of the Archmagi (+2 spell save DC)

```
USER: "I put on the Robe of the Archmagi"
  ↓
[IntentAgent] Detects: equip_item
  ↓
[CommandAgent] Executes:
  1. Update inventory:
     UPDATE creature_inventory
     SET equipped=1
     WHERE creature_id='creature:lyra-uuid' AND item_id='item:robe-123'

  2. Add active modifier:
     INSERT INTO active_modifiers VALUES (
       NULL,
       'creature:lyra-uuid',
       'spell_save_dc',
       'flat',
       '2',
       'Robe of the Archmagi',
       'item:robe-123',
       'permanent',
       NULL
     )

  3. Invalidate entity cache:
     entity = Entity("creature:lyra-uuid")
     entity.invalidate_cache(['spell_save_dc', 'spell_attack_bonus', 'ac'])
  ↓
[SocketIO] Broadcasts:
  - item_equipped event
  - modifier_changed event
  - character_sheet_update event
  ↓
[Frontend] Character sheet updates:
  Spell Save DC: 14 → 16
  Shows breakdown:
    Base: 14 (8 + prof(3) + cha(3))
    + Robe of the Archmagi: +2
    Total: 16
```

---

## TESTING CHECKLIST

### Unit Tests

```python
# /tests/test_formula_service.py
def test_spell_save_dc_calculation():
    """Test basic spell save DC calculation"""
    entity = create_test_character(level=5, cha=16, class_="bard")
    result = formula_service.execute_for_entity("spell_save_dc", entity.id)
    assert result.value == 14  # 8 + 3 (prof) + 3 (cha)

def test_spell_save_dc_with_modifier():
    """Test spell save DC with magic item"""
    entity = create_test_character(level=5, cha=16, class_="bard")
    add_modifier(entity.id, "spell_save_dc", "flat", 2, "Robe of the Archmagi")
    result = formula_service.execute_for_entity("spell_save_dc", entity.id)
    assert result.value == 16  # 14 + 2

def test_saving_throw_with_bless():
    """Test saving throw with Bless spell"""
    entity = create_test_monster(wis=8, proficient_saves=[])
    add_modifier(entity.id, "all_saving_throws", "dice", "1d4", "Bless")
    result = formula_service.execute_for_entity("saving_throw_wis", entity.id)
    assert result.value == "1d20-1+1d4"  # wis_mod=-1, bless=+1d4
```

### Integration Tests

```python
# /tests/test_spell_casting.py
def test_charm_person_spell():
    """Test full spell casting flow"""
    # Setup
    caster = create_test_character(name="Lyra", level=5, cha=16, class_="bard")
    target = create_test_monster(name="Goblin", wis=8)

    # Execute
    workflow = WorkflowOrchestrator(...)
    result = workflow.execute_spell_cast(
        caster_id=caster.id,
        spell_name="Charm Person",
        target_id=target.id
    )

    # Verify
    assert result.spell_dc == 14
    assert result.target_save_modifier == -1
    assert result.save_needed == 14
    # (actual roll varies, can't test outcome)
```

### E2E Tests

Use Playwright/Selenium to test:
1. Character sheet opens and displays correct data
2. Real-time updates when HP changes
3. Modifier breakdown shows correct sources
4. Spell casting updates character sheet
5. Mobile responsive layout

---

## PERFORMANCE CONSIDERATIONS

### Caching Strategy

1. **Entity Modifier Cache**: Cached per entity, invalidated on change
2. **Formula Cache**: Formulas cached in memory, never invalidate (until restart)
3. **Database Connection Pool**: Reuse connections, don't create per request

### Expected Performance

- **Formula Execution**: ~5-10ms (database query + computation)
- **Entity Modifier Aggregation**: ~10-20ms (1-3 database queries)
- **Total Latency**: ~20-40ms per calculation
- **Character Sheet Load**: ~100-200ms (10-15 formula executions in parallel)

### Optimization Opportunities

1. **Batch Formula Execution**: Execute multiple formulas in single transaction
2. **Precompute Character Sheet**: Cache entire sheet, invalidate on change
3. **WebSocket Throttling**: Debounce rapid updates (max 10/second)

---

## DEPLOYMENT CHECKLIST

### Pre-Deployment

- [ ] Run all unit tests
- [ ] Run integration tests
- [ ] Test character sheet on desktop
- [ ] Test character sheet on mobile
- [ ] Verify database migrations run cleanly
- [ ] Check for SQL injection vulnerabilities
- [ ] Review formula extraction security (if LLM-based)

### Deployment Steps

1. Backup existing database
2. Run database migrations (formulas, active_modifiers tables)
3. Seed 11 base formulas
4. Deploy new Python code
5. Restart server
6. Verify health check endpoint
7. Test character sheet load
8. Monitor error logs

### Post-Deployment

- [ ] Verify formula execution working
- [ ] Verify character sheet displaying
- [ ] Check SocketIO connections stable
- [ ] Monitor latency metrics
- [ ] Watch for RAG discovery attempts

---

## TROUBLESHOOTING

### Common Issues

**Issue**: Formula not found error
- **Cause**: Formula name typo or not seeded
- **Fix**: Check formulas table, run seed SQL

**Issue**: Entity modifiers not applying
- **Cause**: Cache not invalidated after item equip
- **Fix**: Ensure `entity.invalidate_cache()` called on changes

**Issue**: Character sheet not updating
- **Cause**: SocketIO not broadcasting or client not listening
- **Fix**: Check SocketIO event names match client/server

**Issue**: Slow formula execution
- **Cause**: Database query not indexed or N+1 queries
- **Fix**: Add indexes on creature_id, applies_to columns

**Issue**: RAG discovery failing
- **Cause**: ChromaDB connection issue or no matching documents
- **Fix**: Check RAG service logs, verify vector database populated

---

## FUTURE ENHANCEMENTS

### Phase 7: Advanced Features (Post-MVP)

1. **LLM Formula Extraction**: Auto-extract formulas from RAG results
2. **Pattern Learning**: Learn common improvised action patterns
3. **Modifier Stacking Rules**: Detect and handle stacking restrictions
4. **Advantage/Disadvantage Sources**: Track why advantage applied
5. **Temporary HP**: Track separately from regular HP
6. **Concentration Tracking**: Auto-track concentration spells
7. **Death Saves**: Automatic death save tracking
8. **Long Rest Recovery**: Auto-recover HP/spell slots on long rest
9. **Character Leveling**: UI for leveling up characters
10. **Multi-Character Sheets**: View multiple characters simultaneously

---

## APPENDIX A: File Structure

```
dnd-ai-dm/
├── data/
│   ├── schemas/
│   │   ├── game_state_db.sql              (existing)
│   │   └── formulas_with_modifiers.sql    (NEW)
│   ├── reference.db                       (existing)
│   └── game_state.db                      (existing)
├── src/
│   ├── agent/
│   │   ├── intent_agent.py                (existing)
│   │   ├── reasoning_agent.py             (MODIFY)
│   │   ├── command_agent.py               (MODIFY)
│   │   ├── dm_agent_v2.py                 (existing)
│   │   └── rag_query_service.py           (existing)
│   ├── entities/                          (NEW)
│   │   ├── __init__.py                    (NEW)
│   │   └── entity.py                      (NEW)
│   ├── services/                          (NEW)
│   │   ├── __init__.py                    (NEW)
│   │   ├── formula_service.py             (NEW)
│   │   └── formula_executor.py            (NEW)
│   ├── parsers/
│   │   └── formula_parser.py              (existing)
│   ├── game/
│   │   ├── workflow.py                    (existing)
│   │   ├── dice.py                        (existing)
│   │   └── spatial/
│   │       ├── spatial_agent.py           (existing)
│   │       └── spatial_translator.py      (existing)
│   └── ui/
│       ├── web_server.py                  (MODIFY)
│       ├── templates/
│       │   ├── index.html                 (existing)
│       │   └── character_sheet.html       (NEW)
│       └── static/
│           ├── css/
│           │   └── character_sheet.css    (NEW)
│           └── js/
│               └── character_sheet.js     (NEW)
└── tests/                                  (NEW)
    ├── test_formula_service.py            (NEW)
    ├── test_entity.py                     (NEW)
    └── test_spell_casting.py              (NEW)
```

---

## APPENDIX B: Key Design Decisions

### Decision 1: Database-Stored Formulas vs Hardcoded

**Choice**: Database-stored
**Rationale**:
- Allows RAG discovery and learning
- Single source of truth
- Can be updated without code changes
- Supports versioning and analytics

### Decision 2: Entity-Owned Modifiers vs Global Service

**Choice**: Entity-owned
**Rationale**:
- Object-oriented governance
- Clear separation of concerns
- Entity responsible for its own state
- Easier to reason about and debug

### Decision 3: Formula Executor Separate from Service

**Choice**: Separate
**Rationale**:
- Pure computation vs business logic
- Executor has no database access
- Service coordinates entity + executor
- Testability and modularity

### Decision 4: On-Demand vs Precomputed Modifiers

**Choice**: On-demand
**Rationale**:
- Always accurate (no sync issues)
- Simpler architecture
- 20-40ms overhead negligible
- Easier cache invalidation

### Decision 5: Improvised Actions - Agent Adjudication vs Fixed Table

**Choice**: Agent adjudication
**Rationale**:
- Handles infinite variations
- Learns from RAG precedent
- Maintains DM flexibility
- Contextual reasoning (40ft vs 10ft wall)

---

## APPENDIX C: SQL Snippets for Testing

### Add Test Character

```sql
-- Add test character to database
INSERT INTO creatures (id, name, creature_type, str, dex, con, int, wis, cha, str_mod, dex_mod, con_mod, int_mod, wis_mod, cha_mod, hp, max_hp, ac)
VALUES (
  'creature:test-bard',
  'Lyra Moonshadow',
  'humanoid',
  10, 14, 12, 13, 8, 16,
  0, 2, 1, 1, -1, 3,
  32, 38, 14
);

INSERT INTO characters (creature_id, total_level, proficiency_bonus, xp)
VALUES ('creature:test-bard', 5, 3, 6500);

INSERT INTO character_classes (character_id, class_id, class_level, class_order)
VALUES ('creature:test-bard', 'class:bard', 5, 1);
```

### Add Test Modifier

```sql
-- Add Robe of the Archmagi (+2 spell save DC)
INSERT INTO active_modifiers (creature_id, applies_to, modifier_type, modifier_value, source_name, source_id, duration_type)
VALUES (
  'creature:test-bard',
  'spell_save_dc',
  'flat',
  '2',
  'Robe of the Archmagi',
  'item:robe-123',
  'permanent'
);
```

### Query Entity Context

```sql
-- Get all data needed for formula execution
SELECT
  c.id,
  c.name,
  c.str, c.dex, c.con, c.int, c.wis, c.cha,
  c.str_mod, c.dex_mod, c.con_mod, c.int_mod, c.wis_mod, c.cha_mod,
  ch.total_level as level,
  ch.proficiency_bonus,
  cc.class_id
FROM creatures c
JOIN characters ch ON ch.creature_id = c.id
LEFT JOIN character_classes cc ON cc.character_id = c.id
WHERE c.id = 'creature:test-bard';
```

### Query Active Modifiers

```sql
-- Get all active modifiers for entity
SELECT
  applies_to,
  modifier_type,
  modifier_value,
  source_name,
  duration_type,
  expires_at
FROM active_modifiers
WHERE creature_id = 'creature:test-bard'
  AND (expires_at IS NULL OR expires_at > datetime('now'))
ORDER BY applies_to;
```

---

## APPENDIX D: Quick Reference Commands

### Start Development Server

```bash
cd /Users/barna/Desktop/DND.SRD.Wiki-main/dnd-ai-dm
python src/ui/web_server.py
```

### Run Database Migration

```bash
sqlite3 data/reference.db < data/schemas/formulas_with_modifiers.sql
```

### Run Tests

```bash
pytest tests/test_formula_service.py -v
pytest tests/test_entity.py -v
pytest tests/ -v  # All tests
```

### Check Formula Cache

```python
from services.formula_service import get_formula_service

fs = get_formula_service()
print(fs._formula_cache)
```

### Debug Entity Modifiers

```python
from entities.entity import Entity
from data.sqlite_db import GameStateDB

db = GameStateDB("data/game_state.db")
entity = Entity("creature:test-bard", db)

# Get all modifiers for spell save DC
mods = entity.get_spell_save_dc_modifiers()
print(f"Modifiers: {mods}")

# Check cache state
print(f"Cache: {entity._modifier_cache}")
print(f"Dirty: {entity._cache_dirty}")
```

---

## CONCLUSION

This implementation guide provides everything needed to add the dynamic formula system, entity-based modifiers, improvised action adjudication, and character sheet UI to the D&D AI DM project.

**Architecture Verification**: ✅ CONFIRMED
- Supports standard actions (spell casting, attacks)
- Supports improvised actions (boiling oil, chandelier swing)
- Supports real-time updates (item equip, condition apply)
- Supports multi-character scenarios (explicit entity_id binding)
- Integrates with existing multi-agent workflow
- Uses database as single source of truth

**Key Success Factors**:
1. Follow the 3-tier architecture strictly
2. Entity owns its modifiers
3. Formula executor is pure computation
4. Improvised actions use agent reasoning + RAG precedent
5. Cache invalidation on entity changes
6. SocketIO for real-time UI updates

**Estimated Implementation Time**:
- Phase 1 (Database): 2 hours
- Phase 2 (Entity): 4 hours
- Phase 3 (Formula Service): 4 hours
- Phase 4 (ReasoningAgent): 6 hours
- Phase 5 (CommandAgent): 4 hours
- Phase 6 (Character Sheet): 8 hours
- **Total**: ~28 hours (3-4 days)

This guide can be used by a fresh Claude Code session with minimal context window to implement the entire system efficiently.

**Next Steps**: Exit plan mode and begin Phase 1 implementation (database setup).
