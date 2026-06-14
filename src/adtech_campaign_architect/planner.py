from __future__ import annotations

import json
import math
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import llm_client
from .prompts import render_prompt


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
_LLAMAINDEX_CACHE: dict[str, Any] = {}
_LLAMAINDEX_CACHE_LOCK = threading.Lock()
_LLAMAINDEX_EMBED_MODEL: Any = None

CATEGORY_KEYWORDS = {
    "pet": ["dog", "cat", "pet", "puppy", "kitten", "treat", "vet", "joint", "senior dogs"],
    "apparel": ["activewear", "clothes", "apparel", "fashion", "socks", "underwear", "outerwear", "shells"],
    "wellness": ["wellness", "supplement", "vitamin", "fitness", "workout", "health", "adaptogen", "sleep"],
    "beauty": ["beauty", "skincare", "makeup", "hair", "cosmetic"],
    "home": ["home", "bedding", "linen", "cookware", "kitchen", "cleaning", "candle", "bath"],
    "groceries": ["grocery", "pantry", "organic", "food", "meal", "protein bar"],
    "beverages": ["drink", "beverage", "soda", "sparkling", "cocktail", "non-alcoholic"],
    "instant_delivery": ["delivery", "convenience", "late-night", "household", "quick"],
    "meal_kits": ["meal kit", "dinner", "recipe", "family meals"],
    "b2b": ["b2b", "saas", "dental", "workflow", "practice", "software"],
}

ATTRIBUTE_KEYWORDS = {
    "premium": ["premium", "luxury", "handcrafted", "italian", "quality", "heritage", "650", "1200"],
    "subscription": ["subscription", "subscribe", "monthly", "box", "repeat"],
    "sustainability": ["sustainable", "recycled", "refillable", "plastic", "eco", "natural", "soy"],
    "science": ["vet", "formulated", "science", "evidence", "ingredient", "clinical"],
    "convenience": ["easy", "quick", "convenience", "time", "one-click", "automate"],
    "gifting": ["gift", "gifts", "holiday", "candles", "presentation"],
    "value": ["price", "half", "discount", "cheap", "value", "compete on price"],
    "women": ["women", "moms", "female", "her"],
    "family": ["family", "kids", "parent", "moms"],
    "performance": ["technical", "performance", "workout", "patrollers", "creatine", "protein"],
}

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "our",
    "that",
    "the",
    "their",
    "to",
    "we",
    "with",
    "who",
    "want",
    "kind",
    "like",
}


@dataclass(frozen=True)
class Match:
    item: dict[str, Any]
    score: float
    reasons: list[str]
    cautions: list[str]


def build_campaign(advertiser_description: str, top_publishers: int = 4) -> dict[str, Any]:
    """Create a reviewable campaign draft from one advertiser description."""
    publishers = _load_json("publishers.json")
    personas = _load_json("shopper_personas.json")
    understanding = understand_advertiser(advertiser_description)
    if _needs_clarification(understanding):
        return _clarification_response(advertiser_description, understanding)

    publisher_matches = rank_publishers(advertiser_description, understanding, publishers)
    publisher_candidates = _select_publishers(understanding, publisher_matches, min(top_publishers, 2))
    persona_matches = rank_personas(advertiser_description, understanding, personas)
    persona_candidates = persona_matches[:2]
    if not publisher_candidates or not persona_candidates:
        return _clarification_response(advertiser_description, understanding, publisher_matches)

    llm_choice = choose_best_candidates(understanding, publisher_candidates, persona_candidates)
    selected_publishers = _apply_llm_publisher_choice(publisher_candidates, llm_choice)
    selected_personas = _apply_llm_persona_choice(persona_candidates, llm_choice)
    creative_personas = _select_creative_personas(selected_personas[0].item["id"], persona_candidates, limit=2)
    campaign_draft = generate_campaign_draft(
        advertiser_description,
        understanding,
        publisher_candidates,
        selected_publishers,
        creative_personas,
    )
    candidate_ids = {match.item["id"] for match in publisher_candidates}

    return {
        "advertiser_understanding": understanding,
        "recommended_publishers": [_match_to_payload(match, llm_choice) for match in publisher_candidates],
        "recommended_personas": [_persona_payload(match, llm_choice) for match in persona_candidates],
        "llm_selection": llm_choice,
        "excluded_publishers": [_excluded_payload(match) for match in publisher_matches if match.item["id"] not in candidate_ids],
        "creative_variants": campaign_draft["creative_variants"],
        "psychological_blueprint": campaign_draft["psychological_blueprint"],
        "campaign_config": campaign_draft["campaign_config"],
        "debug": {
            "retrieval_engine": _retrieval_engine_name(),
            "llm_engine": _llm_engine_name(),
            "note": "Uses Ollama/Qwen for understanding, candidate selection, and campaign generation; uses LlamaIndex embeddings for semantic retrieval.",
        },
    }


