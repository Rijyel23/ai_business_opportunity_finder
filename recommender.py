from __future__ import annotations

import json
from typing import Any

from openai import BadRequestError, OpenAI, OpenAIError


MAX_LISTINGS_FOR_PROMPT = 30
DEFAULT_MODEL = "smart"


def rank_opportunities(
    listings: list[dict],
    criteria: str,
    api_key: str | None,
    base_url: str | None,
    model: str | None = None,
) -> list[dict]:
    if not listings:
        return []

    if not api_key or not base_url:
        return _heuristic_rank(listings, criteria)

    prompt = _build_prompt(listings[:MAX_LISTINGS_FOR_PROMPT], criteria)
    client = OpenAI(api_key=api_key, base_url=base_url)
    resolved_model = _resolve_model(client, model)

    try:
        response = _create_ranking_completion(client, resolved_model, prompt)
    except BadRequestError as exc:
        if "invalid model" not in str(exc).lower():
            raise
        resolved_model = _discover_first_model(client)
        response = _create_ranking_completion(client, resolved_model, prompt)

    content = response.choices[0].message.content or "[]"
    parsed = _parse_json_response(content)
    if not parsed:
        return _heuristic_rank(listings, criteria)

    return _normalize_recommendations(parsed, listings)


def _create_ranking_completion(client: OpenAI, model: str, prompt: str):
    return client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a practical business analyst. Rank listings by how well "
                    "they match the user's opportunity criteria. Return only valid JSON."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        max_tokens=1000,
        temperature=0.2,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )


def _resolve_model(client: OpenAI, model: str | None) -> str:
    normalized = (model or "").strip()
    if normalized and normalized.lower() not in {"default", "auto"}:
        return normalized

    return DEFAULT_MODEL


def _discover_first_model(client: OpenAI) -> str:
    try:
        models = client.models.list()
    except OpenAIError as exc:
        raise RuntimeError(
            "Could not auto-detect a model from the OpenAI-compatible endpoint. "
            "Set OPENAI_MODEL to one of the IDs returned by /v1/models."
        ) from exc

    for available_model in models.data:
        model_id = getattr(available_model, "id", None)
        if model_id:
            return model_id

    raise RuntimeError(
        "The OpenAI-compatible endpoint did not return any models. "
        "Ask Luke for the correct model name."
    )


def _build_prompt(listings: list[dict], criteria: str) -> str:
    payload = [
        {
            "index": index,
            "title": listing.get("title"),
            "company": listing.get("company"),
            "location": listing.get("location"),
            "price": listing.get("price"),
            "business_type": listing.get("business_type"),
            "category": listing.get("category"),
            "description": listing.get("description"),
            "full_description": listing.get("full_description"),
            "detail_sections": listing.get("detail_sections"),
            "posted_date": listing.get("posted_date"),
            "detail_posted_date": listing.get("detail_posted_date"),
            "url": listing.get("url"),
        }
        for index, listing in enumerate(listings)
    ]

    return f"""
User criteria:
{criteria}

Listings:
{json.dumps(payload, indent=2)}

Return a JSON array with up to 10 objects. Each object must contain:
- index: the original listing index
- title: listing title
- score: integer from 1 to 10
- reason: concise explanation of why it is promising
- suggested_next_step: practical follow-up action
Base the score primarily on the detail-page information when available.
"""


def _parse_json_response(content: str) -> Any:
    cleaned = content.strip()

    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("[")
        end = cleaned.rfind("]")
        if start >= 0 and end > start:
            try:
                return json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                return None

    return None


def _normalize_recommendations(parsed: Any, listings: list[dict]) -> list[dict]:
    if isinstance(parsed, dict):
        parsed = parsed.get("recommendations") or parsed.get("results") or []

    recommendations: list[dict] = []

    for item in parsed:
        if not isinstance(item, dict):
            continue

        listing = _listing_for_item(item, listings)
        normalized = {
            "title": item.get("title") or listing.get("title", "Untitled listing"),
            "score": item.get("score", 0),
            "reason": item.get("reason", "Recommended by the AI ranking model."),
            "suggested_next_step": item.get(
                "suggested_next_step",
                "Review the listing and qualify the business manually.",
            ),
            "url": item.get("url") or listing.get("url", ""),
        }
        recommendations.append(normalized)

    return sorted(recommendations, key=lambda item: int(item.get("score") or 0), reverse=True)


def _listing_for_item(item: dict, listings: list[dict]) -> dict:
    index = item.get("index")
    if isinstance(index, int) and 0 <= index < len(listings):
        return listings[index]
    return {}


def _heuristic_rank(listings: list[dict], criteria: str) -> list[dict]:
    criteria_terms = {
        term.lower()
        for term in criteria.replace(",", " ").replace(".", " ").split()
        if len(term) > 3
    }

    scored = []
    for listing in listings:
        text = " ".join(
            [
                listing.get("title", ""),
                listing.get("company", ""),
                listing.get("location", ""),
                listing.get("price", ""),
                listing.get("business_type", ""),
                listing.get("category", ""),
                listing.get("description", ""),
                listing.get("full_description", ""),
                listing.get("detail_text", ""),
            ]
        ).lower()
        matches = sum(1 for term in criteria_terms if term in text)
        detail_bonus = 2 if listing.get("detail_scraped") else 0
        description_bonus = 2 if len(listing.get("full_description") or listing.get("description", "")) > 250 else 0
        link_bonus = 1 if listing.get("url") else 0
        score = min(10, max(1, 4 + matches + detail_bonus + description_bonus + link_bonus))

        scored.append(
            {
                "title": listing.get("title", "Untitled listing"),
                "score": score,
                "reason": (
                    "Fallback ranking based on keyword overlap, listing detail, and available link. "
                    "Add the API key to enable AI reasoning."
                ),
                "suggested_next_step": "Open the listing and verify fit against the criteria.",
                "url": listing.get("url", ""),
            }
        )

    return sorted(scored, key=lambda item: item["score"], reverse=True)[:10]
