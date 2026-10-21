import logging
from dataclasses import dataclass

import httpx

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


class AiProviderError(Exception):
    """The configured chat provider did not return usable text."""


@dataclass(frozen=True)
class ChatResult:
    content: str
    provider_used: bool


def complete_chat(
    messages: list[dict[str, str]],
    settings: Settings | None = None,
    client: httpx.Client | None = None,
) -> ChatResult:
    """Call an OpenAI-compatible chat endpoint. Raises AiProviderError on failure."""
    settings = settings or get_settings()
    if not settings.ai_endpoint:
        raise AiProviderError("AI provider is not configured.")
    payload: dict[str, object] = {"messages": messages, "temperature": 0.2}
    if settings.ai_model:
        payload["model"] = settings.ai_model
    headers = {"Content-Type": "application/json"}
    if settings.ai_api_key:
        header = settings.ai_api_key_header or "Authorization"
        value = settings.ai_api_key
        if header.lower() == "authorization" and not value.lower().startswith(("bearer ", "basic ")):
            value = f"Bearer {value}"
        headers[header] = value
    owns_client = client is None
    http = client or httpx.Client(timeout=45)
    try:
        response = http.post(settings.ai_endpoint, json=payload, headers=headers)
        response.raise_for_status()
        content = _read_content(response.json())
        if not content or not content.strip():
            raise AiProviderError("The AI provider returned no content.")
        return ChatResult(content.strip(), True)
    except AiProviderError:
        raise
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("AI provider request failed: %s", type(exc).__name__)
        raise AiProviderError("The AI provider request failed.") from exc
    finally:
        if owns_client:
            http.close()


def _read_content(root: object) -> str | None:
    if isinstance(root, str):
        return root
    if not isinstance(root, dict):
        return None
    for key in ("content", "text", "output_text", "reply"):
        text = _message_text(root.get(key))
        if text:
            return text
    choices = root.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        first = choices[0]
        message = first.get("message")
        if isinstance(message, dict):
            text = _message_text(message.get("content"))
            if text:
                return text
        if isinstance(first.get("text"), str):
            return first["text"]
    return None


def _message_text(content: object) -> str | None:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return None
    parts: list[str] = []
    for item in content:
        if isinstance(item, str):
            parts.append(item)
        elif isinstance(item, dict) and isinstance(item.get("text"), str):
            parts.append(item["text"])
    return "\n".join(parts) if parts else None