def understand_advertiser(description: str) -> dict[str, Any]:
    text = description.strip()
    llm_understanding = _llm_understand_advertiser(text)
    if not llm_understanding:
        return _vague_understanding(text)
    return llm_understanding


def choose_best_candidates(
    understanding: dict[str, Any], publisher_candidates: list[Match], persona_candidates: list[Match]
) -> dict[str, Any]:
    if not publisher_candidates or not persona_candidates:
        raise RuntimeError("Candidate selection requires at least one publisher and one persona candidate.")

    prompt = render_prompt(
        "candidate_selection",
        {
            "advertiser_understanding": json.dumps(understanding, indent=2),
            "publisher_candidates": json.dumps([_match_to_payload(match) for match in publisher_candidates], indent=2),
            "persona_candidates": json.dumps([_persona_payload(match) for match in persona_candidates], indent=2),
        },
    )
    choice = llm_client.generate_json(prompt)
    if not choice:
        return _fallback_candidate_choice(publisher_candidates, persona_candidates, "LLM candidate selection failed.")

    publisher_ids = {match.item["id"] for match in publisher_candidates}
    persona_ids = {match.item["id"] for match in persona_candidates}
    selected_publisher_id = _resolve_candidate_id(choice.get("selected_publisher_id"), publisher_candidates)
    selected_persona_id = _resolve_candidate_id(choice.get("selected_persona_id"), persona_candidates)
    if selected_publisher_id not in publisher_ids or selected_persona_id not in persona_ids:
        return _fallback_candidate_choice(
            publisher_candidates,
            persona_candidates,
            "LLM candidate selection returned ids outside the retrieved candidate sets.",
        )
    selected_publisher_id, publisher_guardrail_reason = _guardrail_publisher_selection(
        selected_publisher_id, publisher_candidates, choice
    )

    return {
        "selected_publisher_id": selected_publisher_id,
        "selected_persona_id": selected_persona_id,
        "publisher_reasoning": _as_list(choice.get("publisher_reasoning")) + publisher_guardrail_reason,
        "persona_reasoning": _as_list(choice.get("persona_reasoning")),
        "click_hypothesis": str(choice.get("click_hypothesis") or ""),
        "confidence": str(choice.get("confidence") or "medium"),
        "source": llm_client.engine_name(),
    }


def generate_campaign_draft(
    advertiser_description: str,
    understanding: dict[str, Any],
    recommended_publishers: list[Match],
    selected_publishers: list[Match],
    creative_personas: list[Match],
) -> dict[str, Any]:
    if not recommended_publishers or not selected_publishers or not creative_personas:
        raise RuntimeError("Campaign generation requires publishers and creative personas.")

    persona_drafts: list[tuple[Match, dict[str, Any]]] = []
    for persona in creative_personas[:2]:
        prompt = render_prompt(
            "campaign_generation",
            {
                "product": understanding.get("product") or advertiser_description,
                "publisher": json.dumps(_match_to_payload(selected_publishers[0]), indent=2),
                "recommended_publishers": json.dumps(
                    [_match_to_payload(match) for match in recommended_publishers], indent=2
                ),
                "target_audience": json.dumps(_persona_payload(persona), indent=2),
                "advertiser_understanding": json.dumps(understanding, indent=2),
            },
        )
        draft = llm_client.generate_json(prompt, temperature=0.2)
        persona_drafts.append((persona, draft or _fallback_persona_draft(understanding, selected_publishers[0], persona)))

    return _normalize_campaign_draft(
        persona_drafts,
        recommended_publishers,
        selected_publishers[0],
        creative_personas,
    )


def rank_publishers(
    description: str, understanding: dict[str, Any], publishers: list[dict[str, Any]]
) -> list[Match]:
    semantic_scores = _llamaindex_scores(description, publishers, "publisher")
    matches = []
    for publisher in publishers:
        reasons: list[str] = []
        cautions: list[str] = []
        score = 0.0
        if understanding["confidence"] == "low":
            reach_score = math.log10(publisher["monthly_impressions"]) / 8
            aov_score = min(publisher["avg_order_value_usd"] / 120, 1)
            score = round((reach_score * 55) + (aov_score * 20), 2)
            reasons.append("Exploratory reach while the advertiser clarifies category and buyer.")
            cautions.append("Low-signal input; this should not launch without a clearer product description.")
            matches.append(Match(publisher, score, reasons, cautions))
            continue

        category_text = " ".join([publisher["category"], *publisher["subcategories"], publisher["notes"]]).lower()
        overlap = _overlap_score(description, category_text)
        score += 24 * overlap
        score += 22 * semantic_scores.get(publisher["id"], 0.0)

        category_hits = set(understanding["categories"]) & _publisher_category_aliases(publisher)
        if category_hits:
            primary_hit = understanding["categories"] and understanding["categories"][0] in category_hits
            score += 38 if primary_hit else 16
            reasons.append(f"Category match on {', '.join(sorted(category_hits))}.")

        subcategory_hits = _subcategory_hits(understanding["subcategories"], publisher["subcategories"])
        if subcategory_hits:
            score += 18
            reasons.append(f"Subcategory match on {', '.join(sorted(subcategory_hits))}.")

        if understanding["categories"] and not category_hits:
            score -= 12

        for signal in understanding["positioning"]:
            if signal in category_text or any(word in category_text for word in ATTRIBUTE_KEYWORDS.get(signal, [])):
                score += 6
                reasons.append(f"Publisher notes support {signal} positioning.")

        audience_reason, audience_bonus = _audience_fit(understanding, publisher)
        score += audience_bonus
        if audience_reason:
            reasons.append(audience_reason)

        if _is_b2b_mismatch(understanding, publisher):
            score -= 75
            cautions.append("Catalog is consumer-commerce oriented; B2B SaaS has weak publisher fit.")

        if not reasons:
            cautions.append("No strong category or audience overlap found.")

        matches.append(Match(publisher, round(max(score, 0.0), 2), _dedupe(reasons), cautions))

    matches.sort(key=lambda match: match.score, reverse=True)
    max_score = max((match.score for match in matches), default=1) or 1
    return [
        Match(match.item, round((match.score / max_score) * 100, 1), match.reasons, match.cautions)
        for match in matches
    ]


