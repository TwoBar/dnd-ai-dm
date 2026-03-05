"""
Dynamic Formula Service - COMPLETE IMPLEMENTATION

Manages formula storage, retrieval, and execution with entity context binding.

Key Features:
1. Store formulas in database (discovered via RAG or predefined)
2. Semantic formula lookup (natural language → formula)
3. Entity context binding (execute formula for specific character)
4. RAG fallback (discover new formulas on-demand with LLM extraction)
5. Modifier aggregation via Entity class
6. Pure computation via FormulaExecutor
"""

import json
import logging
import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from data.sqlite_db import ReferenceDB, GameStateDB
from parsers.formula_parser import FormulaParser
from entities.entity import Entity, Modifier
from services.formula_executor import FormulaExecutor, ExecutionResult

logger = logging.getLogger(__name__)


@dataclass
class FormulaResult:
    """Result of formula execution"""
    value: Any  # int, str (dice notation), or bool
    formula_name: str
    formula: str
    context_used: Dict[str, Any]
    modifiers_applied: List[Modifier]
    entity_id: str
    entity_type: str
    has_advantage: bool = False
    has_disadvantage: bool = False
    breakdown: str = ""


class FormulaService:
    """
    Manages dynamic formula system with context binding

    Architecture:
    - FormulaService: Coordinates formula execution (business logic)
    - Entity: Aggregates modifiers from database (data access)
    - FormulaExecutor: Applies modifiers to formulas (pure computation)

    Usage:
        result = formula_service.execute_for_entity(
            formula_name="spell_save_dc",
            entity_id="creature:uuid-123",
            entity_type="character"
        )
        # Returns: FormulaResult(value=16, modifiers=[...], ...)
    """

    def __init__(self, reference_db: ReferenceDB, game_state_db: GameStateDB):
        self.ref_db = reference_db
        self.game_db = game_state_db
        self.parser = FormulaParser()
        self.executor = FormulaExecutor(self.parser)

        # Cache for formulas (formula_name → formula_text)
        self._formula_cache = {}

    def execute_for_entity(
        self,
        formula_name: str,
        entity_id: str,
        entity_type: str = "character",
        extra_context: Optional[Dict[str, Any]] = None
    ) -> FormulaResult:
        """
        Execute formula for a specific entity (character, monster, etc.)

        This is the MAIN method agents use!

        Args:
            formula_name: Name of formula to execute (e.g., "spell_save_dc")
            entity_id: ID of entity to execute for (e.g., "creature:uuid-123")
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
            # Returns: FormulaResult(value=16, modifiers=[...], ...)
        """
        # 1. Get formula from database (or cache)
        formula = self._get_formula(formula_name)

        if not formula:
            # Formula not found - try RAG discovery
            logger.info(f"Formula '{formula_name}' not found in database, attempting RAG discovery...")
            formula = self._discover_formula_via_rag(formula_name)

            if not formula:
                raise ValueError(f"Formula '{formula_name}' not found and could not be discovered")

        # 2. Build entity and get context
        entity = Entity(entity_id, self.game_db)
        context = self._build_entity_context(entity_id, entity_type)

        # 3. Merge extra context if provided
        if extra_context:
            context.update(extra_context)

        # 4. Get modifiers from entity
        modifiers = entity.get_modifiers_for(formula_name)

        # 5. Execute formula with executor
        exec_result = self.executor.execute(formula, context, modifiers)

        # 6. Update usage count
        self._increment_usage(formula_name)

        return FormulaResult(
            value=exec_result.value,
            formula_name=formula_name,
            formula=formula,
            context_used=context,
            modifiers_applied=exec_result.modifiers_applied,
            entity_id=entity_id,
            entity_type=entity_type,
            has_advantage=exec_result.has_advantage,
            has_disadvantage=exec_result.has_disadvantage,
            breakdown=exec_result.breakdown
        )

    def _build_entity_context(self, entity_id: str, entity_type: str) -> Dict[str, Any]:
        """
        Build formula context from entity database record

        Args:
            entity_id: Entity ID (e.g., "creature:uuid-123")
            entity_type: Entity type ("character", "monster")

        Returns:
            Context dict with all variables for formula execution
        """
        # Fetch entity data from database
        if entity_type == "character":
            entity_data = self._fetch_character_data(entity_id)
        elif entity_type == "monster":
            entity_data = self._fetch_monster_data(entity_id)
        else:
            raise ValueError(f"Unknown entity type: {entity_type}")

        # Use FormulaParser to build context
        context = self.parser.build_context(entity_data)

        return context

    def _fetch_character_data(self, creature_id: str) -> Dict[str, Any]:
        """
        Fetch character data from database

        Returns:
            Dict with all character stats for formula context
        """
        query = """
        SELECT
            c.id,
            c.name,
            c.str, c.dex, c.con, c.int, c.wis, c.cha,
            c.hp, c.max_hp, c.temp_hp, c.ac,
            ch.total_level as level,
            ch.proficiency_bonus,
            ch.spell_slots,
            ch.class_resources,
            ch.multiclass_caster_level
        FROM creatures c
        LEFT JOIN characters ch ON ch.creature_id = c.id
        WHERE c.id = ?
        """

        result = self.game_db.query(query, (creature_id,))

        if not result:
            raise ValueError(f"Character not found: {creature_id}")

        data = dict(result[0])

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

        # Compute ability modifiers if not present
        for ability in ['str', 'dex', 'con', 'int', 'wis', 'cha']:
            if ability in data and f'{ability}_mod' not in data:
                data[f'{ability}_mod'] = self.parser.get_ability_modifier(data[ability])

        # Get character classes to determine spellcasting ability
        classes_query = """
        SELECT class_id, class_level
        FROM character_classes
        WHERE character_id = ?
        ORDER BY class_order
        """

        classes = self.game_db.query(classes_query, (creature_id,))

        if classes:
            # Get primary class (first in multiclass order)
            primary_class = classes[0]['class_id']

            # Determine spellcasting ability based on class
            spellcasting_ability = self._get_spellcasting_ability(primary_class)
            if spellcasting_ability:
                data['spellcasting_ability'] = spellcasting_ability
                # Get the modifier for that ability
                data['spellcasting_ability_mod'] = data.get(f'{spellcasting_ability}_mod', 0)

        return data

    def _fetch_monster_data(self, creature_id: str) -> Dict[str, Any]:
        """Fetch monster data from database"""
        query = """
        SELECT
            c.id,
            c.name,
            c.str, c.dex, c.con, c.int, c.wis, c.cha,
            c.hp, c.max_hp, c.ac,
            m.cr,
            m.proficiency_bonus
        FROM creatures c
        LEFT JOIN monsters m ON m.creature_id = c.id
        WHERE c.id = ?
        """

        result = self.game_db.query(query, (creature_id,))

        if not result:
            raise ValueError(f"Monster not found: {creature_id}")

        data = dict(result[0])

        # Compute ability modifiers if not present
        for ability in ['str', 'dex', 'con', 'int', 'wis', 'cha']:
            if ability in data and f'{ability}_mod' not in data:
                data[f'{ability}_mod'] = self.parser.get_ability_modifier(data[ability])

        return data

    def _get_spellcasting_ability(self, class_id: str) -> Optional[str]:
        """
        Determine spellcasting ability for a class

        Returns:
            'int', 'wis', or 'cha' (or None for non-casters)
        """
        SPELLCASTING_ABILITIES = {
            'wizard': 'int',
            'artificer': 'int',
            'cleric': 'wis',
            'druid': 'wis',
            'ranger': 'wis',
            'monk': 'wis',
            'bard': 'cha',
            'sorcerer': 'cha',
            'warlock': 'cha',
            'paladin': 'cha',
        }

        # Extract class name from class_id (e.g., "class:wizard" → "wizard")
        class_name = class_id.split(':')[-1].lower()

        return SPELLCASTING_ABILITIES.get(class_name)

    def _get_formula(self, formula_name: str) -> Optional[str]:
        """
        Get formula from cache or database

        Args:
            formula_name: Name of formula

        Returns:
            Formula text or None if not found
        """
        # Check cache first
        if formula_name in self._formula_cache:
            return self._formula_cache[formula_name]

        # Try direct lookup
        query = "SELECT base_formula FROM formulas WHERE formula_name = ?"
        result = self.ref_db.query(query, (formula_name,))

        if result:
            formula = result[0]['base_formula']
            self._formula_cache[formula_name] = formula
            return formula

        # Try alias lookup
        alias_query = """
        SELECT f.base_formula
        FROM formula_aliases fa
        JOIN formulas f ON f.formula_name = fa.formula_name
        WHERE fa.alias = ?
        """
        alias_result = self.ref_db.query(alias_query, (formula_name,))

        if alias_result:
            formula = alias_result[0]['base_formula']
            self._formula_cache[formula_name] = formula
            return formula

        return None

    def _discover_formula_via_rag(self, formula_name: str) -> Optional[str]:
        """
        Discover formula via RAG when not found in database

        This is the MAGIC part - system learns new formulas!

        Process:
        1. Query RAG for related D&D rules
        2. Use LLM to extract formula from rule text
        3. Store discovered formula in database
        4. Return formula for immediate use

        Args:
            formula_name: Name of formula (e.g., "grapple_escape_dc")

        Returns:
            Formula text if discovered, None otherwise
        """
        logger.info(f"🔍 Formula '{formula_name}' not found, attempting RAG discovery...")

        try:
            # Import RAG service
            from agent.rag_query_service import RAGQueryService

            rag = RAGQueryService()

            # Query RAG for formula
            question = f"How to calculate {formula_name.replace('_', ' ')} in D&D 5e?"

            rule_results = rag.search_rules(question, max_results=3)

            if not rule_results:
                logger.warning(f"No RAG results for formula '{formula_name}'")
                return None

            # Combine rule texts
            rule_text = "\n\n".join([r.get('content', r.get('text', '')) for r in rule_results])

            # Use LLM to extract formula from rule text
            formula = self._extract_formula_from_rule(formula_name, rule_text)

            if formula:
                # Store formula in database for future use
                self._store_discovered_formula(formula_name, formula, rule_text[:500])
                logger.info(f"✅ Discovered and stored formula: {formula_name} = {formula}")
                return formula
            else:
                logger.warning(f"Could not extract formula from RAG results for '{formula_name}'")

        except Exception as e:
            logger.error(f"Failed to discover formula via RAG: {e}", exc_info=True)

        return None

    def _extract_formula_from_rule(self, formula_name: str, rule_text: str) -> Optional[str]:
        """
        Use LLM to extract formula from rule text

        Args:
            formula_name: Name of formula we're looking for
            rule_text: RAG result containing rule description

        Returns:
            Extracted formula or None

        Example:
            rule_text = "Spell save DC equals 8 + your proficiency bonus + your spellcasting ability modifier"
            formula = _extract_formula(...)
            # Returns: "8 + proficiency_bonus + spellcasting_ability_mod"
        """
        try:
            # Use OpenAI to extract formula
            import openai

            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                logger.warning("OPENAI_API_KEY not set, cannot extract formula from RAG")
                return None

            client = openai.OpenAI(api_key=api_key)

            prompt = f"""You are a D&D 5e rules expert. Extract a mathematical formula from the following rule text.

Formula name: {formula_name}

Rule text:
{rule_text}

Convert the rule into a mathematical formula using these variable names:
- Ability scores: str, dex, con, int, wis, cha
- Ability modifiers: str_mod, dex_mod, con_mod, int_mod, wis_mod, cha_mod
- Character level: level
- Proficiency bonus: proficiency_bonus
- Spellcasting ability modifier: spellcasting_ability_mod
- Dice notation: 1d20, 2d6, etc.
- Math operators: +, -, *, /, floor(), ceil(), max(), min()

Return ONLY the formula, nothing else. If you cannot extract a formula, return "NONE".

Examples:
- "Spell save DC equals 8 + your proficiency bonus + your spellcasting ability modifier"
  → 8 + proficiency_bonus + spellcasting_ability_mod

- "Initiative is a Dexterity check with no proficiency bonus"
  → 1d20 + dex_mod

- "Grapple escape DC equals 8 + the grappler's proficiency bonus + the grappler's Strength modifier"
  → 8 + proficiency_bonus + str_mod

Formula:"""

            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a D&D 5e rules expert who extracts mathematical formulas."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=200
            )

            formula = response.choices[0].message.content.strip()

            if formula and formula != "NONE" and formula.lower() != "none":
                logger.info(f"Extracted formula: {formula}")
                return formula

        except Exception as e:
            logger.error(f"LLM formula extraction failed: {e}", exc_info=True)

        return None

    def _store_discovered_formula(self, formula_name: str, formula: str, rule_reference: str):
        """
        Store newly discovered formula in database

        Args:
            formula_name: Name of formula
            formula: Formula text
            rule_reference: RAG result that produced this formula
        """
        query = """
        INSERT OR REPLACE INTO formulas (
            formula_name, base_formula, source, rule_reference, discovered_at
        ) VALUES (?, ?, 'rag_discovered', ?, datetime('now'))
        """

        self.ref_db.execute(query, (formula_name, formula, rule_reference))

        # Update cache
        self._formula_cache[formula_name] = formula

    def _increment_usage(self, formula_name: str):
        """Increment usage counter for analytics"""
        query = """
        UPDATE formulas
        SET usage_count = usage_count + 1,
            last_used_at = datetime('now')
        WHERE formula_name = ?
        """

        try:
            self.ref_db.execute(query, (formula_name,))
        except Exception as e:
            logger.warning(f"Failed to increment usage for {formula_name}: {e}")

    def semantic_lookup(self, query: str) -> List[str]:
        """
        Find formulas by natural language query

        Args:
            query: Natural language (e.g., "spell save DC", "attack bonus")

        Returns:
            List of matching formula names
        """
        query_lower = query.lower()

        # Search formulas by name and description
        sql = """
        SELECT formula_name, description
        FROM formulas
        WHERE formula_name LIKE ? OR description LIKE ?
        ORDER BY usage_count DESC
        LIMIT 5
        """

        results = self.ref_db.query(sql, (f"%{query_lower}%", f"%{query_lower}%"))

        return [r['formula_name'] for r in results]


# Singleton instance (initialized by game session)
_formula_service: Optional[FormulaService] = None


def get_formula_service() -> FormulaService:
    """Get global formula service instance"""
    global _formula_service
    if _formula_service is None:
        raise RuntimeError("FormulaService not initialized. Call init_formula_service() first.")
    return _formula_service


def init_formula_service(reference_db: ReferenceDB, game_state_db: GameStateDB):
    """Initialize global formula service"""
    global _formula_service
    _formula_service = FormulaService(reference_db, game_state_db)
    logger.info("FormulaService initialized")
