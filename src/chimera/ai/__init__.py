"""CHIMERA AI Providers.

Provides unified interface for:
- Vision analysis (OpenAI, Claude, BLIP-2)
- Embeddings (OpenAI, Sentence-Transformers)
- Summarization (Claude, GPT-4)
"""

from typing import Dict, Any, Optional
import os


def get_api_key(provider: str) -> Optional[str]:
    """Get API key for provider from environment."""
    key_map = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "claude": "ANTHROPIC_API_KEY",
        "cohere": "COHERE_API_KEY",
        "voyage": "VOYAGE_API_KEY",
    }
    
    env_var = key_map.get(provider.lower())
    if env_var:
        return os.getenv(env_var)
    return None


def list_available_providers() -> Dict[str, bool]:
    """List which AI providers have API keys configured."""
    providers = ["openai", "anthropic", "cohere", "voyage"]
    
    return {
        provider: get_api_key(provider) is not None
        for provider in providers
    }