def rank_personas(description: str, understanding: dict[str, Any], personas: list[dict[str, Any]]) -> list[Match]:
    semantic_scores = _llamaindex_scores(description, personas, "persona")
    matches = []
    for persona in personas:
        persona_text = " ".join(
            [
                persona["name"],
                persona["description"],
                " ".join(persona["category_affinities"]),
                " ".join(persona["messaging_preferences"]),
            ]
        ).lower()
        score = 32 * _overlap_score(description, persona_text)
        score += 30 * semantic_scores.get(persona["id"], 0.0)
        reasons = []

        category_overlap = set(understanding["subcategories"] + understanding["categories"]) & set(
            persona["category_affinities"]
        )
        if category_overlap:
            score += 24
            reasons.append(f"Affinity overlap: {', '.join(sorted(category_overlap))}.")

        for signal in understanding["positioning"]:
            if signal in persona_text or any(word in persona_text for word in ATTRIBUTE_KEYWORDS.get(signal, [])):
                score += 7
                reasons.append(f"Messaging can lean into {signal}.")

        audience_reason, audience_bonus = _persona_audience_fit(understanding, persona)
        score += audience_bonus
        if audience_reason:
            reasons.append(audience_reason)

        if not reasons:
            reasons.append("Chosen as a secondary test audience based on broad shopping behavior.")

        matches.append(Match(persona, round(score, 2), _dedupe(reasons), []))

    matches.sort(key=lambda match: match.score, reverse=True)
    max_score = max((match.score for match in matches), default=1) or 1
    return [
        Match(match.item, round((match.score / max_score) * 100, 1), match.reasons, match.cautions)
        for match in matches
    ]


def _llamaindex_scores(query: str, items: list[dict[str, Any]], item_type: str) -> dict[str, float]:
    try:
        from llama_index.core.postprocessor import SimilarityPostprocessor
    except ImportError:
        return {}

    index = _llamaindex_index(items, item_type)
    nodes = index.as_retriever(similarity_top_k=min(8, len(items))).retrieve(query)
    filtered = SimilarityPostprocessor(similarity_cutoff=0.15).postprocess_nodes(nodes)
    scores = {node.node.metadata["id"]: float(node.score or 0) for node in filtered}
    return _normalize(scores)


def _llamaindex_index(items: list[dict[str, Any]], item_type: str) -> Any:
    global _LLAMAINDEX_EMBED_MODEL
    cache_key = item_type
    with _LLAMAINDEX_CACHE_LOCK:
        cached = _LLAMAINDEX_CACHE.get(cache_key)
        if cached is not None:
            return cached

        from llama_index.core import Document, Settings, VectorStoreIndex
        from llama_index.embeddings.huggingface import HuggingFaceEmbedding

        Settings.llm = None
        if _LLAMAINDEX_EMBED_MODEL is None:
            _LLAMAINDEX_EMBED_MODEL = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")
        Settings.embed_model = _LLAMAINDEX_EMBED_MODEL
        documents = [
            Document(text=_document_text(item, item_type), metadata={"id": item["id"]}) for item in items
        ]
        index = VectorStoreIndex.from_documents(documents)
        _LLAMAINDEX_CACHE[cache_key] = index
        return index


def _retrieval_engine_name() -> str:
    try:
        import llama_index  # noqa: F401
    except ImportError:
        return "deterministic-scoring"
    return "llamaindex"


def _llm_engine_name() -> str:
    return llm_client.engine_name()


def _needs_clarification(understanding: dict[str, Any]) -> bool:
    if understanding.get("confidence") == "low":
        return True
    if not _as_list(understanding.get("categories")):
        return True
    product = str(understanding.get("product") or "").strip().lower()
    return product in {"", "product", "unknown", "unclear", "not specified", "unspecified"}


