import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO=Path(__file__).resolve().parents[1]
SKILL=REPO/".agents/skills/jingfang-research"


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pack=load("public_pack",REPO/"scripts/package_release.py")


class PublicTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project=Path(self.temp.name)/"项目 with spaces"
        self.project.mkdir()
        p=self.run_script(REPO/"scripts/install_skill.py","--project",str(self.project))
        self.assertEqual(p.returncode,0,p.stderr)
        self.skill=self.project/".agents/skills/jingfang-research"

    def run_script(self,script,*args):
        return subprocess.run([sys.executable,"-B",str(script),*args],cwd=self.temp.name,capture_output=True,text=True,timeout=20)

    def ask(self,q,*args):
        r=self.run_script(self.skill/"scripts/research.py",q,"--json",*args)
        self.assertEqual(r.returncode,0,r.stderr)
        return json.loads(r.stdout)

    def bundle(self,sid="N900001"):
        bundle=Path(self.temp.name)/"authorized-bundle"
        (bundle/"sources").mkdir(parents=True)
        r=json.loads((self.skill/"modules/demo/evidence.jsonl").read_text().splitlines()[0])
        r.update(source_id=sid,perspective="nihaixia",local_source_path="sources/fixture.txt")
        (bundle/"sources/fixture.txt").write_text(r["original_excerpt"])
        (bundle/"RIGHTS.md").write_text("Project-created synthetic test fixture; MIT. No physician quotation.")
        (bundle/"evidence.jsonl").write_text(json.dumps(r,ensure_ascii=False)+"\n")
        return bundle

    def test_independent_cwd_and_no_original_paths(self):
        p=self.ask("桂枝汤")
        self.assertEqual(p["groups"]["classics"][0]["source_id"],"DEMO001")

    def test_installed_skill_is_self_contained(self):
        self.assertTrue((self.skill/"data/indexes/evidence.sqlite3").exists())
        self.assertTrue((self.skill/"references/evidence-policy.md").exists())
        self.assertFalse((self.skill/"sources/upstream").exists())

    def test_refuses_existing_skill(self):
        sentinel=self.skill/"keep.txt";sentinel.write_text("keep")
        r=self.run_script(REPO/"scripts/install_skill.py","--project",str(self.project))
        self.assertNotEqual(r.returncode,0)
        self.assertEqual(sentinel.read_text(),"keep")

    def test_relocation_after_install(self):
        moved=Path(self.temp.name)/"搬迁后的 project"
        self.project.rename(moved)
        self.skill=moved/".agents/skills/jingfang-research"
        self.assertTrue(self.ask("桂枝汤")["groups"]["classics"])

    def test_default_comparison_and_missing_physicians(self):
        p=self.ask("桂枝汤和麻黄汤有什么区别？")
        self.assertEqual(p["route"]["mode"],"comparison")
        self.assertFalse(p["groups"]["nihaixia"])
        self.assertFalse(p["groups"]["like"])
        self.assertTrue(any("合成" in x for x in p["limitations"]))

    def test_single_doctor_mode(self):
        self.assertEqual(self.ask("倪师怎么看桂枝汤？")["route"]["mode"],"nihaixia")
        self.assertEqual(self.ask("李可如何理解真寒假热？")["route"]["mode"],"like")

    def test_session_switch_and_new_session(self):
        self.ask("切换倪师视角", "--session","a")
        self.assertEqual(self.ask("解释太阳中风","--session","a")["route"]["mode"],"nihaixia")
        self.assertEqual(self.ask("改为多医家对照","--session","a")["next_session_mode"],"comparison")
        self.assertEqual(self.ask("桂枝汤","--session","b")["route"]["mode"],"comparison")

    def test_current_multi_overrides_preference(self):
        p=self.ask("比较倪海厦和李可的桂枝汤观点","--mode","nihaixia")
        self.assertEqual(p["route"]["perspectives"],["nihaixia","like"])

    def test_demo_expansion_and_unknown_real_id(self):
        r=self.ask("展开证据 DEMO001")["evidence"]
        self.assertEqual((r["record_kind"],r["verification_status"]),("demo","D"))
        self.assertEqual(r["source_url"],"")
        self.assertIsNone(self.ask("展开证据 N003")["evidence"])

    def test_nonexistent_quote(self):
        self.assertFalse(any(self.ask('倪师说过“量子桂枝汤可以让人永生不死”吗？')["groups"].values()))

    def test_unknown_physician(self):
        self.assertEqual(self.ask("胡希恕怎么看桂枝汤？")["route"]["perspectives"],[])

    def test_engineering_not_medical(self):
        self.assertEqual(self.ask("写Python脚本检索桂枝汤")["route"]["intent"],"engineering")

    def test_offline_build_and_query(self):
        code='''import sys,socket,urllib.request
sys.path.insert(0,sys.argv[1])
def denied(*a,**k): raise AssertionError("network disabled")
socket.socket=denied
socket.create_connection=denied
urllib.request.urlopen=denied
from retrieval import build
from research import ask
assert build()["records"]==2
assert ask("桂枝汤")["groups"]["classics"]
'''
        r=subprocess.run([sys.executable,"-B","-c",code,str(self.skill/"scripts")],cwd=self.temp.name,capture_output=True,text=True,timeout=20)
        self.assertEqual(r.returncode,0,r.stderr)

    def test_user_import_and_trace(self):
        r=self.run_script(self.skill/"scripts/import_evidence.py",str(self.bundle()),"--name","fixture")
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(self.ask("倪师怎么看桂枝汤？")["groups"]["nihaixia"][0]["source_id"],"N900001")
        self.assertIn("private-fixture",self.ask("展开证据 N900001")["evidence"]["local_source_path"])

    def test_import_duplicate_rollback(self):
        old=(self.skill/"data/indexes/evidence.sqlite3").read_bytes()
        r=self.run_script(self.skill/"scripts/import_evidence.py",str(self.bundle("DEMO001")),"--name","duplicate")
        self.assertNotEqual(r.returncode,0)
        self.assertFalse((self.skill/"modules/private-duplicate").exists())
        self.assertEqual((self.skill/"data/indexes/evidence.sqlite3").read_bytes(),old)

    def test_import_rejects_escape(self):
        bundle=self.bundle()
        r=json.loads((bundle/"evidence.jsonl").read_text());r["local_source_path"]="../outside.txt"
        (bundle/"evidence.jsonl").write_text(json.dumps(r))
        p=self.run_script(self.skill/"scripts/import_evidence.py",str(bundle),"--name","escape")
        self.assertNotEqual(p.returncode,0)
        self.assertFalse((self.skill/"modules/private-escape").exists())

    def test_import_requires_rights_declaration(self):
        bundle=self.bundle();(bundle/"RIGHTS.md").unlink()
        self.assertNotEqual(self.run_script(self.skill/"scripts/import_evidence.py",str(bundle),"--name","no-rights").returncode,0)

    def test_import_rejects_quote_absent_from_source(self):
        bundle=self.bundle()
        (bundle/"sources/fixture.txt").write_text("This source does not contain the declared excerpt.")
        old=(self.skill/"data/indexes/evidence.sqlite3").read_bytes()
        p=self.run_script(self.skill/"scripts/import_evidence.py",str(bundle),"--name","wrong-quote")
        self.assertNotEqual(p.returncode,0)
        self.assertFalse((self.skill/"modules/private-wrong-quote").exists())
        self.assertEqual((self.skill/"data/indexes/evidence.sqlite3").read_bytes(),old)

    def test_empty_knowledge_base_is_usable(self):
        (self.skill/"modules/demo/evidence.jsonl").unlink()
        r=self.run_script(self.skill/"scripts/build_index.py")
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(json.loads(r.stdout)["records"],0)
        self.assertFalse(any(self.ask("桂枝汤")["groups"].values()))

    def test_public_manifest_integrity_and_privacy(self):
        _,problems=pack.inspect()
        self.assertEqual(problems,[])

    def test_pack_rejects_extra_private_file(self):
        copy=Path(self.temp.name)/"dirty-public"
        shutil.copytree(REPO,copy,ignore=shutil.ignore_patterns('__pycache__','*.sqlite3'))
        (copy/"private-note.txt").write_text("unlisted local material")
        self.assertTrue(any("private-note.txt" in s for s in pack.inspect(copy)[1]))

    def test_installer_rejects_symlink_escape(self):
        other=Path(self.temp.name)/"another-project";other.mkdir()
        outside=Path(self.temp.name)/"outside";outside.mkdir()
        (other/".agents").symlink_to(outside,target_is_directory=True)
        self.assertNotEqual(self.run_script(REPO/"scripts/install_skill.py","--project",str(other)).returncode,0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
