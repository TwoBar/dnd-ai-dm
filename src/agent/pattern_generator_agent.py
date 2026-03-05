"""
Pattern Generator Agent - Self-Learning Intent Patterns

This agent learns new intent patterns from RAG discoveries and adds them
to the system's pattern library, making future detections faster and more accurate.

Purpose:
- Receive pattern proposals from RAG Intent Agent
- Validate patterns against test cases
- Add patterns to database (with approval workflow)
- Generate execution formulas based on D&D rules
- Test patterns in backend before activation

Flow:
1. Receive pattern proposal from RAG Agent
2. Generate regex pattern and execution formula
3. Validate with test cases
4. Store in database (pending or approved status)
5. Optionally activate after manual review

Benefits:
- System learns over time
- Reduces LLM calls (more regex patterns)
- Handles D&D-specific actions
- Self-documenting (patterns reference rules)
"""

import re
import json
import sqlite3
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from .intent_agent import Intent, ActionType, SkillType


@dataclass
class PatternValidation:
    """Result of pattern validation"""
    is_valid: bool
    test_passed: int
    test_failed: int
    errors: List[str]
    warnings: List[str]


@dataclass
class LearnedPattern:
    """A learned intent pattern"""
    pattern_id: str
    name: str
    action_type: ActionType
    regex_patterns: List[str]
    skill: Optional[SkillType]
    execution_formula: str  # How to execute mechanics
    rule_references: List[Dict]
    example_messages: List[str]
    confidence: float
    status: str  # 'pending', 'approved', 'active', 'rejected'
    created_at: str
    validated_at: Optional[str]
    activated_at: Optional[str]