def _vague_understanding(text: str) -> dict[str, Any]:
    return {
        "raw_query": text,
        "company_name": None,
        "product": "unclear",
        "primary_intent": "Query is too vague to choose a publisher or shopper persona.",
        "categories": [],
        "subcategories": [],
        "attributes": [],
        "audience": {
            "age_range": "",
            "gender_skew": "",
            "description": "",
            "price_sensitivity": "",
            "typical_aov_usd": None,
            "demographics": [],
            "interests": [],
            "purchase_motivations": [],
            "disinterested_in": [],
        },
        "positioning": [],
        "confidence": "low",
        "clarifying_questions": _default_clarifying_questions(),
    }


def _clarification_response(
    advertiser_description: str,
    understanding: dict[str, Any],
    publisher_matches: list[Match] | None = None,
) -> dict[str, Any]:
    publisher_matches = publisher_matches or []
    clarifying_questions = _as_list(understanding.get("clarifying_questions")) or _default_clarifying_questions()
    return {
        "advertiser_understanding": {
            **understanding,
            "confidence": "low",
            "clarifying_questions": clarifying_questions,
        },
        "recommended_publishers": [],
        "recommended_personas": [],
        "llm_selection": {
            "selected_publisher_id": None,
            "selected_persona_id": None,
            "publisher_reasoning": ["No publisher selected because the advertiser query is too vague."],
            "persona_reasoning": ["No persona selected because the target buyer is not defined clearly enough."],
            "click_hypothesis": "",
            "confidence": "low",
            "source": "needs_clarification",
        },
        "excluded_publishers": [_excluded_payload(match) for match in publisher_matches[:4]],
        "creative_variants": [],
        "psychological_blueprint": {
            "contextual_vibe": "No publisher context selected.",
            "friction_point": "The product, buyer, or category is not specific enough to build a campaign.",
            "angle": "Ask for the missing product and audience details before choosing media or writing ads.",
        },
        "campaign_config": {
            "launch_recommendation": "needs_clarification",
            "objective": "clarify advertiser intent",
            "flight": {"duration_days": 0, "pacing": "paused"},
            "budget": {
                "recommended_test_budget_usd": 0,
                "allocation": [],
                "daily_starting_budget_usd": 0,
                "allocation_strategy": "Do not allocate budget until the product and buyer are clear.",
            },
            "targeting": {
                "included_personas": [],
                "category_signals": _as_list(understanding.get("categories"))
                + _as_list(understanding.get("subcategories")),
                "positioning_signals": _as_list(understanding.get("positioning")),
                "geo": [],
                "exclusions": ["all paid placements until the query is clarified"],
            },
            "bid_strategy": {
                "type": None,
                "starting_cpm_range_usd": [0, 0],
                "optimization": "paused until launchable targeting exists",
                "explanation": "No bid should be set for a vague query.",
            },
            "measurement": {
                "primary_kpi": "brief completeness",
                "secondary_kpis": ["product category supplied", "target buyer supplied", "price point supplied"],
            },
            "targeting_rationale": (
                "The advertiser description is too vague to select a reliable publisher/persona pair. "
                "Ask clarifying questions before campaign generation."
            ),
            "psychological_blueprint": {
                "contextual_vibe": "No publisher context selected.",
                "friction_point": "The product, buyer, or category is not specific enough to build a campaign.",
                "angle": "Ask for the missing product and audience details before choosing media or writing ads.",
            },
            "target_publisher": None,
            "target_persona": None,
        },
        "debug": {
            "retrieval_engine": "not_run" if not publisher_matches else _retrieval_engine_name(),
            "llm_engine": _llm_engine_name(),
            "note": "Returned needs_clarification because the query did not contain enough launchable product/audience detail.",
        },
    }


def _default_clarifying_questions() -> list[str]:
    return [
        "What product or service are you advertising?",
        "Who is the target buyer or shopper persona?",
        "What price point, positioning, or key differentiator should the campaign use?",
    ]


