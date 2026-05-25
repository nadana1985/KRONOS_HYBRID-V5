"""
KRONOS Token Proxy Engine (Pillar 2 Compliance)
================================================
Centralizes LLM routing, fallback models, caching, and budget tracking via LiteLLM.
All models and fallbacks are configured in params_yaml.txt under cfg["tokens"].
"""
import os
from typing import Dict, Any
import litellm

def execute_completion(prompt_payload: Dict[str, Any], config: Dict) -> Dict[str, Any]:
    """
    Executes a structured completion using litellm with fallback models and active caching.
    """
    token_cfg = config["tokens"]
    const = config["reproducibility"]["constants"]
    
    # Configure LiteLLM global options dynamically from environment
    litellm.api_key = os.getenv("LITELLM_API_KEY")
    litellm.cache = litellm.Cache(type=token_cfg.get("cache_type", "disk"))
    
    # Construct message structure causally
    messages_payload = [{"role": token_cfg.get("user_role_key", "user"), "content": prompt_payload["content"]}]
    
    try:
        response = litellm.completion(
            model=token_cfg["primary_model"],
            messages=messages_payload,
            temperature=float(token_cfg["temperature"]),
            max_tokens=int(token_cfg["max_tokens"]),
            caching=True,
            fallbacks=token_cfg["fallback_models"]
        )
        return response
    except Exception as exc:
        raise RuntimeError(f"LiteLLM universal completion failed: {exc}")
