"""OpenCode Console inference for one user's coaching and resume rewrites.

The host is fixed. Settings never accepts a URL, and the API key is encrypted
with a key derived from JWT_KEY. A rotated signing key makes saved keys
unreadable; callers fail closed instead of falling back to another provider.
"""

import base64
import hashlib
import logging
from collections.abc import Iterable

import httpx
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import OpenCodeConnection, User, utcnow
from app.services.ai import AiProviderError, AiTarget, ChatResult, _message_text, _read_content

logger = logging.getLogger(__name__)

INFERENCE_ROOT = "https://opencode.ai/inference"
MODELS_URL = f"{INFERENCE_ROOT}/v1/models"
DEFAULT_MODEL = "deepseek-v4.1-flash"
BROKEN_KEY = "The saved OpenCode key could not be read. Reconnect it in Settings."
KEY_REJECTED = "That API key was not accepted."
KEY_CANNOT_LIST = "That API key cannot list models."
MODEL_UNAVAILABLE = "That model is not available."
INFERENCE_KEY_REJECTED = "OpenCode rejected the API key."
TEST_PROMPT = "Reply with the single word ok."

# Free on the pricing table, but the id does not end in -free.
FREE_IDS = {"big-pickle"}
# Image generation is not a chat turn. Match id fragments, not display names.
IMAGE_MARKERS = ("gpt-image", "dall-e", "imagen", "flux", "stable-diffusion", "image-gen")

# Live /v1/models returns ids only. Families come from the Console model table so
# an unknown id is hidden instead of guessed. Paid text models are included even
# when their native API is Anthropic or Gemini: Console translates those onto
# chat completions and the Responses API. Free-tier chat models, Jev / System
# One, and image-only models are omitted because this client cannot use them.
FAMILIES: dict[str, str] = {
    "qwen3.8-max": "chat",
    "deepseek-v4.1-flash": "chat",
    "deepseek-v4-pro": "chat",
    "minimax-m3": "chat",
    "minimax-m2.7": "chat",
    "minimax-m2.5": "chat",
    "glm-5.3-flash": "chat",
    "glm-5.3": "chat",
    "glm-5.2": "chat",
    "glm-5.1": "chat",
    "glm-5": "chat",
    "kimi-k2.7-code": "chat",
    "kimi-k3": "chat",
    "kimi-k2.6": "chat",
    "kimi-k2.5": "chat",
    "mistral-large-4": "chat",
    "gpt-6-astra": "responses",
    "gpt-6-sol": "responses",
    "gpt-6.1-sol": "responses",
    "gpt-6-luna": "responses",
    "gpt-5.6-sol": "responses",
    "gpt-5.6-terra": "responses",
    "gpt-5.6-luna": "responses",
    "gpt-5.5": "responses",
    "gpt-5.5-pro": "responses",
    "gpt-5.4": "responses",
    "gpt-5.4-pro": "responses",
    "gpt-5.4-mini": "responses",
    "gpt-5.4-nano": "responses",
    "gpt-5.3-codex-spark": "responses",
    "gpt-5.3-codex": "responses",
    "gpt-5.2": "responses",
    "gpt-5.2-codex": "responses",
    "gpt-5.1": "responses",
    "gpt-5.1-codex": "responses",
    "gpt-5.1-codex-max": "responses",
    "gpt-5.1-codex-mini": "responses",
    "gpt-5": "responses",
    "gpt-5-codex": "responses",
    "gpt-5-nano": "responses",
    "grok-4.7": "responses",
    "grok-4.6": "responses",
    "grok-4.5": "responses",
    "grok-build-0.1": "responses",
    "muse-wonder-1.0": "responses",
    "muse-spark-1.3": "responses",
    "muse-spark-1.2": "responses",
    "claude-fable-5-1": "anthropic",
    "claude-fable-5": "anthropic",
    "claude-opus-5-5": "anthropic",
    "claude-opus-5": "anthropic",
    "claude-opus-4-8": "anthropic",
    "claude-opus-4-7": "anthropic",
    "claude-opus-4-6": "anthropic",
    "claude-opus-4-5": "anthropic",
    "claude-sonnet-5-5": "anthropic",
    "claude-sonnet-5": "anthropic",
    "claude-sonnet-4-6": "anthropic",
    "claude-sonnet-4-5": "anthropic",
    "claude-haiku-5-5": "anthropic",
    "claude-haiku-4-5": "anthropic",
    "qwen3.8-flash": "anthropic",
    "qwen3.6-plus": "anthropic",
    "qwen3.5-plus": "anthropic",
    "gemini-4-argon": "gemini",
    "gemini-3.8-flash": "gemini",
    "gemini-3.7-flash": "gemini",
    "gemini-3.6-flash": "gemini",
    "gemini-3.5-flash": "gemini",
    "gemini-3.5-flash-lite": "gemini",
    "gemini-3.1-pro": "gemini",
    "gemini-3-flash": "gemini",
}