def _llm_understand_advertiser(text: str) -> dict[str, Any] | None:
    prompt = render_prompt("advertiser_understanding", {"advertiser_description": text})
    payload = llm_client.generate_json(prompt)
    if not payload:
        return None

    categories = _as_list(payload.get("categories"))
    attributes = _as_list(payload.get("attributes") or payload.get("positioning"))
    audience = payload.get("audience") if isinstance(payload.get("audience"), dict) else {}
    confidence = str(payload.get("confidence") or "").lower()
    if confidence not in {"high", "medium", "low"}:
        confidence = "medium"
    product = payload.get("product")
    primary_intent = payload.get("primary_intent")
    if not isinstance(product, str) or not product.strip():
        raise RuntimeError("LLM advertiser understanding returned no product.")
    if not isinstance(primary_intent, str) or not primary_intent.strip():
        raise RuntimeError("LLM advertiser understanding returned no primary intent.")

    normalized_audience = {
        "age_range": str(audience.get("age_range") or ""),
        "gender_skew": str(audience.get("gender_skew") or ""),
        "description": str(audience.get("description") or ""),
        "price_sensitivity": str(audience.get("price_sensitivity") or ""),
        "typical_aov_usd": _number_or_none(audience.get("typical_aov_usd")),
        "disinterested_in": _as_list(audience.get("disinterested_in")),
        "demographics": _as_list(audience.get("demographics")),
        "interests": _as_list(audience.get("interests")),
        "purchase_motivations": _as_list(audience.get("purchase_motivations")),
    }

    return {
        "raw_query": text,
        "company_name": payload.get("company_name"),
        "product": product.strip(),
        "primary_intent": primary_intent.strip(),
        "categories": categories[:4],
        "subcategories": _as_list(payload.get("subcategories"))[:8],
        "attributes": attributes[:8],
        "audience": normalized_audience,
        "positioning": attributes[:8],
        "confidence": confidence,
        "clarifying_questions": _as_list(payload.get("clarifying_questions")),
    }


def _apply_llm_publisher_choice(candidates: list[Match], choice: dict[str, Any]) -> list[Match]:
    selected_id = choice.get("selected_publisher_id")
    selected = [match for match in candidates if match.item["id"] == selected_id]
    if not selected:
        raise RuntimeError("Selected publisher id is not present in the retrieved candidates.")
    return selected


def _guardrail_publisher_selection(
    selected_publisher_id: str, candidates: list[Match], choice: dict[str, Any]
) -> tuple[str, list[str]]:
    top_candidate = candidates[0]
    selected_candidate = next(match for match in candidates if match.item["id"] == selected_publisher_id)
    score_gap = top_candidate.score - selected_candidate.score
    if score_gap < 15:
        return selected_publisher_id, []

    reasoning_text = " ".join(_as_list(choice.get("publisher_reasoning"))).lower()
    top_name = top_candidate.item["name"].lower()
    has_top_disqualifier = top_name in reasoning_text and any(
        word in reasoning_text
        for word in [
            "disqual",
            "mismatch",
            "incompatible",
            "wrong",
            "too low",
            "too young",
            "too old",
            "low income",
            "watchout",
        ]
    )
    if has_top_disqualifier:
        return selected_publisher_id, []

    return top_candidate.item["id"], [
        (
            f"Retrieval guardrail kept {top_candidate.item['name']} because its score "
            f"({top_candidate.score}) was {score_gap:.1f} points above "
            f"{selected_candidate.item['name']} and the LLM did not cite a concrete "
            "catalog disqualifier for the top candidate."
        )
    ]


def _fallback_candidate_choice(
    publisher_candidates: list[Match], persona_candidates: list[Match], reason: str
) -> dict[str, Any]:
    publisher = publisher_candidates[0]
    persona = persona_candidates[0]
    return {
        "selected_publisher_id": publisher.item["id"],
        "selected_persona_id": persona.item["id"],
        "publisher_reasoning": [
            f"{reason} Used top retrieval match: {publisher.item['name']} ({publisher.score})."
        ],
        "persona_reasoning": [
            f"{reason} Used top persona match: {persona.item['name']} ({persona.score})."
        ],
        "click_hypothesis": (
            f"{persona.item['name']} is the strongest retrieved audience for "
            f"{publisher.item['name']} based on catalog fit."
        ),
        "confidence": "low",
        "source": f"{llm_client.engine_name()}+retrieval-fallback",
    }


def _resolve_candidate_id(value: Any, candidates: list[Match]) -> str:
    candidate_ids = {match.item["id"] for match in candidates}
    text = str(value or "").strip()
    if text in candidate_ids:
        return text

    normalized_text = _normalize_name(text)
    for match in candidates:
        if normalized_text == _normalize_name(match.item["name"]):
            return match.item["id"]
    return text


def _normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _apply_llm_persona_choice(candidates: list[Match], choice: dict[str, Any]) -> list[Match]:
    selected_id = choice.get("selected_persona_id")
    selected = [match for match in candidates if match.item["id"] == selected_id]
    if not selected:
        raise RuntimeError("Selected persona id is not present in the retrieved candidates.")
    return selected


