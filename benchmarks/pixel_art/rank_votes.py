"""Aggregate exported human judgments by case and method pair, without a composite score."""
import argparse
from collections import defaultdict
import json
from pathlib import Path


def aggregate(paths):
    reviews = {}
    for path in paths:
        document = json.loads(path.read_text(encoding="utf-8"))
        if document.get("track") != "human_conversion_pairwise":
            raise ValueError(f"Not a human pairwise vote file: {path}")
        reviewer = document.get("reviewer") or str(path.resolve())
        for vote in document["votes"]:
            pair = tuple(sorted((vote["left"], vote["right"])))
            if vote["choice"] not in ("left", "right", "tie", "skip"):
                raise ValueError("Unknown vote choice")
            reviews[reviewer, vote["case"], pair] = vote
    counts = defaultdict(lambda: {"a_wins": 0, "b_wins": 0, "ties": 0, "skips": 0})
    for (_, case, pair), vote in reviews.items():
        choice = vote["choice"]
        category = ("ties" if choice == "tie" else "skips" if choice == "skip" else
                    "a_wins" if vote[choice] == pair[0] else "b_wins")
        counts[case, pair][category] += 1
    return [{"case": case, "a": pair[0], "b": pair[1], **result}
            for (case, pair), result in sorted(counts.items())]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("votes", type=Path, nargs="+")
    args = parser.parse_args()
    print(json.dumps({"track": "human_conversion_pairwise", "results": aggregate(args.votes)}, indent=2))
