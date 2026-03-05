"""Configuration management"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SRD_DIR = DATA_DIR / "srd"
VECTOR_DB_DIR = DATA_DIR / "vector_dbs"

# Database paths
REFERENCE_DB_PATH = DATA_DIR / "reference.db"
GAME_STATE_DB_PATH = DATA_DIR / "game_state.db"

# API Configuration
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

# Embedding Configuration
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "openai")  # "openai" or "local"
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

# Agent Configuration (which LLM to use for DM)
AGENT_PROVIDER = os.getenv("AGENT_PROVIDER", "openai")  # "openai" or "anthropic"

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
VECTOR_DB_DIR.mkdir(exist_ok=True)

# Validate configuration
if AGENT_PROVIDER == "anthropic" and not ANTHROPIC_API_KEY:
    print("WARNING: ANTHROPIC_API_KEY not set in .env file")
if AGENT_PROVIDER == "openai" and not OPENAI_API_KEY:
    print("WARNING: OPENAI_API_KEY not set in .env file")
if EMBEDDING_PROVIDER == "openai" and not OPENAI_API_KEY:
    print("WARNING: OPENAI_API_KEY needed for embeddings but not set in .env file")