class OpenCodeError(Exception):
    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def key_hint(api_key: str) -> str:
    cleaned = api_key.strip()
    return f"{cleaned[:10]}…"


def clean_api_key(value: str) -> str:
    key = value.strip()
    if any(char.isspace() for char in key) or len(key) < 8 or len(key) > 500:
        raise OpenCodeError("That API key does not look valid.", 400)
    return key


def require_model(model_id: str) -> str:
    model = model_id.strip()
    if _free(model):
        raise OpenCodeError(MODEL_UNAVAILABLE, 400)
    if model not in FAMILIES or _non_chat(model):
        raise OpenCodeError("Choose a supported OpenCode model.", 400)
    return model


def encrypt_key(api_key: str, secret: str) -> str:
    return _fernet(secret).encrypt(api_key.encode("utf-8")).decode("ascii")


def decrypt_key(token: str, secret: str) -> str:
    return _fernet(secret).decrypt(token.encode("ascii")).decode("utf-8")


def resolve_ai(user: User, db: Session, settings: Settings | None = None) -> AiTarget:
    """Prefer the user's OpenCode connection. A saved but unreadable key does not fall back."""
    settings = settings or get_settings()
    row = connection_for(user, db)
    if row is not None:
        try:
            key = decrypt_key(row.api_key_ciphertext, settings.jwt_key)
        except (InvalidToken, ValueError, OpenCodeError):
            return AiTarget("none", notice=BROKEN_KEY)
        if not key:
            return AiTarget("none", notice=BROKEN_KEY)
        return AiTarget("opencode", model_id=row.model_id, api_key=key)
    if settings.ai_endpoint:
        return AiTarget("env")
    return AiTarget("none")


def connection_for(user: User, db: Session) -> OpenCodeConnection | None:
    return db.get(OpenCodeConnection, user.id)


def list_models(client: httpx.Client | None = None, api_key: str = "") -> list[dict[str, str]]:
    """Chat models this app can call. A key limits the list to ids that key can see."""
    live = _fetch_ids(api_key, client)
    chosen = [model_id for model_id in FAMILIES if _selectable(model_id) and (live is None or model_id in live)]
    chosen.sort(key=lambda item: (item != DEFAULT_MODEL, item))
    return [{"id": model_id, "family": FAMILIES[model_id]} for model_id in chosen]


def verify_key(api_key: str, client: httpx.Client | None = None) -> set[str]:
    """Confirm the key can list models. Returns chat ids this app can call with it."""
    return {item["id"] for item in list_models(client, api_key)}


def ensure_available(model_id: str, live_ids: set[str]) -> None:
    if model_id not in live_ids:
        raise OpenCodeError(MODEL_UNAVAILABLE, 400)


