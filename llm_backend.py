"""
LLM backend abstraction — Anthropic API and Ollama (local).
"""

import os
import sys
import time

_backend = None
_model = None
_client = None


def init_backend(backend: str = "anthropic", model: str | None = None):
    global _backend, _model, _client

    _backend = backend

    if backend == "anthropic":
        import anthropic
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            print("ERROR: Set ANTHROPIC_API_KEY environment variable")
            sys.exit(1)
        _client = anthropic.Anthropic(api_key=api_key)
        _model = model or "claude-haiku-4-5-20251001"

    elif backend == "ollama":
        import httpx
        _model = model or "qwen2.5:32b"
        # Check Ollama is running
        try:
            resp = httpx.get("http://localhost:11434/api/tags", timeout=5)
            resp.raise_for_status()
            available = [m["name"] for m in resp.json().get("models", [])]
            # Ollama model names may include :latest suffix
            found = any(_model in name for name in available)
            if not found:
                print(f"WARNING: Model '{_model}' not found in Ollama. Available: {available}")
                print(f"  Try: ollama pull {_model}")
        except Exception:
            print("ERROR: Cannot connect to Ollama. Is it running? Try: ollama serve")
            sys.exit(1)
        _client = httpx.Client(timeout=120)

    else:
        print(f"ERROR: Unknown backend '{backend}'. Use 'anthropic' or 'ollama'.")
        sys.exit(1)

    print(f"Backend: {backend} | Model: {_model}")


def get_backend() -> str:
    """Return the current backend name ('anthropic' or 'ollama')."""
    return _backend


def is_local() -> bool:
    """Return True if the current backend is local (not sending data to a cloud API)."""
    return _backend == "ollama"


def call_llm(prompt: str, system: str = "", max_tokens: int = 1024) -> str:
    if _backend is None:
        raise RuntimeError("Call init_backend() first")

    if _backend == "anthropic":
        msgs = [{"role": "user", "content": prompt}]
        kwargs = {"model": _model, "max_tokens": max_tokens, "messages": msgs}
        if system:
            kwargs["system"] = system
        resp = _client.messages.create(**kwargs)
        time.sleep(0.3)  # rate limit
        return resp.content[0].text

    elif _backend == "ollama":
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        resp = _client.post(
            "http://localhost:11434/api/generate",
            json={"model": _model, "prompt": full_prompt, "stream": False},
        )
        resp.raise_for_status()
        return resp.json()["response"]
