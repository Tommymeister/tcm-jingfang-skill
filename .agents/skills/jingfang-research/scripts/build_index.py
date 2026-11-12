import json
from retrieval import build

if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