def _normalize_campaign_draft(
    persona_drafts: list[tuple[Match, dict[str, Any]]],
    recommended_publishers: list[Match],
    primary_publisher: Match,
    creative_personas: list[Match],
) -> dict[str, Any]:
    draft = persona_drafts[0][1] if persona_drafts else {}
    configuration = draft.get("campaign_configuration") or draft.get("campaign_config") or {}
    if not isinstance(configuration, dict):
        raise RuntimeError("LLM campaign generation returned an invalid campaign configuration.")
    blueprint = draft.get("psychological_blueprint")
    if not isinstance(blueprint, dict):
        raise RuntimeError(
            "LLM campaign generation returned an invalid psychological blueprint "
            f"(type={type(blueprint).__name__}, keys={list(draft.keys())})."
        )

    config = _campaign_config(recommended_publishers, creative_personas, primary_publisher)
    objective = configuration.get("objective")
    if objective:
        config["objective"] = str(objective)
    targeting_rationale = configuration.get("targeting_rationale")
    if targeting_rationale:
        config["targeting_rationale"] = str(targeting_rationale)
    daily_budget = _number_or_none(configuration.get("daily_starting_budget_usd"))
    if daily_budget:
        config["budget"]["daily_starting_budget_usd"] = int(daily_budget)
    budget_allocation = configuration.get("budget_allocation")
    if budget_allocation:
        config["budget"]["allocation_strategy"] = str(budget_allocation)
    config["bid_strategy"]["explanation"] = str(
        configuration.get("suggested_bid_strategy")
        or configuration.get("bid_strategy_explanation")
        or ""
    )
    bid_type = str(configuration.get("bid_type") or "").lower()
    if bid_type in {"cpc", "cpm"}:
        config["bid_strategy"]["type"] = bid_type
    bid_range = configuration.get("bid_range_usd") or configuration.get("suggested_bid_range_usd")
    if isinstance(bid_range, list) and len(bid_range) >= 2:
        range_key = "starting_cpc_range_usd" if config["bid_strategy"].get("type") == "cpc" else "starting_cpm_range_usd"
        config["bid_strategy"][range_key] = [
            float(_number_or_none(bid_range[0]) or 0),
            float(_number_or_none(bid_range[1]) or 0),
        ]
    target_cpa = _number_or_none(configuration.get("target_cpa_guardrail_usd") or configuration.get("target_cpa_guardrail"))
    if target_cpa:
        config["bid_strategy"]["target_cpa_guardrail_usd"] = float(target_cpa)
    financial_reasoning = configuration.get("financial_reasoning")
    if financial_reasoning:
        config["bid_strategy"]["financial_reasoning"] = str(financial_reasoning)
    config["psychological_blueprint"] = blueprint
    config["target_publisher"] = primary_publisher.item["name"]
    if creative_personas:
        config["target_persona"] = creative_personas[0].item["name"]
        config["target_personas"] = [
            {"id": match.item["id"], "name": match.item["name"], "score": match.score}
            for match in creative_personas[:2]
        ]

    creative_variants = _normalize_creative_variants(persona_drafts)
    return {
        "campaign_config": config,
        "psychological_blueprint": blueprint,
        "creative_variants": creative_variants,
    }


def _normalize_creative_variants(persona_drafts: list[tuple[Match, dict[str, Any]]]) -> list[dict[str, Any]]:
    normalized = []
    for index, (persona_match, draft) in enumerate(persona_drafts[:2], start=1):
        persona = persona_match.item
        variant = draft.get("creative_variant")
        if variant is None:
            variants = draft.get("creative_variants")
            if isinstance(variants, list) and variants:
                variant = variants[0]
        if not isinstance(variant, dict):
            continue
        normalized.append(
            {
                "persona_id": str(variant.get("persona_id") or persona["id"]),
                "persona_name": str(variant.get("persona_name") or persona["name"]),
                "persona_fit_score": persona_match.score,
                "variant_type": str(variant.get("variant_type") or f"{persona['name']} angle"),
                "persona_reasoning": _as_list(
                    variant.get("persona_reasoning")
                    or f"{persona['name']} is a plausible test audience because {persona['description']}"
                ),
                "headline": str(variant.get("headline") or "A Better Fit"),
                "body": str(variant.get("body_copy") or variant.get("body") or ""),
                "cta": str(variant.get("cta") or "Learn More"),
                "why_this_works": str(variant.get("why_this_works") or ""),
            }
        )
    if not normalized:
        raise RuntimeError("LLM campaign generation returned invalid creative variants.")
    return normalized


def _fallback_persona_draft(
    understanding: dict[str, Any], publisher: Match, persona: Match
) -> dict[str, Any]:
    persona_item = persona.item
    product = str(understanding.get("product") or "this product")
    positioning = _as_list(understanding.get("positioning"))
    primary_signal = positioning[0] if positioning else "relevant"
    return {
        "campaign_configuration": {
            "objective": "Conversion",
            "targeting_rationale": (
                f"{publisher.item['name']} is the primary placement and {persona_item['name']} "
                f"matches the {primary_signal} buying angle."
            ),
            "suggested_bid_strategy": "Start with CPM testing, then optimize toward qualified click and add-to-cart behavior.",
            "bid_type": "cpm",
            "bid_range_usd": [10, 22],
            "daily_starting_budget_usd": 250,
            "budget_allocation": "Allocate more budget to the highest-fit publisher and reserve the rest for test-and-learn coverage.",
            "target_cpa_guardrail_usd": max(20, round(float(persona_item.get("typical_aov_usd") or 75) * 0.35, 2)),
            "financial_reasoning": "Use persona AOV as a guardrail while the prototype learns which publisher converts efficiently.",
        },
        "psychological_blueprint": {
            "contextual_vibe": f"Shopping in a {publisher.item['category']} context.",
            "friction_point": persona_item["description"],
            "angle": f"Connect {product} to {persona_item['name']}'s stated motivations.",
        },
        "creative_variant": {
            "persona_id": persona_item["id"],
            "persona_name": persona_item["name"],
            "variant_type": f"{persona_item['name']} angle",
            "persona_reasoning": f"{persona_item['name']} is plausible because their preferences overlap with the advertiser positioning.",
            "headline": product[:48] or "A Better Fit",
            "body_copy": f"Built for shoppers who care about {primary_signal}. See why {product} fits your routine.",
            "cta": "Learn More",
            "why_this_works": f"This speaks to {persona_item['name']}'s motivation without inventing unsupported claims.",
        },
    }


