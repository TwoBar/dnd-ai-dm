"""
Question generation for the reasoning agent.

Generates natural, conversational clarification questions using LLM,
with RAG-backed suggestions for options like spells, subclasses, etc.
"""
import re
from typing import Dict, List, Optional, Tuple

from agent.intent_agent import ActionType
from agent.rag_query_service import ActionRequirements


def generate_question_with_rag(
    param_name: str,
    action_type: ActionType,
    requirements: ActionRequirements,
    context: Dict,
    rag_query,
    requirement_details=None
) -> Tuple[str, List[str]]:
    """
    Generate clarification question using LLM for natural conversation.

    For character creation, uses RAG-determined requirements dynamically.

    Returns: (question, suggestions)
    """
    suggestions = _get_suggestions(param_name, context, rag_query, requirement_details)

    question = _generate_conversational_question_with_llm(
        param_name=param_name,
        action_type=action_type,
        requirements=requirements,
        suggestions=suggestions,
        context=context,
        requirement_details=requirement_details
    )

    return question, suggestions


def _get_suggestions(
    param_name: str,
    context: Dict,
    rag_query,
    requirement_details
) -> List[str]:
    """Get contextual suggestions for a parameter."""
    if param_name == 'target':
        enemies = context.get('nearby_enemies', [])
        return [
            f"{e.get('name', 'unknown')} ({e.get('distance', 0):.1f}m away)"
            for e in enemies[:5]
        ]

    elif param_name == 'spells' and requirement_details:
        class_name = context.get('extracted_parameters', {}).get('class_name')
        level = context.get('extracted_parameters', {}).get('level', 1)
        if class_name:
            return _get_spell_suggestions_from_rag(rag_query, class_name, level)

    elif param_name == 'class_name':
        return ['Wizard', 'Fighter', 'Rogue', 'Cleric', 'Barbarian', 'Ranger',
                'Paladin', 'Bard', 'Druid', 'Monk', 'Sorcerer', 'Warlock']

    elif param_name == 'ability_scores':
        return ['Roll 4d6 drop lowest', 'Standard Array (15,14,13,12,10,8)', 'Point Buy']

    elif param_name == 'subclass' and requirement_details:
        class_name = context.get('extracted_parameters', {}).get('class_name')
        if class_name:
            return _get_subclass_suggestions_from_rag(rag_query, class_name)

    elif param_name == 'weapon':
        equipped = context.get('equipped_weapons', [])
        return equipped if equipped else ['Sword', 'Bow', 'Staff', 'Dagger']

    return []


def _generate_conversational_question_with_llm(
    param_name: str,
    action_type: ActionType,
    requirements: ActionRequirements,
    suggestions: List[str],
    context: Dict,
    requirement_details=None
) -> str:
    """Use LLM to generate natural, conversational clarification questions."""
    try:
        import openai
        from config import OPENAI_API_KEY

        if not OPENAI_API_KEY:
            return fallback_template_question(param_name)

        system_prompt = """You are a friendly D&D Dungeon Master having a natural conversation with a player.

Generate a natural, conversational question to ask for missing information.

**Guidelines**:
1. Be conversational and warm, like a real DM
2. Reference what the player already told you
3. Keep it concise (1-2 sentences max)
4. Don't use formal templates like "What is your..."
5. Make it feel like natural dialogue

**Examples**:
Bad: "What's your character's name?"
Good: "I'd love to know what to call your character!"

Bad: "What class are you?"
Good: "And what path has your adventurer chosen - are you a wizard, a fighter, perhaps a rogue?"

**Context matters**: If the player said "I'm a barbarian", acknowledge it:
Good: "Great! And what's your barbarian's name?"
"""

        context_str = f"Action: {action_type.value}\n"
        context_str += f"Missing parameter: {param_name}\n"

        if requirement_details:
            context_str += f"Parameter description: {requirement_details.description}\n"
            if requirement_details.rule_reference:
                context_str += f"D&D Rule: {requirement_details.rule_reference}\n"

        if suggestions:
            context_str += f"Available options: {', '.join(suggestions[:5])}\n"

        if requirements and requirements.conditions:
            context_str += f"Rules: {requirements.conditions[0]}\n"

        already_known = []
        if context.get('extracted_parameters'):
            for key, val in context['extracted_parameters'].items():
                if val and key != param_name:
                    already_known.append(f"{key}={val}")

        if already_known:
            context_str += f"Already know: {', '.join(already_known)}\n"

        user_prompt = f"{context_str}\nGenerate a natural, conversational question asking for: {param_name}"

        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=100
        )

        question = response.choices[0].message.content.strip()
        question = question.strip('"\'')
        return question

    except Exception as e:
        print(f"[Reasoning] LLM question generation failed: {e}")
        return fallback_template_question(param_name)


