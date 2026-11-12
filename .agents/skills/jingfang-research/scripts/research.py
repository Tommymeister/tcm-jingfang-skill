"""Unified entry: route -> local retrieval -> traceable evidence packet for Codex."""
import argparse
import hashlib
import json
import re
import uuid
from pathlib import Path

from retrieval import ROOT, DB, get_evidence, query_terms, search
from router import MODES, route

LABELS = {"comparison": "多医家对照", "nihaixia": "倪海厦视角", "like": "李可视角", "classics": "经典"}


def session_path(session):
    return ROOT / "data/sessions" / (hashlib.sha256(session.encode()).hexdigest()+".json")


def ask(question, mode=None, session=None, db=DB):
    config = json.loads((ROOT / "data/config.json").read_text(encoding="utf-8"))
    state = {}
    if session and session_path(session).exists():
        state = json.loads(session_path(session).read_text(encoding="utf-8"))
    previous = mode or state.get("mode")
    decision = route(question, previous, config["default_mode"])
    packet = {"question": question, "route": decision, "groups": {}, "limitations": [],
              "next_session_mode": previous or config["default_mode"]}
    if decision["intent"] == "engineering":
        packet["message"] = "工程任务交回 Codex 工程能力，不强制调用医学检索。"
        return packet
    if decision["intent"] == "evidence":
        packet["evidence"] = get_evidence(decision["evidence_id"], db)
        if not packet["evidence"]:
            packet["message"] = "证据编号不存在；不生成替代引用。"
        return packet
    if decision["persist_mode"]:
        packet["next_session_mode"] = decision["mode"]
    if decision["intent"] == "switch":
        packet["message"] = "已切换为"+LABELS[decision["mode"]]+"。"
    else:
        terms, exact = query_terms(question)
        followup = bool(re.search(r"继续|刚才|上述|那(?:个|么)", question))
        known_topic = any(t in question for t in ("汤", "中风", "寒", "阴", "阳", "辨证", "附子", "乌头"))
        effective = question
        if followup and not known_topic and not exact:
            effective = state.get("last_question", "")
            if not effective:
                packet["limitations"].append("需要当前聊天的上一问题或医案正文；未跨聊天猜测病案。")
        packet["retrieval_question"] = effective
        if effective:
            for perspective in ["classics"]+decision["perspectives"]:
                packet["groups"][perspective] = search(effective, perspective, config["max_results_per_source"], db)
        if exact and not any(packet["groups"].values()):
            packet["limitations"].append("资料不足：未找到所询引句，无法确认其为医家原话。")
        for name in decision["unsupported"]:
            packet["limitations"].append(name+"原始文献尚未接入；不以模型记忆冒充本地检索结果。")
        for name, rows in packet["groups"].items():
            if rows and all(r["record_kind"] == "demo" for r in rows):
                packet["limitations"].append(LABELS.get(name,name)+"：仅命中合成演示数据，未检得可支持医学观点的文献。")
            elif not rows:
                packet["limitations"].append(LABELS.get(name,name)+"：本地样本未检得直接相关证据，不强制生成观点。")
            elif len(terms) > 1:
                covered = {r["matched_term"] for r in rows}
                for term in terms:
                    if term not in covered:
                        packet["limitations"].append(LABELS.get(name,name)+"：未检得“"+term+"”的相关证据。")
        if not exact:
            state["last_question"] = effective
    state["mode"] = packet["next_session_mode"]
    if session:
        path = session_path(session)
        path.parent.mkdir(exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2))
        tmp.replace(path)
    packet["limitations"].append("来源 A/B/C/D 是核验状态，不是临床有效性等级；同一来源的短引及转载不算独立证据。")
    if decision["clinical_request"]:
        packet["limitations"].append("当前涉及真实个体，不能据这些历史资料开方、给剂量或替代就医。")
    if re.search(r"附子|乌头|四逆汤", question):
        packet["limitations"].append("附子、乌头涉及中毒风险，历史方药讨论不构成自行用药指令。")
    return packet


def markdown(packet):
    decision = packet["route"]
    parts = ["当前："+LABELS[decision["mode"]]]
    if packet.get("message"):
        parts.append(packet["message"])
    if "evidence" in packet:
        e = packet["evidence"]
        if e:
            parts += ["[%s] %s（%s）" % (e["source_id"],e["title"],e["verification_status"]),
                      e["chapter_or_lesson"]+" / "+e["page_or_timestamp"],
                      ("合成演示文本：" if e["record_kind"] == "demo" else "资料短引：")+e["original_excerpt"] if e["original_excerpt"] else "仅有定位，尚未核对原件。",
                      "[来源](%s)" % e["source_url"] if e["source_url"] else "无外部来源链接。", "本地："+str(ROOT/e["local_source_path"]), e["verification_note"]]
    for group, rows in packet["groups"].items():
        parts.append(LABELS.get(group,group)+"检索：")
        for r in rows:
            excerpt = r["original_excerpt"]
            if decision["clinical_request"]:
                excerpt = "仅提供来源定位；个体问题不展开历史操作内容。"
            link = " [来源](%s)" % r["source_url"] if r["source_url"] else ""
            parts.append("- [%s] %s / %s / %s：%s%s" % (r["source_id"], r["title"], r["verification_status"],r["page_or_timestamp"] or r["chapter_or_lesson"], excerpt or "仅有定位，未核原件。",link))
    parts.extend(packet["limitations"])
    return "\n\n".join(parts)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("question", nargs="?")
    p.add_argument("--mode", choices=MODES, help="来自本聊天最近一次明确模式；当前消息仍可覆盖")
    p.add_argument("--session", help="仅用真实聊天 ID 或新建唯一 ID，禁止多个聊天共用")
    p.add_argument("--json", action="store_true")
    p.add_argument("--interactive", action="store_true", help="本地交互检索，生成独立会话 ID")
    a = p.parse_args()
    if a.interactive:
        session = a.session or str(uuid.uuid4())
        print("本地证据检索；输入 exit 结束。本会话 ID："+session)
        while True:
            try:
                q = input("> ")
            except (EOFError, KeyboardInterrupt):
                break
            if q.strip() in ("exit", "quit", "退出"):
                break
            print(markdown(ask(q, session=session)))
    else:
        if not a.question:
            p.error("请提供问题或使用 --interactive")
        result = ask(a.question, mode=a.mode, session=a.session)
        print(json.dumps(result, ensure_ascii=False, indent=2) if a.json else markdown(result))


if __name__ == "__main__":
    main()
