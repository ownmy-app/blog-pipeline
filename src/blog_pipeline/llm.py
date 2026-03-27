"""
LLM abstraction layer — routes to anthropic, openai, or litellm.

Provider selection:
    LLM_PROVIDER=anthropic  (default)
    LLM_PROVIDER=openai
    LLM_PROVIDER=litellm

Model override:
    LLM_MODEL=claude-opus-4-5  (anthropic default)
    LLM_MODEL=gpt-4o            (openai default)
    LLM_MODEL=...               (litellm passes through)
"""

import os

_PROVIDER_DEFAULTS = {
    "anthropic": "claude-opus-4-5",
    "openai": "gpt-4o",
    "litellm": "claude-opus-4-5",
}


def _get_provider() -> str:
    """Return the LLM provider name (lowercase)."""
    return os.environ.get("LLM_PROVIDER", "anthropic").strip().lower()


def _get_model(provider: str = None) -> str:
    """Return the model string for the active provider."""
    p = provider or _get_provider()
    explicit = os.environ.get("LLM_MODEL", "").strip()
    if explicit:
        return explicit
    # Legacy fallback: CLAUDE_MODEL env var for anthropic
    if p == "anthropic":
        legacy = os.environ.get("CLAUDE_MODEL", "").strip()
        if legacy:
            return legacy
    return _PROVIDER_DEFAULTS.get(p, "claude-opus-4-5")


def _ask_anthropic(prompt: str, system: str = "", max_tokens: int = 8096) -> str:
    """Call Anthropic Messages API."""
    try:
        import anthropic
    except ImportError:
        raise ImportError(
            "anthropic SDK is not installed. Run: pip install anthropic"
        )

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set. See .env.example.")

    client = anthropic.Anthropic(api_key=api_key)
    kwargs = dict(
        model=_get_model("anthropic"),
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    if system:
        kwargs["system"] = system
    msg = client.messages.create(**kwargs)
    return (msg.content[0].text or "").strip()


def _ask_openai(prompt: str, system: str = "", max_tokens: int = 8096) -> str:
    """Call OpenAI ChatCompletion API."""
    try:
        import openai
    except ImportError:
        raise ImportError(
            "openai SDK is not installed. Run: pip install 'blog-pipeline[openai]'"
        )

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    client = openai.OpenAI(api_key=api_key)
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    resp = client.chat.completions.create(
        model=_get_model("openai"),
        max_tokens=max_tokens,
        messages=messages,
    )
    return (resp.choices[0].message.content or "").strip()


def _ask_litellm(prompt: str, system: str = "", max_tokens: int = 8096) -> str:
    """Call any model via litellm unified interface."""
    try:
        import litellm
    except ImportError:
        raise ImportError(
            "litellm is not installed. Run: pip install 'blog-pipeline[litellm]'"
        )

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    resp = litellm.completion(
        model=_get_model("litellm"),
        max_tokens=max_tokens,
        messages=messages,
    )
    return (resp.choices[0].message.content or "").strip()


_PROVIDERS = {
    "anthropic": _ask_anthropic,
    "openai": _ask_openai,
    "litellm": _ask_litellm,
}


def ask_llm(prompt: str, system: str = "", max_tokens: int = 8096) -> str:
    """
    Send a prompt to the configured LLM provider and return the text response.

    Reads LLM_PROVIDER and LLM_MODEL from environment. Falls back to
    anthropic / claude-opus-4-5 when not set.

    Args:
        prompt:     User message to send.
        system:     Optional system prompt.
        max_tokens: Maximum tokens in the response.

    Returns:
        The model's text response, stripped of leading/trailing whitespace.
    """
    provider = _get_provider()
    fn = _PROVIDERS.get(provider)
    if fn is None:
        supported = ", ".join(sorted(_PROVIDERS))
        raise ValueError(
            f"Unknown LLM_PROVIDER={provider!r}. Supported: {supported}"
        )
    return fn(prompt, system=system, max_tokens=max_tokens)
