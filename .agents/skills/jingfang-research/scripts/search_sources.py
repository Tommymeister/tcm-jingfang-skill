import argparse
import json
from retrieval import search, get_evidence

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="检索隔离的本地经方证据，不生成处方")
    p.add_argument("query", nargs="?", default="")
    p.add_argument("--perspective", choices=["classics", "nihaixia", "like"], default="classics")
    p.add_argument("--evidence")
    p.add_argument("--limit", type=int, default=4)
    args = p.parse_args()
    result = get_evidence(args.evidence) if args.evidence else search(args.query, args.perspective, max(1,min(args.limit,20)))
    print(json.dumps(result, ensure_ascii=False, indent=2))
