"""Deterministic routing helpers. No medical conclusions are generated here."""
import re

ALIASES = {"nihaixia": ("倪海厦", "倪师", "倪海廈"), "like": ("李可", "李可老中医")}
UNCONNECTED = ("胡希恕", "刘渡舟", "劉渡舟", "黄煌", "黃煌", "郑钦安", "彭子益")
MODES = ("comparison", "nihaixia", "like")


def route(question, previous_mode=None, default_mode="comparison"):
    if previous_mode is not None and previous_mode not in MODES:
        raise ValueError("无效的当前会话模式")
    if default_mode not in MODES:
        raise ValueError("无效的默认模式")
    q = question.strip()
    mentioned = [key for key, aliases in ALIASES.items() if any(a in q for a in aliases)]
    unsupported = [name for name in UNCONNECTED if name in q]
    unknown = re.match(r"^(?:请问|请教)?([\u4e00-\u9fff]{2,4})(?:怎么看|如何理解|如何看待)", q)
    if unknown:
        name = unknown.group(1)
        if not any(a in name for aliases in ALIASES.values() for a in aliases) and not name.endswith(("汤", "论", "病", "方", "中医", "经典")):
            unsupported.append(name)
    for name in re.findall(r"(?:用|从|以|切换到?|切換到?)([\u4e00-\u9fff]{2,5})(?:的)?视角", q):
        if not any(a in name for aliases in ALIASES.values() for a in aliases) and name not in ("多医家",):
            unsupported.append(name)
    explicit_multi = bool(re.search(r"比较|對比|对比|对照|交叉分析|多医家|不同医家|两位医家|雙方|双方", q))
    engineering = bool(re.search(r"(?:编写|开发|调试|修复|写|测试).{0,18}(?:Python|python|脚本|代码|程序|索引)|文件管理|系统维护|安装依赖", q))
    switching = bool(re.search(r"切换|改为|切換|视角|模式|^多医家对照[。！!]?\s*$", q))
    if explicit_multi or len(mentioned) + len(set(unsupported)) > 1:
        mode, reason = "comparison", "当前要求交叉检索或涉及多位医家"
    elif mentioned:
        mode, reason = mentioned[0], "当前消息指定医家"
    elif unsupported:
        mode, reason = "comparison", "医家尚未接入，不替换为其他医家观点"
    else:
        mode, reason = previous_mode or default_mode, "继承本聊天模式" if previous_mode else "项目默认模式"
    evidence = re.search(r"(?:展开|查看|查找|展開)\s*(?:证据|證據)?\s*([NLC]\d{3,}|N-S[0-9a-f]{12}|C-J\d{3,}|DEMO\d{3,})", q, re.I)
    intent = "engineering" if engineering else "evidence" if evidence else "switch" if switching and len(q) < 24 and not re.search(r"解释|解释|分析|怎么|如何", q) else "research"
    clinical = bool(re.search(r"我(?:现在|今年|最近|的|有|该)|给我.*(?:剂量|处方|开药)|患者.*(?:开方|用药|剂量)|宝宝|我妈|我爸", q))
    if mode == "comparison":
        selected = mentioned if len(mentioned)+len(set(unsupported)) > 1 else ["nihaixia", "like"]
    else:
        selected = [mode]
    if unsupported and not mentioned:
        selected = []
        if intent == "switch":
            intent = "research"
    return {"intent": intent, "mode": mode, "reason": reason, "perspectives": selected,
            "unsupported": sorted(set(unsupported)), "evidence_id": evidence.group(1).upper() if evidence else None,
            "persist_mode": switching and intent != "engineering" and not (unsupported and not mentioned), "clinical_request": clinical}
