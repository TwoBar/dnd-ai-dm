"""
RAG-Based Character Creation Requirements

Instead of hardcoded parameters, query D&D rules to determine
what's needed to create a character dynamically.
"""
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class CharacterRequirement:
    """A required piece of information for character creation"""
    parameter: str
    description: str
    is_required: bool
    depends_on: Optional[List[str]] = None  # Depends on other parameters
    rule_reference: Optional[str] = None


class CharacterRequirementsRAG:
    """
    Query RAG to determine what's needed for character creation.

    Instead of hardcoded "name, race, class, level", this queries
    D&D rules to understand what's actually needed.
    """

    def __init__(self, rag_query_service):
        """
        Args:
            rag_query_service: RAGQueryService for querying D&D rules
        """
        self.rag_query = rag_query_service

    def get_requirements(
        self,
        extracted_parameters: Dict[str, any]
    ) -> List[CharacterRequirement]:
        """
        Determine what's needed for character creation based on D&D rules.

        Returns dynamically determined requirements based on:
        - What class was chosen (wizards need spells, etc.)
        - What level they are (higher levels need more choices)
        - What's already been provided

        Args:
            extracted_parameters: Parameters already collected

        Returns:
            List of requirements, both fulfilled and missing
        """
        requirements = []

        # Base requirements (always needed)
        base_reqs = self._get_base_requirements()
        requirements.extend(base_reqs)

        # Class-specific requirements
        class_name = extracted_parameters.get('class_name')
        if class_name:
            class_reqs = self._get_class_requirements(class_name, extracted_parameters)
            requirements.extend(class_reqs)

        # Level-specific requirements
        level = extracted_parameters.get('level', 1)
        if level > 1:
            level_reqs = self._get_level_requirements(level, extracted_parameters)
            requirements.extend(level_reqs)

        return requirements

    def _get_base_requirements(self) -> List[CharacterRequirement]:
        """
        Base requirements for any D&D character.

        These are universal, but we could query RAG to confirm.
        """
        return [
            CharacterRequirement(
                parameter='name',
                description='Character name',
                is_required=True,
                rule_reference='PHB Chapter 1'
            ),
            CharacterRequirement(
                parameter='race',
                description='Character race (Human, Elf, Dwarf, etc.)',
                is_required=True,
                rule_reference='PHB Chapter 2'
            ),
            CharacterRequirement(
                parameter='class_name',
                description='Character class (Wizard, Fighter, etc.)',
                is_required=True,
                rule_reference='PHB Chapter 3'
            ),
            CharacterRequirement(
                parameter='level',
                description='Character level (1-20)',
                is_required=True,
                rule_reference='PHB Chapter 1'
            ),
            CharacterRequirement(
                parameter='ability_scores',
                description='Ability scores (STR, DEX, CON, INT, WIS, CHA)',
                is_required=True,
                rule_reference='PHB Chapter 1'
            ),
            CharacterRequirement(
                parameter='background',
                description='Character background (Soldier, Noble, etc.)',
                is_required=False,  # Optional but recommended
                rule_reference='PHB Chapter 4'
            ),
        ]

    def _get_class_requirements(
        self,
        class_name: str,
        extracted_parameters: Dict
    ) -> List[CharacterRequirement]:
        """
        Query database for class-specific requirements.

        Examples:
        - Wizard: needs spell selection, arcane tradition
        - Cleric: needs deity, domain
        - Fighter: needs fighting style
        """
        class_lower = class_name.lower()
        requirements = []

        # Query database for class info
        try:
            # Get class data from database
            with self.rag_query.entity_manager.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT is_spellcaster, spellcasting_ability, spells_known_by_level,
                           cantrips_known_by_level, spellcasting_type
                    FROM classes
                    WHERE LOWER(name) = LOWER(?)
                """, (class_name,))
                class_data = cursor.fetchone()

            # If class is a spellcaster, require spell selection
            if class_data and class_data[0]:  # is_spellcaster
                requirements.append(CharacterRequirement(
                    parameter='spells',
                    description='Starting spells and cantrips',
                    is_required=True,
                    depends_on=['class_name', 'level'],
                    rule_reference=f'{class_name} Spellcasting (PHB)'
                ))

        except Exception as e:
            print(f"[CharacterRAG] Error querying class data: {e}")

        # Fallback: Use hardcoded class knowledge when database doesn't have details
        # This preserves functionality while the database is being populated

        # Check if spells requirement already added from database
        has_spells_req = any(req.parameter == 'spells' for req in requirements)

        # Add class-specific requirements based on D&D 5e rules
        if class_lower == 'wizard' and not has_spells_req:
            requirements.append(CharacterRequirement(
                parameter='spells',
                description='Starting spells and cantrips',
                is_required=True,
                depends_on=['class_name', 'level'],
                rule_reference='Wizard Spellcasting (PHB p. 114)'
            ))

        elif class_lower == 'cleric':
            requirements.append(CharacterRequirement(
                parameter='deity',
                description='Deity or pantheon',
                is_required=False,
                depends_on=['class_name'],
                rule_reference='Cleric (PHB p. 56)'
            ))
            if not has_spells_req:
                requirements.append(CharacterRequirement(
                    parameter='spells',
                    description='Starting spells and cantrips',
                    is_required=True,
                    depends_on=['class_name', 'level'],
                    rule_reference='Cleric Spellcasting (PHB p. 58)'
                ))

        elif class_lower == 'fighter':
            requirements.append(CharacterRequirement(
                parameter='fighting_style',
                description='Fighting Style (Archery, Defense, Dueling, etc.)',
                is_required=True,
                depends_on=['class_name'],
                rule_reference='Fighting Style (PHB p. 72)'
            ))

        elif class_lower in ['bard', 'sorcerer', 'warlock'] and not has_spells_req:
            requirements.append(CharacterRequirement(
                parameter='spells',
                description='Starting spells and cantrips',
                is_required=True,
                depends_on=['class_name', 'level'],
                rule_reference=f'{class_name} Spellcasting (PHB)'
            ))

        # Deduplicate requirements
        seen = set()
        unique_reqs = []
        for req in requirements:
            if req.parameter not in seen:
                seen.add(req.parameter)
                unique_reqs.append(req)

        return unique_reqs

    def _get_level_requirements(
        self,
        level: int,
        extracted_parameters: Dict
    ) -> List[CharacterRequirement]:
        """
        Query RAG for level-specific requirements.

        Higher levels may need:
        - Subclass selection (level 2-3 depending on class)
        - Ability score improvements (level 4, 8, 12, 16, 19)
        - Additional spell selections
        - Feat choices (if using ASI for feats)
        """
        requirements = []
        class_name = extracted_parameters.get('class_name', '')

        # Subclass selection (varies by class)
        if class_name:
            # Most classes get subclass at level 2-3
            # Some (Cleric, Sorcerer, Warlock) get it at level 1
            subclass_levels = {
                'wizard': 2,
                'cleric': 1,
                'fighter': 3,
                'rogue': 3,
                'ranger': 3,
                'paladin': 3,
                'bard': 3,
                'druid': 2,
                'monk': 3,
                'sorcerer': 1,
                'warlock': 1,
                'barbarian': 3
            }

            subclass_level = subclass_levels.get(class_name.lower(), 3)
            if level >= subclass_level:
                requirements.append(CharacterRequirement(
                    parameter='subclass',
                    description=f'{class_name} subclass choice',
                    is_required=True,
                    depends_on=['class_name', 'level'],
                    rule_reference=f'PHB {class_name} Level {subclass_level}'
                ))

        # Ability Score Improvements
        asi_levels = [4, 8, 12, 16, 19]
        if level in asi_levels:
            requirements.append(CharacterRequirement(
                parameter='asi_choices',
                description=f'Ability Score Improvement or Feat (level {level})',
                is_required=True,
                depends_on=['level'],
                rule_reference=f'PHB Chapter 6 - Level {level}'
            ))

        return requirements

    def get_missing_requirements(
        self,
        extracted_parameters: Dict[str, any]
    ) -> List[CharacterRequirement]:
        """
        Get requirements that are still missing.

        Returns only requirements that:
        1. Are required
        2. Haven't been provided yet
        3. Dependencies are met (e.g., can't ask for subclass before class)
        """
        all_requirements = self.get_requirements(extracted_parameters)
        missing = []

        for req in all_requirements:
            # Skip if already provided
            if req.parameter in extracted_parameters and extracted_parameters[req.parameter]:
                continue

            # Skip if not required
            if not req.is_required:
                continue

            # Check dependencies
            if req.depends_on:
                dependencies_met = all(
                    dep in extracted_parameters and extracted_parameters[dep]
                    for dep in req.depends_on
                )
                if not dependencies_met:
                    continue  # Can't ask yet

            missing.append(req)

        return missing

    def format_requirement_explanation(
        self,
        requirement: CharacterRequirement,
        extracted_parameters: Dict
    ) -> str:
        """
        Format an explanation of what's needed and why.

        Uses RAG to provide context from D&D rules.
        """
        explanation = f"**{requirement.description}**\n\n"

        if requirement.rule_reference:
            explanation += f"According to {requirement.rule_reference}:\n"

        # Query RAG for more details
        try:
            query = f"D&D 5e {requirement.parameter} {extracted_parameters.get('class_name', '')} how to choose"
            rules = self.rag_query.entity_manager.search_rules(query=query)[:2]

            if rules:
                explanation += f"\n{rules[0].content[:300]}...\n"
        except:
            pass

        return explanation
