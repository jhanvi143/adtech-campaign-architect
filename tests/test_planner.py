from pathlib import Path
import unittest
from unittest.mock import patch

from adtech_campaign_architect import build_campaign


ROOT = Path(__file__).resolve().parents[1]


ACTIVEWEAR_UNDERSTANDING = {
    "raw_query": "A sustainable activewear brand for women. Made from recycled ocean plastic.",
    "company_name": None,
    "product": "sustainable activewear",
    "primary_intent": "Find apparel publishers and sustainability-minded shoppers.",
    "categories": ["apparel"],
    "subcategories": ["activewear", "sustainable_apparel"],
    "attributes": ["sustainability", "women"],
    "positioning": ["sustainability", "women"],
    "audience": {
        "age_range": "25-45",
        "gender_skew": "female",
        "description": "Women who buy sustainable activewear.",
        "price_sensitivity": "medium",
        "typical_aov_usd": 92,
        "demographics": [],
        "interests": [],
        "purchase_motivations": [],
        "disinterested_in": [],
    },
    "confidence": "high",
    "clarifying_questions": [],
}


def campaign_draft(persona_id: str, persona_name: str) -> dict:
    return {
        "campaign_configuration": {
            "objective": "Conversion",
            "targeting_rationale": f"{persona_name} is a strong audience for sustainable activewear.",
            "suggested_bid_strategy": "Start with CPM, then optimize toward qualified clicks.",
            "bid_type": "cpm",
            "bid_range_usd": [12, 24],
            "daily_starting_budget_usd": 300,
            "budget_allocation": "Weight spend toward the highest-fit ranked publisher.",
            "target_cpa_guardrail_usd": 32,
            "financial_reasoning": "AOV can support a measured CPM test.",
        },
        "psychological_blueprint": {
            "contextual_vibe": "Browsing activewear.",
            "friction_point": "Skepticism about sustainability claims.",
            "angle": "Specific materials and transparent proof.",
        },
        "creative_variant": {
            "persona_id": persona_id,
            "persona_name": persona_name,
            "variant_type": f"{persona_name} angle",
            "persona_reasoning": f"{persona_name} has a plausible reason to care about this product.",
            "headline": "Move With Proof",
            "body_copy": "Activewear made for buyers who check the details before they buy.",
            "cta": "See the Fabric",
            "why_this_works": "It matches the persona's motivation without adding unsupported claims.",
        },
    }


class PlannerContractTest(unittest.TestCase):
    def test_prompts_are_in_required_top_level_directory(self):
        prompts_dir = ROOT / "prompts"

        self.assertTrue(prompts_dir.is_dir())
        self.assertTrue((prompts_dir / "__init__.py").is_file())
        self.assertTrue((prompts_dir / "templates.py").is_file())

    def test_two_persona_creative_calls_and_ranked_publisher_allocation(self):
        llm_outputs = [
            {
                "selected_publisher_id": "pub_002",
                "selected_persona_id": "persona_006",
                "publisher_reasoning": ["Movewell directly matches activewear."],
                "persona_reasoning": ["The Sustainability Buyer matches the product promise."],
                "click_hypothesis": "Sustainability buyers will click when proof is visible in context.",
                "confidence": "high",
            },
            campaign_draft("persona_006", "The Sustainability Buyer"),
            campaign_draft("persona_009", "The Fitness Enthusiast"),
        ]

        with patch("adtech_campaign_architect.planner.understand_advertiser", return_value=ACTIVEWEAR_UNDERSTANDING), patch(
            "adtech_campaign_architect.planner._llamaindex_scores", return_value={}
        ), patch("adtech_campaign_architect.llm_client.generate_json", side_effect=llm_outputs) as generate_json:
            campaign = build_campaign(
                "A sustainable activewear brand for women. Made from recycled ocean plastic."
            )

        creative_persona_ids = {variant["persona_id"] for variant in campaign["creative_variants"]}
        recommended_publisher_ids = {publisher["id"] for publisher in campaign["recommended_publishers"]}
        allocated_publisher_ids = {
            allocation["publisher_id"] for allocation in campaign["campaign_config"]["budget"]["allocation"]
        }
        allocation_total = sum(
            allocation["budget_pct"] for allocation in campaign["campaign_config"]["budget"]["allocation"]
        )

        self.assertEqual(generate_json.call_count, 3)
        self.assertEqual(creative_persona_ids, {"persona_006", "persona_009"})
        self.assertEqual(recommended_publisher_ids, allocated_publisher_ids)
        self.assertAlmostEqual(allocation_total, 100.0, delta=0.2)
        self.assertEqual(campaign["campaign_config"]["target_personas"][0]["id"], "persona_006")


if __name__ == "__main__":
    unittest.main()
