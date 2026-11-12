"""Local evidence index and Chinese literal retrieval; no network or LLM calls."""
import hashlib
import json
import re
import sqlite3
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data/indexes/evidence.sqlite3"
TRANSLATE = str.maketrans("湯陽陰風證傷熱廈醫經脈虛實黃惡汗", "汤阳阴风证伤热厦医经脉虚实黄恶汗")
TERMS = ("当归四逆汤", "通脉四逆汤", "桂枝汤", "麻黄汤", "四逆汤", "真寒假热", "真热假寒", "太阳中风", "太阳伤寒", "六经辨证", "少阴病", "附子", "乌头", "金匮要略")
COMPOUNDS = {"四逆汤": ("当归四逆汤", "通脉四逆汤", "茯苓四逆汤", "桔甘四逆汤"),
             "桂枝汤": ("柴胡桂枝汤", "黄芪桂枝汤"), "麻黄汤": ("射干麻黄汤", "厚朴麻黄汤")}


def normalize(text):
    return text.translate(TRANSLATE).replace("太陽", "太阳")


def connect(db=DB):
    if not Path(db).exists():
        raise FileNotFoundError("索引不存在，请运行 python3 scripts/build_index.py")
    c = sqlite3.connect(Path(db).resolve().as_uri()+"?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA trusted_schema=OFF")
    return c


def build(db=DB, root=ROOT):
    db = Path(db)
    db.parent.mkdir(parents=True, exist_ok=True)
    records, seen = [], set()
    for p in sorted((Path(root)/"modules").glob("*/evidence.jsonl")):
        for line in p.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r["perspective"] not in ("classics", "nihaixia", "like"):
                raise ValueError("未知的资料视角")
            if not r.get("rights_basis"):
                raise ValueError("需要 rights_basis 记录使用权依据；该声明不代表已独立核验授权")
            if r.get("record_kind") == "demo" and r["verification_status"] != "D":
                raise ValueError("演示数据必须标记 D")
            if r["source_id"] in seen:
                raise ValueError("重复证据编号: "+r["source_id"])
            seen.add(r["source_id"])
            if r["verification_status"] not in "ABCD" or len(r["verification_status"]) != 1:
                raise ValueError("无效的来源状态")
            if r["verification_status"] == "A" and not r.get("verification_log"):
                raise ValueError("A 类需要原件核验记录")
            excerpt = r["original_excerpt"]
            if hashlib.sha256(excerpt.encode()).hexdigest() != r["original_excerpt_sha256"]:
                raise ValueError("短引文哈希不匹配: "+r["source_id"])
            if Path(r["local_source_path"]).is_absolute():
                raise ValueError("来源必须使用包内相对路径")
            local = (Path(root)/r["local_source_path"]).resolve()
            if not local.is_relative_to(Path(root).resolve()) or not local.is_file():
                raise ValueError("来源路径不存在或越界")
            if excerpt and excerpt not in local.read_text(encoding="utf-8"):
                raise ValueError("短引不存在于所指本地来源文件")
            records.append(r)
    # Build atomically; an interrupted rebuild leaves the working index intact.
    with tempfile.NamedTemporaryFile(dir=db.parent, suffix=".tmp", delete=False) as f:
        tmp = Path(f.name)
    try:
        with sqlite3.connect(tmp) as c:
            c.execute("CREATE TABLE evidence (id TEXT PRIMARY KEY, perspective TEXT, kind TEXT, fingerprint TEXT, search_text TEXT, payload TEXT)")
            try:
                c.execute("CREATE VIRTUAL TABLE search USING fts5(search_text, tokenize='trigram')")
                backend = "fts5-trigram"
            except sqlite3.OperationalError:
                backend = "literal-scan"
            c.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT)")
            for r in records:
                searchable = normalize(" ".join([r["title"], r["original_excerpt"], r["chapter_or_lesson"]]))
                fingerprint = hashlib.sha256((r["origin_family"]+"\n"+normalize(r["original_excerpt"] or r["source_url"])).encode()).hexdigest()
                cur = c.execute("INSERT INTO evidence VALUES (?,?,?,?,?,?)", (r["source_id"], r["perspective"], r["record_kind"], fingerprint, searchable, json.dumps(r, ensure_ascii=False)))
                if backend == "fts5-trigram":
                    c.execute("INSERT INTO search(rowid,search_text) VALUES (?,?)", (cur.lastrowid, searchable))
            c.execute("INSERT INTO metadata VALUES ('backend',?)", (backend,))
            c.execute("INSERT INTO metadata VALUES ('records',?)", (str(len(records)),))
        tmp.replace(db)
    finally:
        tmp.unlink(missing_ok=True)
    return {"records": len(records), "backend": backend, "db": str(db)}


def query_terms(question):
    quoted = re.findall(r'[「“"]([^」”"]{3,})[」”"]', question)
    if quoted:
        return [normalize(q) for q in quoted], True
    q = normalize(question)
    terms = [t for t in TERMS if t in q]
    terms = [t for t in terms if not any(t != longer and t in longer for longer in terms)]
    if terms:
        return terms, False
    q = re.sub(r"倪海厦|倪师|李可老中医|李可|如何|怎么看|请|解释|讨论|继续|原始课程|出处|找到|视角|[？?。！!，,\s]", "", q)
    return ([q] if q else []), False


def get_evidence(source_id, db=DB):
    with connect(db) as c:
        row = c.execute("SELECT payload FROM evidence WHERE id=?", (source_id,)).fetchone()
    return json.loads(row[0]) if row else None


def search(question, perspective, limit=4, db=DB):
    terms, exact_quote = query_terms(question)
    if not terms:
        return []
    found, fingerprints = [], set()
    with connect(db) as c:
        backend = c.execute("SELECT value FROM metadata WHERE key='backend'").fetchone()[0]
        for term in terms:
            sql = "SELECT e.payload, e.fingerprint FROM evidence e "
            args = []
            if backend == "fts5-trigram" and len(term) >= 3:
                sql += "JOIN search ON search.rowid=e.rowid WHERE search MATCH ? AND e.perspective=? "
                args += ['"'+term.replace('"', '""')+'"', perspective]
            else:
                sql += "WHERE instr(e.search_text,?)>0 AND e.perspective=? "
                args += [term, perspective]
            sql += "ORDER BY (e.kind='locator_only'), length(e.search_text), e.id"
            rows = list(c.execute(sql, args).fetchall())
            # Prefer the topic's own discussion over incidental mentions in other formulas.
            def relevance(row):
                r = json.loads(row["payload"])
                return (r["record_kind"] == "locator_only",
                        not bool(re.search(r"(?<![\u4e00-\u9fff])"+re.escape(term)+r"(?![\u4e00-\u9fff])", normalize(r["title"]))),
                        term not in normalize(r["title"]),
                        term not in normalize(r["original_excerpt"]), r.get("upstream_line", 0), r["source_id"])
            rows.sort(key=relevance)
            count = 0
            for row in rows:
                r = json.loads(row["payload"])
                excerpt = normalize(r["original_excerpt"])
                haystack = normalize(r["title"]+" "+r["original_excerpt"])
                for compound in COMPOUNDS.get(term, ()):
                    haystack = haystack.replace(compound, "")
                if term in COMPOUNDS and term not in haystack:
                    continue
                if exact_quote and term not in excerpt:
                    continue
                if row["fingerprint"] in fingerprints:
                    continue
                fingerprints.add(row["fingerprint"])
                r["matched_term"] = term
                r["match_scope"] = "excerpt" if term in excerpt else "context_or_locator"
                found.append(r)
                count += 1
                if count >= limit:
                    break
    return found
