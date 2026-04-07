"""
Groq LLM client - free OSS models (llama3-70b, mixtral, gemma2 etc.)
"""
import os
import json
import logging
from groq import Groq

logger = logging.getLogger(__name__)

# Free Groq models to cycle through if rate limited
FREE_MODELS = [
    "openai/gpt-oss-120b",
    "llama-3.1-8b-instant",
    "llama-3.3-70b-versatile",
    "openai/gpt-oss-20b",
]

client = Groq(api_key=os.getenv("GROQ_API_KEY", ""))


def chat(messages: list[dict], system: str = "", model: str = FREE_MODELS[0], temperature: float = 0.3) -> str:
    """
    Single-turn or multi-turn chat with Groq.
    Returns the assistant reply as a string.
    """
    full_messages = []
    if system:
        full_messages.append({"role": "system", "content": system})
    full_messages.extend(messages)

    # Try each model in order if rate-limited
    for m in [model] + [x for x in FREE_MODELS if x != model]:
        try:
            logger.info(f"Calling Groq model: {m}")
            resp = client.chat.completions.create(
                model=m,
                messages=full_messages,
                temperature=temperature,
                max_tokens=2048,
            )
            return resp.choices[0].message.content
        except Exception as e:
            if "rate_limit" in str(e).lower() or "429" in str(e):
                logger.warning(f"Rate limited on {m}, trying next model...")
                continue
            logger.error(f"Groq error: {e}")
            raise
    raise RuntimeError("All Groq models rate-limited. Try again in a minute.")


def chat_json(messages: list[dict], system: str = "", model: str = FREE_MODELS[0]) -> dict:
    """
    Like chat() but parses and returns JSON. Retries once on parse failure.
    """
    system_json = system + "\n\nIMPORTANT: Respond ONLY with valid JSON. No markdown, no explanation."
    raw = chat(messages, system=system_json, model=model, temperature=0.1)
    # Strip markdown fences if model misbehaves
    raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("JSON parse failed, retrying with stricter prompt...")
        messages2 = messages + [
            {"role": "assistant", "content": raw},
            {"role": "user", "content": "That was not valid JSON. Reply ONLY with the raw JSON object, nothing else."}
        ]
        raw2 = chat(messages2, system=system_json, model=model, temperature=0.0)
        raw2 = raw2.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        return json.loads(raw2)