def fallback_template_question(param_name: str) -> str:
    """Fallback template questions if LLM unavailable."""
    templates = {
        'name': "What's your character's name?",
        'class_name': "What class are you?",
        'level': "What level are you starting at?",
        'target': "Which enemy do you want to attack?",
        'spell_name': "Which spell do you want to cast?",
        'weapon': "Which weapon do you want to use?",
        'skill': "Which skill do you want to use?"
    }
    return templates.get(param_name, f"What is your {param_name}?")


def extract_option_keywords(option_label: str) -> List[str]:
    """Extract searchable keywords from an option label."""
    label = re.sub(r'\([^)]*\)', '', option_label).strip()
    words = re.findall(r'\w+', label.lower())
    stopwords = {'of', 'the', 'a', 'an', 'and', 'or', 'for', 'to', 'in', 'on', 'at'}
    return [w for w in words if w not in stopwords and len(w) > 1]


def normalize_option_value(option_label: str, param_name: str) -> str:
    """Convert option label to normalized value for storage."""
    if param_name == 'ability_scores':
        label_lower = option_label.lower()
        if 'roll' in label_lower or '4d6' in label_lower:
            return 'roll'
        elif 'standard' in label_lower:
            return 'standard_array'
        elif 'point' in label_lower and 'buy' in label_lower:
            return 'point_buy'
    return option_label


def _get_spell_suggestions_from_rag(rag_query, class_name: str, level: int) -> List[str]:
    """Query RAG for class-specific spell suggestions."""
    try:
        query = f"D&D 5e {class_name} level {level} starting spells cantrips spell list"
        spells = rag_query.entity_manager.search_spells(
            query=query, class_name=class_name
        )[:8]

        if spells:
            return [spell.name for spell in spells]
        else:
            return ["Fireball", "Magic Missile", "Cure Wounds", "Shield", "Mage Armor"]
    except Exception as e:
        print(f"[Reasoning] Spell RAG query failed: {e}")
        return ["Fireball", "Magic Missile", "Cure Wounds", "Shield"]


def _get_subclass_suggestions_from_rag(rag_query, class_name: str) -> List[str]:
    """Query RAG for class-specific subclass options."""
    try:
        query = f"D&D 5e {class_name} subclass options archetypes traditions domains paths"
        rules = rag_query.entity_manager.search_rules(query=query, domain='classes')[:5]

        subclasses = []
        for rule in rules:
            content = rule.content.lower()
            if class_name.lower() == 'wizard':
                for school in ['evocation', 'abjuration', 'conjuration', 'divination']:
                    if school in content:
                        subclasses.append(f'School of {school.title()}')
            elif class_name.lower() == 'cleric':
                for domain in ['Life', 'War', 'Tempest', 'Light', 'Knowledge', 'Nature', 'Trickery']:
                    if domain.lower() in content:
                        subclasses.append(f'{domain} Domain')
            elif class_name.lower() == 'fighter':
                for archetype in ['Champion', 'Battle Master', 'Eldritch Knight']:
                    if archetype.lower() in content:
                        subclasses.append(archetype)

        subclasses = list(set(subclasses))
        if subclasses:
            return subclasses[:6]
        else:
            return [f"{class_name} Subclass Option 1", f"{class_name} Subclass Option 2"]

    except Exception as e:
        print(f"[Reasoning] Subclass RAG query failed: {e}")
        return [f"{class_name} Subclass Option 1", f"{class_name} Subclass Option 2"]
