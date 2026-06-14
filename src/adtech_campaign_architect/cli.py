from __future__ import annotations

import argparse
import json

from .planner import build_campaign


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a draft ad campaign from an advertiser description.")
    parser.add_argument("description", help="Advertiser/product description")
    parser.add_argument("--top-publishers", type=int, default=4)
    args = parser.parse_args()

    campaign = build_campaign(args.description, top_publishers=args.top_publishers)
    print(json.dumps(campaign, indent=2))


if __name__ == "__main__":
    main()
