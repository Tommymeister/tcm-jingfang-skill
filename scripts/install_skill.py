"""Install only manifest-listed public Skill files into an explicit project."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

REPO = Path(__file__).resolve().parents[1]
PREFIX = ".agents/skills/jingfang-research/"


def install(project):
    root = Path(project).expanduser().resolve()
    if not root.is_dir():
        raise ValueError("目标项目目录必须已存在")
    parent = root/".agents/skills"
    if not parent.resolve().is_relative_to(root):
        raise ValueError("目标 Skills 路径越出项目，拒绝安装")
    dest = parent/"jingfang-research"
    if dest.exists() or dest.is_symlink():
        raise FileExistsError("目标已有同名 Skill，未覆盖；请使用另一个项目")
    manifest = json.loads((REPO/"PUBLIC_FILES.json").read_text(encoding="utf-8"))
    files = [(name, digest) for name,digest in manifest["files"].items() if name.startswith(PREFIX)]
    if not files:
        raise ValueError("公开清单没有 Skill 文件")
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=parent) as tmp:
        stage=Path(tmp)/"jingfang-research"
        for name,digest in files:
            src=REPO/name
            relative=Path(name[len(PREFIX):])
            if src.is_symlink() or not src.resolve().is_relative_to(REPO) or ".." in relative.parts:
                raise ValueError("公开清单路径无效")
            if hashlib.sha256(src.read_bytes()).hexdigest() != digest:
                raise ValueError("公开文件已变化，请重新审查并生成清单")
            target=stage/relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src,target)
        subprocess.run([sys.executable,"-B",str(stage/"scripts/build_index.py")],check=True,capture_output=True,timeout=30)
        # No existing skill is ever replaced.
        if dest.exists() or dest.is_symlink():
            raise FileExistsError("目标已出现同名 Skill，未覆盖")
        stage.rename(dest)
    return dest


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project",required=True,help="明确指定目标项目目录；不更改全局配置")
    a=p.parse_args()
    try:
        dest=install(a.project)
    except (ValueError,FileExistsError,subprocess.SubprocessError) as e:
        p.exit(1,str(e)+"\n")
    print("已安装项目级 jingfang-research；请在目标项目启动新聊天。")
