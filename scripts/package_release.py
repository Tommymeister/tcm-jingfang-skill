"""Create an allowlisted source ZIP only. Never upload or include runtime/private data."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

REPO=Path(__file__).resolve().parents[1]


def ignored(relative):
    return bool(set(relative.parts) & {".git","__pycache__",".venv"}) or relative.suffix == ".pyc" or any(
        relative.parts[i:i+2] in (("data","indexes"),("data","sessions")) for i in range(len(relative.parts)-1))


def inspect(root=REPO):
    manifest=json.loads((root/"PUBLIC_FILES.json").read_text(encoding="utf-8"))
    expected=set(manifest["files"])|{"PUBLIC_FILES.json"}
    actual=set()
    problems=[]
    for p in root.rglob("*"):
        rel=p.relative_to(root)
        if ignored(rel):
            continue
        if p.is_symlink():
            problems.append("symbolic link: "+rel.as_posix())
        elif p.is_file():
            actual.add(rel.as_posix())
    for name in sorted(expected ^ actual):
        problems.append("unexpected or missing public file: "+name)
    for name in sorted(expected & actual):
        p=root/name
        body=p.read_bytes()
        if name != "PUBLIC_FILES.json" and hashlib.sha256(body).hexdigest() != manifest["files"][name]:
            problems.append("hash changed: "+name)
        try:
            text=body.decode("utf-8")
        except UnicodeDecodeError:
            problems.append("non-text public file: "+name)
            continue
        for pattern in (r"/(?:Users|home)/[^/\s]+", r"[A-Za-z]:\\Users\\", r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"):
            if re.search(pattern,text):
                problems.append("possible personal information or secret: "+name)
                break
    return sorted(expected), problems


def package(output):
    output=Path(output).resolve()
    if output.is_relative_to(REPO):
        raise ValueError("ZIP 必须输出到仓库外")
    if output.exists():
        raise FileExistsError("输出文件已存在，未覆盖")
    names,problems=inspect()
    if problems:
        raise ValueError("\n".join(problems))
    with zipfile.ZipFile(output,"x",compression=zipfile.ZIP_DEFLATED) as z:
        for name in names:
            z.write(REPO/name,"jingfang-research-public/"+name)
    digest=hashlib.sha256(output.read_bytes()).hexdigest()
    return {"files":len(names),"sha256":digest}


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    print(json.dumps(package(a.output),ensure_ascii=False))