def _select_creative_personas(selected_persona_id: str, persona_candidates: list[Match], limit: int) -> list[Match]:
    selected: list[Match] = []
    for match in persona_candidates:
        if match.item["id"] == selected_persona_id:
            selected.append(match)
            break
    for match in persona_candidates:
        if match.item["id"] != selected_persona_id:
            selected.append(match)
        if len(selected) >= limit:
            break
    return selected


def _select_publishers(
    understanding: dict[str, Any], publisher_matches: list[Match], top_publishers: int
) -> list[Match]:
    if "b2b" in understanding["categories"]:
        return [match for match in publisher_matches if match.score >= 35][:top_publishers]
    if understanding["confidence"] == "low":
        return _diverse_exploratory_publishers(publisher_matches, top_publishers)
    return [match for match in publisher_matches if match.score > 20][:top_publishers]


def _diverse_exploratory_publishers(matches: list[Match], limit: int) -> list[Match]:
    selected: list[Match] = []
    seen_categories = set()
    for match in matches:
        category = match.item["category"]
        if category not in seen_categories:
            selected.append(match)
            seen_categories.add(category)
        if len(selected) == limit:
            return selected
    return selected


def _document_text(item: dict[str, Any], item_type: str) -> str:
    if item_type == "publisher":
        audience = item["audience"]
        return " ".join(
            [
                item["name"],
                item["category"],
                " ".join(item["subcategories"]),
                audience["age_skew"],
                audience["income_tier"],
                " ".join(audience["top_geos"]),
                item["notes"],
            ]
        )
    return " ".join(
        [
            item["name"],
            item["description"],
            " ".join(item["category_affinities"]),
            " ".join(item["messaging_preferences"]),
            " ".join(item["disinterested_in"]),
        ]
    )


def _load_json(filename: str) -> list[dict[str, Any]]:
    with (DATA_DIR / filename).open() as file:
        return json.load(file)


