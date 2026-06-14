"""Prompt templates used by the local campaign-planning LLM pipeline."""

ADVERTISER_UNDERSTANDING_PROMPT = """
You are the query-understanding and input de-noising layer for an advanced ad-tech campaign planner.

An advertiser will give you a free-text description of what they sell. The description may be vague,
messy, short, or low-signal. Decode the underlying product, positioning, buyer, and economics so the
retrieval layer can find the right publisher placement and shopper persona.

Ad-tech definitions you must respect:
- Advertiser: the business paying to promote a product or service.
- Publisher: the platform/environment where the ad can appear.
- Shopper persona: the audience segment likely to see and respond to the ad.
- Targeting: the explicit rules connecting advertiser intent to publisher context and persona psychology.
- AOV: expected order value; use it to infer whether premium, value, or impulse economics make sense.

Extract metadata needed to:
1. Retrieve the right publisher/platform.
2. Retrieve the right shopper persona.
3. Structure later budget, bid, and CPA reasoning.
4. Ask clarifying questions when the brief is too vague to launch safely.

Return ONLY valid JSON with this shape:

{
  "company_name": "explicit company or brand name, otherwise null",
  "product": "plain-English product or service being advertised",
  "primary_intent": "one sentence describing what the campaign should find",
  "categories": ["broad categories such as pet, apparel, wellness, beauty, home, groceries, beverages, meal_kits, instant_delivery, b2b"],
  "subcategories": ["specific product or audience terms such as pet_food, pet_health, activewear, sustainable_apparel, supplements, functional_beverages"],
  "attributes": ["premium, subscription, sustainability, science, convenience, gifting, value, women, family, performance, etc."],
  "audience": {
    "age_range": "best inferred buyer age range, or empty string",
    "gender_skew": "female, male, balanced, female-leaning, male-leaning, or empty string",
    "description": "short description of the target consumer",
    "price_sensitivity": "low, low-medium, medium, medium-high, high, or empty string",
    "typical_aov_usd": 0,
    "demographics": ["demographic clues"],
    "interests": ["shopping or lifestyle interests"],
    "purchase_motivations": ["why this buyer would care"],
    "disinterested_in": ["things this buyer likely ignores or dislikes"]
  },
  "confidence": "high | medium | low",
  "clarifying_questions": ["only include questions when category, product, audience, or price point is missing"]
}

Rules:
- Infer only what is reasonably supported by the text.
- Use concise taxonomy terms that can match a publisher/persona catalog.
- Translate messy wording into plain product positioning without inventing unsupported claims.
- Capture price posture and likely AOV when the advertiser implies premium, value, subscription, impulse, or high-consideration buying.
- Prefer buyer psychology and shopping intent over generic demographics.
- If the advertiser is vague, set confidence to "low" and ask direct clarifying questions.
- If the product is B2B or off-catalog, say so in "categories" and ask for the right publisher supply.
- Do not overstate medical, health, sustainability, or performance claims.
- Do not include markdown fences in the answer.

Advertiser description:
{{ advertiser_description }}
""".strip()


CANDIDATE_SELECTION_PROMPT = """
Choose one publisher id and one shopper persona id from the candidates.

Return ONLY a valid JSON object. Do not include markdown, prose, XML, or step-by-step reasoning.
The selected ids MUST be copied exactly from the candidate ids below.

Required JSON shape:

{
  "selected_publisher_id": "copy the exact id value from one publisher candidate, e.g. pub_004",
  "selected_persona_id": "copy the exact id value from one persona candidate, e.g. persona_005",
  "publisher_reasoning": ["short specific reason"],
  "persona_reasoning": ["short specific reason"],
  "click_hypothesis": "one sentence explaining why this persona would click on this publisher",
  "confidence": "high | medium | low"
}

Decision rules:
- Return ids, never names. Do not put publisher names such as "Marlowe & Co." in selected_publisher_id.
- Return ids, never names. Do not put persona names such as "The Gifter" in selected_persona_id.
- Treat the candidate "score" as the retrieval layer's confidence. The highest-score publisher is the default winner.
- Only override the highest-score publisher if the lower-score publisher has a concrete, catalog-grounded advantage AND the top publisher has a concrete disqualifier.
- A concrete disqualifier must cite fields from the candidate JSON, such as incompatible category, incompatible subcategories, clearly wrong audience age/income/price posture, or explicit watchouts.
- Broad adjacency is not enough to override. For example, do not choose an activewear publisher over a luxury/classic apparel publisher for premium handcrafted leather handbags.
- Prefer direct category/subcategory overlap over broad adjacency.
- Check publisher AOV and persona typical AOV against the product price posture.
- For premium, luxury, handcrafted, heritage, high-price, slow-fulfillment, or high-consideration products, favor publishers with high-income audiences, older/affluent audience notes, quality messaging, classic/premium context, and higher AOV over younger activewear or mass transactional contexts.
- Prefer the persona whose messaging preferences match the product attributes.
- If all choices are weak, still choose from the candidates and set confidence to "low".

Advertiser understanding:
{{ advertiser_understanding }}

Publisher candidates:
{{ publisher_candidates }}

Persona candidates:
{{ persona_candidates }}
""".strip()


