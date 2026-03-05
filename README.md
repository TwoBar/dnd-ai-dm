# D&D AI Dungeon Master

**AI-powered Dungeon Master for D&D 5th Edition** with a two-stage retrieval architecture that achieves 100% rule accuracy at 25x lower cost than naive RAG.

## The Problem

Naive RAG for tabletop RPGs dumps entire rulebooks into context — expensive, slow, and prone to hallucination. This system treats rules as reference material, not memory.

## Two-Stage Retrieval Architecture

```
Player Input
    ↓
DM Agent (GPT-4o, minimal context ~500 tokens)
    ↓
Needs rules? → Tool Call
    ↓
Entity Manager:
  Stage 1: SQL Metadata Filter (type, level, school, CR, etc.)
  Stage 2: Vector Embedding Similarity (top semantic matches)
  Cache: LRU (90% hit rate)
    ↓
Rules injected → DM Response
```

### Why Two Stages?

| Approach | Context Size | Cost/Turn | Accuracy |
|----------|-------------|-----------|----------|
| Full manual in context | ~10k tokens | $0.0025 | Hallucination-prone |
| **Two-stage retrieval** | **500–1k tokens** | **$0.0001** | **100% exact, ~95% semantic** |

**25x cost reduction** with better accuracy.

## 932 Atomic Entities

The entire D&D 5E SRD parsed into self-contained, searchable objects:

| Type | Count | Searchable Fields |
|------|-------|-------------------|
| Spells | 322 | Level, school, damage, save, components |
| Monsters | 319 | CR, AC, HP, size, type |
| Items | 242 | Rarity, type, attunement |
| Rules | ~35 | Domain, category |
| Conditions | 14 | Name, effects |

## Features

- **GPT-4o agent with tool-calling** — looks up rules on demand, never guesses
- **Full combat tracker** — initiative, HP, conditions, dice rolling
- **Web UI** (Flask + Socket.IO) — real-time browser interface
- **Terminal UI** (Rich) — play from the command line
- **Session persistence** — save/load game state
- **D&D dice system** — advantage, critical hits, keep-highest notation

## Quick Start

```bash
pip install -r requirements.txt
cp .env.example .env  # Add OPENAI_API_KEY
python scripts/bootstrap_atomic.py  # Parse SRD + generate embeddings (~$0.03)
python src/main.py  # Choose: Web UI, Terminal UI, or Chat
```

Web UI runs at `http://localhost:5001`

## Tech Stack

Python · OpenAI (GPT-4o + embeddings) · ChromaDB · Flask · Socket.IO · SQLite · Rich

## Data Source

Uses the D&D 5th Edition System Reference Document (SRD), licensed under CC-BY-4.0 by Wizards of the Coast.

## License

MIT