def _tokenize(text: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", text.lower()) if token not in STOPWORDS]


def _normalize(scores: dict[str, float]) -> dict[str, float]:
    max_score = max(scores.values(), default=0)
    if not max_score:
        return scores
    return {key: value / max_score for key, value in scores.items()}


def _overlap_score(query: str, document: str) -> float:
    query_terms = set(_tokenize(query))
    doc_terms = set(_tokenize(document))
    if not query_terms:
        return 0.0
    return len(query_terms & doc_terms) / len(query_terms)


def _publisher_category_aliases(publisher: dict[str, Any]) -> set[str]:
    aliases = {publisher["category"], *publisher["subcategories"]}
    if publisher["category"] in {"wellness_dtc", "wellness_services"}:
        aliases.add("wellness")
    if publisher["category"] == "pet":
        aliases.add("pet")
    if publisher["category"] == "beverages":
        aliases.add("wellness")
    return aliases


def _subcategory_hits(query_subcategories: list[str], publisher_subcategories: list[str]) -> set[str]:
    aliases = set(publisher_subcategories)
    if "sustainable" in aliases:
        aliases.add("sustainable_apparel")
    if "subscription" in aliases:
        aliases.add("subscription_services")
    if "functional_beverages" in aliases:
        aliases.add("wellness")
    return set(query_subcategories) & aliases


def _audience_fit(understanding: dict[str, Any], publisher: dict[str, Any]) -> tuple[str | None, float]:
    audience = publisher["audience"]
    target_audience = understanding.get("audience", {})
    reasons = []
    bonus = 0.0
    if "premium" in understanding["positioning"] and audience["income_tier"] in {"high", "mid-high"}:
        reasons.append(f"{audience['income_tier']} income audience can support premium pricing.")
        bonus += 8
    if "women" in understanding["positioning"] and audience["gender_split"]["female"] >= 0.7:
        reasons.append("Female-skewed audience matches the buyer description.")
        bonus += 7
    if str(target_audience.get("gender_skew", "")).lower().startswith("female") and audience["gender_split"]["female"] >= 0.7:
        reasons.append("Publisher gender skew aligns with the extracted target audience.")
        bonus += 7
    target_aov = _number_or_none(target_audience.get("typical_aov_usd"))
    if target_aov and abs(target_aov - publisher["avg_order_value_usd"]) <= 45:
        reasons.append("Publisher AOV is close to the target shopper's expected order value.")
        bonus += 6
    if "convenience" in understanding["positioning"] and publisher["category"] in {"instant_delivery", "meal_kits"}:
        reasons.append("Convenience-oriented placement matches the value proposition.")
        bonus += 8
    return (" ".join(reasons) if reasons else None, bonus)


def _is_b2b_mismatch(understanding: dict[str, Any], publisher: dict[str, Any]) -> bool:
    return "b2b" in understanding["categories"] and publisher["category"] not in {"wellness_services"}


def _persona_audience_fit(understanding: dict[str, Any], persona: dict[str, Any]) -> tuple[str | None, float]:
    audience = understanding.get("audience", {})
    reasons = []
    bonus = 0.0
    extracted_gender = str(audience.get("gender_skew") or "").lower()
    if extracted_gender and extracted_gender in persona["gender_skew"].lower():
        reasons.append("Extracted gender skew aligns with this shopper persona.")
        bonus += 7
    extracted_price = str(audience.get("price_sensitivity") or "").lower()
    if extracted_price and extracted_price in persona["price_sensitivity"].lower():
        reasons.append("Price sensitivity matches the expected buyer.")
        bonus += 6
    target_aov = _number_or_none(audience.get("typical_aov_usd"))
    if target_aov and abs(target_aov - persona["typical_aov_usd"]) <= 45:
        reasons.append("Typical AOV is close to this persona's purchase behavior.")
        bonus += 5
    disinterested = set(_as_list(audience.get("disinterested_in")))
    if disinterested & set(persona["disinterested_in"]):
        reasons.append("Known disinterests overlap, which helps avoid weak creative angles.")
        bonus += 3
    return (" ".join(reasons) if reasons else None, bonus)


def _match_to_payload(match: Match, choice: dict[str, Any] | None = None) -> dict[str, Any]:
    publisher = match.item
    choice = choice or {}
    return {
        **publisher,
        "score": match.score,
        "selected": choice.get("selected_publisher_id") == publisher["id"],
        "reasoning": match.reasons,
        "watchouts": match.cautions,
    }


def _persona_payload(match: Match, choice: dict[str, Any] | None = None) -> dict[str, Any]:
    persona = match.item
    choice = choice or {}
    return {
        **persona,
        "score": match.score,
        "selected": choice.get("selected_persona_id") == persona["id"],
        "reasoning": match.reasons,
    }


def _excluded_payload(match: Match) -> dict[str, Any]:
    return {
        "id": match.item["id"],
        "name": match.item["name"],
        "score": match.score,
        "why_excluded": match.cautions[:1] or ["Lower relative fit than selected publishers."],
    }


def _campaign_config(
    publishers: list[Match], personas: list[Match], primary_publisher: Match | None = None
) -> dict[str, Any]:
    total_weight = sum(match.score for match in publishers) or 1
    primary_id = primary_publisher.item["id"] if primary_publisher else publishers[0].item["id"]
    allocations = [
        {
            "publisher_id": match.item["id"],
            "publisher_name": match.item["name"],
            "budget_pct": round((match.score / total_weight) * 100, 1),
            "role": "primary scale" if match.item["id"] == primary_id else "test and learn",
        }
        for index, match in enumerate(publishers)
    ]
    return {
        "launch_recommendation": "draft_ready_for_review",
        "objective": "qualified traffic and first-purchase testing",
        "flight": {"duration_days": 30, "pacing": "even daily pacing"},
        "budget": {
            "recommended_test_budget_usd": 10000,
            "allocation": allocations,
        },
        "targeting": {
            "included_personas": [
                {"id": match.item["id"], "name": match.item["name"], "score": match.score}
                for match in personas[:4]
            ],
            "category_signals": [],
            "positioning_signals": [],
            "geo": _geo_from_publishers(publishers),
            "exclusions": ["publishers with no category or audience rationale"],
        },
        "bid_strategy": {
            "type": "cpm",
            "starting_cpm_range_usd": [0, 0],
            "optimization": "increase bids on publishers/personas with creative CTR and post-click engagement above median",
        },
        "measurement": {
            "primary_kpi": "add-to-cart or qualified site visit",
            "secondary_kpis": ["publisher CTR", "creative CTR", "persona-level conversion proxy"],
        },
    }


def _geo_from_publishers(publishers: list[Match]) -> list[str]:
    geos: list[str] = []
    for match in publishers:
        geos.extend(match.item["audience"]["top_geos"])
    return sorted(set(geos), key=geos.index)


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        if not value.strip():
            return []
        return [part.strip() for part in re.split(r"[,;\n]", value) if part.strip()]
    return [str(value).strip()]


def _number_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"\d+(?:\.\d+)?", str(value).replace(",", ""))
    return float(match.group(0)) if match else None
