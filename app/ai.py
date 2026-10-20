import httpx
from fastapi import HTTPException
from app.config import settings

SYSTEM = "You are MedNova AI, a medical information and learning assistant. You are not a doctor and must not present possibilities as confirmed diagnoses. Never invent sources, lab values, medical history, or clinical validations. Encourage urgent local emergency care for potentially life-threatening symptoms. Do not recommend starting, stopping, or changing prescription medicines. Be clear about uncertainty and answer in the user's requested language. This is informational support, not a substitute for qualified care."

async def answer(messages: list[dict], language: str = "en") -> str:
    if not settings.ai_api_key or not settings.ai_model:
        raise HTTPException(503, "AI service is not configured. Set AI_API_KEY and AI_MODEL on the server.")
    url = settings.ai_base_url.rstrip("/") + "/chat/completions"
    payload = {"model": settings.ai_model, "messages": [{"role": "system", "content": SYSTEM + f" Response language: {language}."}] + messages, "temperature": 0.2}
    try:
        async with httpx.AsyncClient(timeout=settings.ai_timeout_seconds) as client:
            response = await client.post(url, json=payload, headers={"Authorization": f"Bearer {settings.ai_api_key}"})
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise ValueError("Empty model response")
            return content.strip()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(502, f"AI provider returned HTTP {exc.response.status_code}")
    except (httpx.HTTPError, KeyError, IndexError, ValueError):
        raise HTTPException(502, "AI provider is unavailable or returned an invalid response. Your message has not been answered.")