def complete_opencode(
    messages: list[dict[str, str]],
    model_id: str,
    api_key: str,
    client: httpx.Client | None = None,
) -> ChatResult:
    """Call the Console family for this model. Raises AiProviderError on failure."""
    if _free(model_id) or _non_chat(model_id):
        raise AiProviderError(MODEL_UNAVAILABLE)
    family = FAMILIES.get(model_id)
    if not family:
        raise AiProviderError("That OpenCode model is not supported.")
    url, payload = _request_for(family, model_id, messages)
    try:
        response = _send("POST", url, api_key=api_key, json=payload, client=client)
    except httpx.HTTPError as exc:
        logger.warning("OpenCode request failed: %s", type(exc).__name__)
        raise AiProviderError("The OpenCode request failed.") from exc
    if response.status_code == 401:
        raise AiProviderError(INFERENCE_KEY_REJECTED)
    if response.status_code == 403:
        raise AiProviderError(MODEL_UNAVAILABLE)
    if response.status_code >= 400:
        logger.warning("OpenCode request failed: HTTP %s", response.status_code)
        raise AiProviderError("The OpenCode request failed.")
    try:
        content = read_opencode_text(response.json())
    except ValueError as exc:
        raise AiProviderError("The OpenCode request failed.") from exc
    if not content or not content.strip():
        raise AiProviderError("OpenCode returned no content.")
    return ChatResult(content.strip(), True)


def read_opencode_text(root: object) -> str | None:
    text = _read_content(root)
    if text and text.strip():
        return text
    if not isinstance(root, dict):
        return None
    return _responses_text(root) or _gemini_text(root)


def save_connection(db: Session, user: User, api_key: str, model_id: str, settings: Settings) -> OpenCodeConnection:
    row = connection_for(user, db)
    if row is None:
        row = OpenCodeConnection(user_id=user.id)
        db.add(row)
    row.api_key_ciphertext = encrypt_key(api_key, settings.jwt_key)
    row.key_hint = key_hint(api_key)
    row.model_id = model_id
    row.last_checked_at = utcnow()
    row.last_error = ""
    db.commit()
    db.refresh(row)
    return row


def stored_key(row: OpenCodeConnection, settings: Settings) -> str:
    try:
        return decrypt_key(row.api_key_ciphertext, settings.jwt_key)
    except (InvalidToken, ValueError, OpenCodeError) as exc:
        raise OpenCodeError(BROKEN_KEY, 400) from exc


def mark_check(db: Session, row: OpenCodeConnection, error: str) -> None:
    row.last_checked_at = utcnow()
    row.last_error = error[:300]
    db.commit()


def _fernet(secret: str) -> Fernet:
    if not secret:
        raise OpenCodeError("Server signing key is not configured.", 500)
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _selectable(model_id: str) -> bool:
    return model_id in FAMILIES and not _free(model_id) and not _non_chat(model_id)


def _free(model_id: str) -> bool:
    lowered = model_id.lower()
    return lowered.endswith("-free") or lowered in FREE_IDS


def _non_chat(model_id: str) -> bool:
    lowered = model_id.lower()
    if lowered.startswith("jev") or "systemone" in lowered:
        return True
    return any(marker in lowered for marker in IMAGE_MARKERS)


def _fetch_ids(api_key: str, client: httpx.Client | None) -> set[str] | None:
    """Live ids for this key. None means the public catalog could not be read."""
    key = api_key.strip()
    try:
        response = _send("GET", MODELS_URL, api_key=key, client=client)
    except httpx.HTTPError as exc:
        if key:
            logger.warning("OpenCode model list failed: %s", type(exc).__name__)
            raise OpenCodeError("Could not reach OpenCode.", 502) from exc
        return None
    if key and response.status_code == 401:
        raise OpenCodeError(KEY_REJECTED, 400)
    if key and response.status_code == 403:
        raise OpenCodeError(KEY_CANNOT_LIST, 400)
    if response.status_code >= 400:
        if key:
            logger.warning("OpenCode model list failed: HTTP %s", response.status_code)
            raise OpenCodeError("Could not reach OpenCode.", 502)
        return None
    try:
        return _model_ids(response.json())
    except ValueError as exc:
        if key:
            raise OpenCodeError("Could not reach OpenCode.", 502) from exc
        return None


