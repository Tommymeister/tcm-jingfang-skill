"""Import a user-authorized local bundle. No downloading or execution of bundle code."""
import argparse
import json
from pathlib import Path
import re
import shutil
import tempfile

from retrieval import ROOT, build


def import_bundle(bundle, name):
    bundle=Path(bundle).resolve()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,47}",name):
        raise ValueError("name 只允许小写字母、数字和连字符")
    records=[json.loads(l) for l in (bundle/"evidence.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    if not records:
        raise ValueError("资料包为空")
    if not (bundle/"RIGHTS.md").is_file():
        raise ValueError("需要 RIGHTS.md 说明资料使用权依据；导入器不验证法律权利")
    dest=ROOT/"modules"/("private-"+name)
    if dest.exists() or dest.is_symlink():
        raise FileExistsError("此导入名称已存在，未覆盖")
    with tempfile.TemporaryDirectory(dir=ROOT/"modules") as tmp:
        stage=Path(tmp)/"bundle"
        stage.mkdir()
        for r in records:
            relative=Path(r["local_source_path"])
            src=bundle/relative
            if relative.is_absolute() or ".." in relative.parts or not relative.parts or relative.parts[0] != "sources":
                raise ValueError("来源只允许资料包内 sources/ 相对路径")
            if not src.resolve().is_relative_to(bundle) or src.is_symlink() or not src.is_file():
                raise ValueError("来源缺失或链接越界")
            target=stage/relative
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(src,target)
            r["local_source_path"]=(Path("modules")/dest.name/relative).as_posix()
        shutil.copyfile(bundle/"RIGHTS.md",stage/"RIGHTS.md")
        (stage/"evidence.jsonl").write_text("".join(json.dumps(r,ensure_ascii=False)+"\n" for r in records),encoding="utf-8")
        stage.rename(dest)
    try:
        result=build()
    except Exception:
        shutil.rmtree(dest)
        raise
    return {"imported":len(records),"index_records":result["records"],"module":dest.name}


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("bundle",help="用户有权使用的本地资料包")
    p.add_argument("--name",required=True)
    a=p.parse_args()
    try:
        print(json.dumps(import_bundle(a.bundle,a.name),ensure_ascii=False))
    except (ValueError,FileExistsError,KeyError) as e:
        p.exit(1,str(e)+"\n")