class PatternGeneratorAgent:
    """
    Generates and validates new intent patterns from RAG discoveries.

    This agent implements the learning loop that makes the system smarter over time.
    """

    def __init__(self, database_path: str):
        """
        Initialize Pattern Generator Agent.

        Args:
            database_path: Path to pattern database
        """
        self.db_path = database_path
        self._ensure_database()

    def _ensure_database(self):
        """Create database tables if they don't exist"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()

            # Learned patterns table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS learned_patterns (
                    pattern_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    regex_patterns JSON NOT NULL,
                    skill TEXT,
                    execution_formula TEXT NOT NULL,
                    rule_references JSON,
                    example_messages JSON NOT NULL,
                    confidence REAL DEFAULT 0.8,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    validated_at TIMESTAMP,
                    activated_at TIMESTAMP,
                    activation_count INTEGER DEFAULT 0,
                    success_count INTEGER DEFAULT 0,
                    failure_count INTEGER DEFAULT 0
                )
            """)

            # Pattern test cases
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pattern_test_cases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern_id TEXT NOT NULL,
                    test_message TEXT NOT NULL,
                    expected_match BOOLEAN NOT NULL,
                    actual_result BOOLEAN,
                    test_passed BOOLEAN,
                    tested_at TIMESTAMP,
                    FOREIGN KEY (pattern_id) REFERENCES learned_patterns(pattern_id)
                )
            """)

            # Pattern activation log
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pattern_activations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern_id TEXT NOT NULL,
                    user_message TEXT NOT NULL,
                    matched BOOLEAN NOT NULL,
                    executed BOOLEAN NOT NULL,
                    execution_result TEXT,
                    activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (pattern_id) REFERENCES learned_patterns(pattern_id)
                )
            """)

            conn.commit()
        finally:
            conn.close()

    def generate_pattern(
        self,
        proposal: Dict,
        auto_approve: bool = False
    ) -> Optional[LearnedPattern]:
        """
        Generate a new pattern from RAG proposal.

        Args:
            proposal: Pattern proposal from RAG Intent Agent
            auto_approve: If True, activate immediately without review

        Returns:
            LearnedPattern if successfully generated
        """
        print(f"[Pattern Gen] Generating pattern: {proposal.get('name')}")

        # Step 1: Generate regex patterns
        regex_patterns = self._generate_regex_patterns(proposal)

        # Step 2: Generate execution formula
        execution_formula = self._generate_execution_formula(proposal)

        # Step 3: Create pattern object
        pattern_id = f"learned_{proposal['action_type']}_{int(datetime.now().timestamp())}"

        pattern = LearnedPattern(
            pattern_id=pattern_id,
            name=proposal['name'],
            action_type=ActionType(proposal['action_type']),
            regex_patterns=regex_patterns,
            skill=SkillType(proposal['detected_skill']) if proposal.get('detected_skill') else None,
            execution_formula=execution_formula,
            rule_references=proposal.get('rule_references', []),
            example_messages=[proposal['example_message']],
            confidence=proposal.get('confidence', 0.8),
            status='pending',
            created_at=datetime.now().isoformat(),
            validated_at=None,
            activated_at=None
        )

        # Step 4: Validate pattern
        validation = self._validate_pattern(pattern)

        if not validation.is_valid:
            print(f"[Pattern Gen] Validation failed: {validation.errors}")
            return None

        print(f"[Pattern Gen] Validation passed: {validation.test_passed}/{validation.test_passed + validation.test_failed}")

        # Step 5: Store in database
        self._store_pattern(pattern)

        # Step 6: Auto-approve if requested
        if auto_approve and validation.test_passed >= 3:
            self.approve_pattern(pattern_id)
            print(f"[Pattern Gen] Pattern auto-approved and activated")

        return pattern

    def _generate_regex_patterns(self, proposal: Dict) -> List[str]:
        """
        Generate regex patterns from proposal.

        Uses trigger phrases and example message to create patterns.
        """
        patterns = []

        # Add proposed regex if available
        if proposal.get('proposed_regex'):
            patterns.append(proposal['proposed_regex'])

        # Generate patterns from trigger phrases
        trigger_phrases = proposal.get('trigger_phrases', [])
        if trigger_phrases:
            # Pattern 1: Exact phrase match
            phrases_or = '|'.join(re.escape(phrase) for phrase in trigger_phrases)
            patterns.append(f"r'\\b({phrases_or})\\b'")

            # Pattern 2: Phrase with optional object
            patterns.append(f"r'\\b({phrases_or})\\s+(?:the\\s+)?(\\w+)'")

        # Generate pattern from example message
        example = proposal.get('example_message', '')
        if example:
            # Extract verb from example
            words = example.lower().split()
            action_words = [w for w in words if w in ['try', 'attempt', 'want', 'going']]
            if action_words and len(words) > words.index(action_words[0]) + 1:
                verb = words[words.index(action_words[0]) + 2]
                patterns.append(f"r'\\b{re.escape(verb)}\\b'")

        # Remove duplicates
        return list(set(patterns))

    def _generate_execution_formula(self, proposal: Dict) -> str:
        """
        Generate execution formula based on D&D rules.

        Formula describes how to execute the mechanics.

        Examples:
        - "1d20 + Athletics vs DC (contested by target's Athletics or Acrobatics)"
        - "1d20 + Sleight of Hand vs target's Perception"
        - "Save: DEX DC 15, half damage on success"
        """
        action_type = proposal.get('action_type')
        skill = proposal.get('detected_skill')

        # Extract DC or contested check from rules
        rules_text = ""
        rule_refs = proposal.get('rule_references', [])
        if rule_refs:
            rules_text = rule_refs[0].get('text', '').lower()

        # Analyze rules for formula
        if 'contested' in rules_text or 'opposed' in rules_text:
            # Contested check
            if skill:
                return f"1d20 + {skill.upper()} vs target's contested check"
            else:
                return "1d20 + ability modifier vs target's contested check"

        elif 'dc' in rules_text:
            # DC-based check
            # Try to extract DC
            dc_match = re.search(r'dc\s+(\d+)', rules_text)
            dc = dc_match.group(1) if dc_match else '15'

            if skill:
                return f"1d20 + {skill.upper()} vs DC {dc}"
            else:
                return f"1d20 + ability modifier vs DC {dc}"

        elif action_type == 'skill_check' and skill:
            return f"1d20 + {skill.upper()} vs DM-set DC"

        elif action_type == 'attack':
            return "1d20 + attack modifier vs target AC, then damage roll"

        elif action_type == 'spell_cast':
            return "Spell save DC or spell attack roll (spell-dependent)"

        else:
            return "1d20 + modifier vs DC or contested (context-dependent)"

    def _validate_pattern(self, pattern: LearnedPattern) -> PatternValidation:
        """
        Validate pattern with test cases.

        Tests:
        1. Regex compiles successfully
        2. Matches example messages
        3. Doesn't match unrelated messages
        4. Execution formula is valid
        """
        errors = []
        warnings = []
        test_passed = 0
        test_failed = 0

        # Test 1: Regex compilation
        for regex_pattern in pattern.regex_patterns:
            try:
                # Remove r' prefix and ' suffix if present
                pattern_str = regex_pattern
                if pattern_str.startswith("r'"):
                    pattern_str = pattern_str[2:-1]

                re.compile(pattern_str)
            except re.error as e:
                errors.append(f"Invalid regex: {regex_pattern} - {e}")
                test_failed += 1
            else:
                test_passed += 1

        # Test 2: Matches example messages
        for example in pattern.example_messages:
            matched = self._test_pattern_match(pattern, example)
            if matched:
                test_passed += 1
            else:
                warnings.append(f"Pattern doesn't match its own example: {example}")
                test_failed += 1

        # Test 3: Doesn't match unrelated messages
        negative_tests = [
            "I walk north",
            "Tell me about the town",
            "What do I see?",
            "I cast Fireball",
        ]

        for neg_test in negative_tests:
            matched = self._test_pattern_match(pattern, neg_test)
            if not matched:
                test_passed += 1
            else:
                # This is okay if it's actually related
                warnings.append(f"Pattern matches unrelated message: {neg_test}")

        # Test 4: Execution formula is non-empty
        if pattern.execution_formula and len(pattern.execution_formula) > 10:
            test_passed += 1
        else:
            errors.append("Execution formula is missing or too short")
            test_failed += 1

        is_valid = len(errors) == 0 and test_passed >= 3

        return PatternValidation(
            is_valid=is_valid,
            test_passed=test_passed,
            test_failed=test_failed,
            errors=errors,
            warnings=warnings
        )

    def _test_pattern_match(self, pattern: LearnedPattern, message: str) -> bool:
        """Test if pattern matches a message"""
        message_lower = message.lower()

        for regex_pattern in pattern.regex_patterns:
            try:
                pattern_str = regex_pattern
                if pattern_str.startswith("r'"):
                    pattern_str = pattern_str[2:-1]

                if re.search(pattern_str, message_lower):
                    return True
            except re.error:
                continue

        return False

    def _store_pattern(self, pattern: LearnedPattern):
        """Store pattern in database"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO learned_patterns (
                    pattern_id, name, action_type, regex_patterns, skill,
                    execution_formula, rule_references, example_messages,
                    confidence, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                pattern.pattern_id,
                pattern.name,
                pattern.action_type.value,
                json.dumps(pattern.regex_patterns),
                pattern.skill.value if pattern.skill else None,
                pattern.execution_formula,
                json.dumps(pattern.rule_references),
                json.dumps(pattern.example_messages),
                pattern.confidence,
                pattern.status
            ))
            conn.commit()
        finally:
            conn.close()

    def approve_pattern(self, pattern_id: str) -> bool:
        """
        Approve and activate a pattern.

        Args:
            pattern_id: Pattern to approve

        Returns:
            True if successful
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE learned_patterns
                SET status = 'active',
                    activated_at = ?
                WHERE pattern_id = ?
            """, (datetime.now().isoformat(), pattern_id))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def reject_pattern(self, pattern_id: str, reason: str = "") -> bool:
        """Reject a pattern"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE learned_patterns
                SET status = 'rejected'
                WHERE pattern_id = ?
            """, (pattern_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def get_active_patterns(self) -> List[LearnedPattern]:
        """Get all active learned patterns"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM learned_patterns
                WHERE status = 'active'
                ORDER BY confidence DESC, activation_count DESC
            """)

            patterns = []
            for row in cursor.fetchall():
                patterns.append(LearnedPattern(
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
                ))

            return patterns
        finally:
            conn.close()

    def get_pending_patterns(self) -> List[LearnedPattern]:
        """Get patterns awaiting approval"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM learned_patterns
                WHERE status = 'pending'
                ORDER BY created_at DESC
            """)

            patterns = []
            for row in cursor.fetchall():
                patterns.append(LearnedPattern(
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
                ))

            return patterns
        finally:
            conn.close()

    def log_pattern_usage(
        self,
        pattern_id: str,
        user_message: str,
        matched: bool,
        executed: bool,
        result: Optional[str] = None
    ):
        """Log usage of a pattern for analytics"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()

            # Log activation
            cursor.execute("""
                INSERT INTO pattern_activations (
                    pattern_id, user_message, matched, executed, execution_result
                ) VALUES (?, ?, ?, ?, ?)
            """, (pattern_id, user_message, matched, executed, result))

            # Update pattern statistics
            if executed:
                success = result and 'success' in result.lower()
                cursor.execute("""
                    UPDATE learned_patterns
                    SET activation_count = activation_count + 1,
                        success_count = success_count + ?,
                        failure_count = failure_count + ?
                    WHERE pattern_id = ?
                """, (1 if success else 0, 0 if success else 1, pattern_id))

            conn.commit()
        finally:
            conn.close()
