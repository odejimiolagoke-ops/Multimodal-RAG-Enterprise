"""Run LangSmith evaluation for the knowledge-base RAG pipeline."""

import argparse

from monitoring import evaluate_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, help="LangSmith dataset name or ID")
    parser.add_argument("--max-concurrency", type=int, default=2)
    args = parser.parse_args()
    results = evaluate_dataset(args.dataset, max_concurrency=args.max_concurrency)
    print(f"LangSmith evaluation started: {results}")


if __name__ == "__main__":
    main()