def _model_ids(root: object) -> set[str]:
    if not isinstance(root, dict):
        return set()
    data = root.get("data")
    if not isinstance(data, list):
        return set()
    return {item["id"] for item in data if isinstance(item, dict) and isinstance(item.get("id"), str)}


def _send(
    method: str,
    url: str,
    *,
    api_key: str,
    json: dict | None = None,
    client: httpx.Client | None = None,
) -> httpx.Response:
    if not url.startswith(f"{INFERENCE_ROOT}/"):
        raise OpenCodeError("OpenCode requests must stay on opencode.ai.", 500)
    headers = {"Accept": "application/json"}
    if json is not None:
        headers["Content-Type"] = "application/json"
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    owns = client is None
    http = client or httpx.Client(timeout=45, follow_redirects=False)
    try:
        response = http.request(method, url, headers=headers, json=json)
        response.read()
        return response
    finally:
        if owns:
            http.close()


def _request_for(family: str, model_id: str, messages: list[dict[str, str]]) -> tuple[str, dict]:
    system, turns = _split(messages)
    if family == "chat":
        chat_messages = messages or [{"role": "user", "content": TEST_PROMPT}]
        payload = {"model": model_id, "messages": chat_messages, "temperature": 0.2}
        return f"{INFERENCE_ROOT}/openai/v1/chat/completions", payload
    if family == "responses":
        payload = {"model": model_id, "input": turns or TEST_PROMPT}
        if system:
            payload["instructions"] = system
        return f"{INFERENCE_ROOT}/openai/v1/responses", payload
    if family == "anthropic":
        payload = {"model": model_id, "max_tokens": 4096, "messages": _alternate(turns)}
        if system:
            payload["system"] = system
        return f"{INFERENCE_ROOT}/anthropic/v1/messages", payload
    contents = [
        {"role": "model" if turn["role"] == "assistant" else "user", "parts": [{"text": turn["content"]}]}
        for turn in turns
    ]
    if not contents:
        contents = [{"role": "user", "parts": [{"text": TEST_PROMPT}]}]
    payload = {"contents": contents, "generationConfig": {"temperature": 0.2}}
    if system:
        payload["systemInstruction"] = {"parts": [{"text": system}]}
    return f"{INFERENCE_ROOT}/google/v1beta/models/{model_id}:generateContent", payload


def _split(messages: Iterable[dict[str, str]]) -> tuple[str, list[dict[str, str]]]:
    system: list[str] = []
    turns: list[dict[str, str]] = []
    for message in messages:
        role = message.get("role") or "user"
        content = message.get("content") or ""
        if role == "system":
            if content.strip():
                system.append(content.strip())
            continue
        turns.append({"role": "assistant" if role == "assistant" else "user", "content": content})
    while turns and turns[0]["role"] != "user":
        if turns[0]["content"].strip():
            system.append(turns[0]["content"].strip())
        turns.pop(0)
    return "\n\n".join(system), turns


def _alternate(turns: list[dict[str, str]]) -> list[dict[str, str]]:
    merged: list[dict[str, str]] = []
    for turn in turns:
        if merged and merged[-1]["role"] == turn["role"]:
            merged[-1]["content"] = f"{merged[-1]['content']}\n\n{turn['content']}"
        else:
            merged.append(dict(turn))
    return merged or [{"role": "user", "content": TEST_PROMPT}]


def _responses_text(root: dict) -> str | None:
    output = root.get("output")
    if not isinstance(output, list):
        return None
    parts: list[str] = []
    for item in output:
        if not isinstance(item, dict) or item.get("type") not in {None, "message"}:
            continue
        text = _message_text(item.get("content"))
        if text:
            parts.append(text)
    return "\n".join(parts) if parts else None


def _gemini_text(root: dict) -> str | None:
    candidates = root.get("candidates")
    if not isinstance(candidates, list):
        return None
    parts: list[str] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        content = candidate.get("content")
        if not isinstance(content, dict):
            continue
        text = _message_text(content.get("parts"))
        if text:
            parts.append(text)
    return "\n".join(parts) if parts else None