CAMPAIGN_GENERATION_PROMPT = """
Create a launch-ready ad creative for exactly one shopper persona, plus campaign architecture context.

Return ONLY one valid JSON object. Do not include markdown, prose, XML, or step-by-step reasoning.
Use exactly these top-level keys: campaign_configuration, psychological_blueprint, creative_variant.
Do not rename, omit, nest, stringify, or wrap any of these top-level keys.

Context:
- Product: {{ product }}
- Primary publisher: {{ publisher }}
- Ranked recommended publishers: {{ recommended_publishers }}
- Shopper persona for this creative: {{ target_audience }}
- Advertiser metadata: {{ advertiser_understanding }}

Required JSON shape:

{
  "campaign_configuration": {
    "objective": "Conversion",
    "targeting_rationale": "why this product fits the primary publisher, ranked publishers, and persona",
    "suggested_bid_strategy": "CPC or CPM strategy with short AOV-based reasoning",
    "bid_type": "cpc or cpm",
    "bid_range_usd": [1, 3],
    "daily_starting_budget_usd": 250,
    "budget_allocation": "short daily budget strategy across the ranked recommended publishers",
    "target_cpa_guardrail_usd": 25,
    "financial_reasoning": "short explanation of AOV, bid, and CPA logic"
  },
  "psychological_blueprint": {
    "contextual_vibe": "what the shopper is doing on this publisher",
    "friction_point": "specific shopper pain, desire, or doubt",
    "angle": "conversion angle that resolves the friction point"
  },
  "creative_variant": {
    "persona_id": "copy the exact id from the shopper persona",
    "persona_name": "copy the shopper persona name",
    "variant_type": "persona-specific angle label",
    "persona_reasoning": "one sentence explaining why this persona is plausible for the advertiser",
    "headline": "under 50 characters",
    "body_copy": "1-3 sentences",
    "cta": "low-friction action text",
    "why_this_works": "one sentence psychological trigger"
  }
}

Schema contract:
- campaign_configuration MUST be a JSON object, not a string or array.
- psychological_blueprint MUST be a JSON object with exactly these string keys: contextual_vibe, friction_point, angle.
- creative_variant MUST be a JSON object, not an array.
- creative_variant.persona_id MUST match the provided shopper persona id.
- creative_variant.persona_name MUST match the provided shopper persona name.
- Do not use alternate keys such as "psychology", "blueprint", "The Psychological Blueprint", "campaign_config", "ads", or "variants".
- Every string value must be concrete and filled in. Do not use placeholders.
- Every why_this_works value must be a non-empty sentence.
- If a value is uncertain, still return the required key with the best concise inferred value.

Strict rules:
- Headlines must be under 50 characters.
- Keep body_copy to 1-2 short sentences.
- Do not invent discounts, medical claims, or sustainability claims beyond context.
- Never mention coupons, promo codes, percent-off offers, dollar-off offers, sale pricing, or free shipping unless that exact offer appears in the provided context.
- Use value framing, risk reduction, replenishment logic, or AOV fit instead of fabricated discounts.
- Avoid empty buzzwords like "revolutionary" or "game-changing".
""".strip()


PUBLISHER_RANKING_PROMPT = """
This prompt documents the ranking reasoning contract used after retrieval.

Given extracted advertiser intent and a candidate publisher, explain whether this publisher should be recommended.

Consider:
- Category and subcategory overlap
- Audience age, income, gender skew, and geography
- Publisher qualitative notes
- Target shopper price sensitivity and typical AOV
- Whether the advertiser's price point and positioning match the publisher audience
- Whether the publisher context is premium, transactional, educational, replenishment-driven, or impulse-friendly
- Whether CPC, CPM, and target CPA economics look plausible against publisher AOV
- Why apparently adjacent publishers should still be excluded

Return:
- "fit_score": 0-100
- "reasons": visible user-facing reasoning
- "watchouts": mismatch or launch risks
""".strip()


PROMPTS = {
    "advertiser_understanding": ADVERTISER_UNDERSTANDING_PROMPT,
    "candidate_selection": CANDIDATE_SELECTION_PROMPT,
    "campaign_generation": CAMPAIGN_GENERATION_PROMPT,
    "publisher_ranking": PUBLISHER_RANKING_PROMPT,
}
