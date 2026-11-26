"""Day 4 offline tests: UI/Data engineers, Build Doctor, failure memory. Fakes only."""
import json
from pathlib import Path

import pytest

from appbuilder.agents import (BUILD_DOCTOR, DATA_ENGINEER, UI_ENGINEER, AgentOutputError, AgentRunner,
                               BuildDoctor, FailureMemory, RecordedClient, run_code_agent, signature)
from appbuilder.agents.memory import normalise
from appbuilder.orchestrator import SchemaRegistry
from appbuilder.tools import EditThenLint, FakeLinter, GradleResult

FIX = Path(__file__).parent / "fixtures"
MG = json.loads((FIX / "recorded_module_graph.json").read_text())
STORY = {"id": "s1", "title": "Add task", "acceptance": ["Given a list When I add Then it shows"]}
SCHEMAS = SchemaRegistry()
ERR = "e: file:///work/app/feature/tasks/src/main/kotlin/TaskScreen.kt:12:5 Unresolved reference: Scaffold"
BAD_SRC = "package x\nfun f() { Scaffold() }\n"
PATCH = {"path": "feature/tasks/src/main/kotlin/TaskScreen.kt",
         "find": "fun f() { Scaffold() }", "replace": "import androidx.compose.material3.Scaffold\nfun f() { Scaffold() }"}


def change(module, files, **kw):
    return json.dumps({"module": module, "summary": "s", "files": [{"path": p, "content": c} for p, c in files.items()], **kw})


def editor(tmp_path, check=None):
    return EditThenLint(tmp_path, FakeLinter(check) if check else FakeLinter())


# ---- UI / Data engineers -------------------------------------------------
def ui_inputs(module=":feature:tasks"):
    return {"module": module, "module_graph": MG, "story": STORY}


def test_ui_engineer_writes_files_through_edit_then_lint(tmp_path):
    p = "feature/tasks/src/main/kotlin/TaskScreen.kt"
    c = RecordedClient([change(":feature:tasks", {p: "package x\n@Composable fun TaskScreen() {}\n"})])
    doc, res = run_code_agent(AgentRunner(c), UI_ENGINEER, ui_inputs(), editor(tmp_path))
    assert SCHEMAS.errors("code-change", doc) == [] and res.applied
    assert (tmp_path / p).read_text().startswith("package x")
    assert '<untrusted name="story">' in c.calls[0].user


def test_lint_failure_rolls_back_and_becomes_feedback(tmp_path):
    p = "feature/tasks/src/main/kotlin/A.kt"
    (tmp_path / "feature/tasks/src/main/kotlin").mkdir(parents=True)
    (tmp_path / p).write_text("old")
    ed = editor(tmp_path, lambda path, t: "ktlint: bad" if "BAD" in t else None)
    c = RecordedClient([change(":feature:tasks", {p: "BAD"})])
    with pytest.raises(AgentOutputError, match="ktlint: bad"):
        run_code_agent(AgentRunner(c), UI_ENGINEER, ui_inputs(), ed)
    assert (tmp_path / p).read_text() == "old"


@pytest.mark.parametrize("agent,module,files,expect", [
    (UI_ENGINEER, ":feature:tasks", {"data/src/A.kt": "x"}, "must be under feature/tasks/src/"),
    (UI_ENGINEER, ":feature:tasks", {"feature/tasks/src/../../x.kt": "x"}, "relative path"),
    (UI_ENGINEER, ":feature:tasks", {"feature/tasks/src/main/A.java": "x"}, "only .kt"),
    (UI_ENGINEER, ":feature:tasks", {"feature/tasks/src/A.kt": "import androidx.room.Dao\n"}, "forbidden import"),
    (UI_ENGINEER, ":feature:tasks", {"feature/tasks/src/A.kt": "k = sk-ant-abc123"}, "secret"),
    (UI_ENGINEER, ":data", {"data/src/A.kt": "x"}, "writes only"),
    (DATA_ENGINEER, ":ui", {"ui/src/A.kt": "x"}, "unknown target module"),
    (DATA_ENGINEER, ":data", {"data/src/A.kt": "import androidx.compose.ui.Modifier\n"}, "forbidden import"),
    (DATA_ENGINEER, ":data", {"data/src/A.kt": "@Database(entities=[], version = 1, exportSchema = false)\nclass D"}, "exportSchema"),
    (DATA_ENGINEER, ":data", {"data/src/local.properties": "x"}, "not writable"),
    (DATA_ENGINEER, ":data", {"data/src/A.kt": "@Database(autoMigrations=[AutoMigration(from=1, to=2)], entities=[], version=2, exportSchema=false)\nclass D"}, "exportSchema"),
    (DATA_ENGINEER, ":data", {"data/src/A.kt": "@Database(entities=[], version=1)\nclass D"}, "exportSchema"),
    (DATA_ENGINEER, ":data", {"data/src/A.kt": "// Migration(\n@Database(entities=[], version=2, exportSchema=true)\nclass D"}, "db_version"),
    (DATA_ENGINEER, ":data", {"data/schemas/x.txt": "x"}, "only .kt"),
])
def test_code_agents_reject_bad_output(tmp_path, agent, module, files, expect):
    c = RecordedClient([change(module, files)])
    with pytest.raises(AgentOutputError, match=expect):
        run_code_agent(AgentRunner(c), agent, {**ui_inputs(module)}, editor(tmp_path))
    assert list(tmp_path.iterdir()) == []  # nothing written


def test_data_engineer_migration_required_on_version_bump(tmp_path):
    db = "@Database(entities=[], version = 2, exportSchema = true)\nabstract class D"
    inputs = {**ui_inputs(":data"), "db_version": 1}
    with pytest.raises(AgentOutputError, match="needs a Migration"):
        run_code_agent(AgentRunner(RecordedClient([change(":data", {"data/src/A.kt": db})])), DATA_ENGINEER, inputs, editor(tmp_path))
    ok = {"data/src/A.kt": db, "data/src/M.kt": "val M = Migration(1, 2) {}"}
    doc, res = run_code_agent(AgentRunner(RecordedClient([change(":data", ok, db_version=2)])), DATA_ENGINEER, inputs, editor(tmp_path))
    assert res.applied and doc["db_version"] == 2


# ---- failure memory ------------------------------------------------------
def test_signature_ignores_paths_lines_and_names():
    a = "e: file:///a/b/X.kt:12:5 Unresolved reference: Foo"
    b = "e: /other/proj/Y.kt:99:1 Unresolved reference: Bar"
    assert signature([a]) == signature([b]) != signature(["e: Type mismatch"])
    assert "foo" not in normalise(a)


def test_memory_persists_and_refuses_secrets(tmp_path):
    f = tmp_path / "mem" / "failures.json"
    m = FailureMemory(f)
    m.record([ERR], "missing import", [PATCH])
    assert FailureMemory(f).lookup([ERR]).patches == [PATCH]
    with pytest.raises(ValueError, match="secret"):
        m.record(["e: x"], "d", [{**PATCH, "replace": "key=sk-ant-zzz"}])
    with pytest.raises(ValueError, match="unsafe path"):
        m.record(["e: y"], "d", [{**PATCH, "path": "../x.kt"}])
    assert "sk-ant" not in f.read_text()


def test_unproven_entry_stops_being_used():
    m = FailureMemory()
    e = m.record([ERR], "d", [PATCH])
    m.mark(e.signature, False)
    m.mark(e.signature, False)
    assert m.lookup([ERR]) is None


# ---- Build Doctor --------------------------------------------------------
class ScriptedGradle:
    """Red until `fixed(project)` is true; reports ERR while red."""
    def __init__(self, fixed):
        self.fixed, self.calls = fixed, 0

    def run(self, project, task):
        self.calls += 1
        ok = self.fixed(Path(project))
        return GradleResult(ok, task, () if ok else (ERR,))


def project(tmp_path):
    f = tmp_path / PATCH["path"]
    f.parent.mkdir(parents=True)
    f.write_text(BAD_SRC)
    return tmp_path, (lambda p: "import androidx.compose.material3.Scaffold" in (p / PATCH["path"]).read_text())


def fix_reply(patch=PATCH):
    return json.dumps({"diagnosis": "missing import", "patches": [patch]})


def doctor(tmp, client, mem, gradle, **kw):
    return BuildDoctor(AgentRunner(client), mem, gradle, EditThenLint(tmp, FakeLinter()), tmp, **kw)


def test_green_build_needs_no_work(tmp_path):
    c = RecordedClient([])
    rep = doctor(tmp_path, c, FailureMemory(), ScriptedGradle(lambda p: True)).fix()
    assert rep.green and rep.rounds == 0 and c.calls == []


def test_doctor_uses_model_then_records_fix(tmp_path):
    tmp, fixed = project(tmp_path)
    mem, c = FailureMemory(tmp_path / "m.json"), RecordedClient([fix_reply()])
    rep = doctor(tmp, c, mem, ScriptedGradle(fixed)).fix()
    assert rep.green and rep.model_calls == 1 and rep.steps[-1]["outcome"] == "green"
    assert "Unresolved reference" in c.calls[0].user and "TaskScreen" in c.calls[0].user  # error + file context
    assert mem.lookup([ERR]) is not None
    assert SCHEMAS.errors("build-fix", json.loads(fix_reply())) == []


def test_doctor_checks_memory_first_and_skips_model(tmp_path):
    tmp, fixed = project(tmp_path)
    mem = FailureMemory()
    mem.record([ERR], "missing import", [PATCH])
    c = RecordedClient([])  # any model call would raise
    rep = doctor(tmp, c, mem, ScriptedGradle(fixed)).fix()
    assert rep.green and rep.rounds == 1 and rep.model_calls == 0 and c.calls == []
    assert rep.steps[0]["source"] == "memory" and mem.lookup([ERR]).hits == 1


def test_second_identical_failure_is_fixed_from_memory_in_one_round(tmp_path):
    mem = FailureMemory()
    t1, fixed = project(tmp_path / "one")
    c1 = RecordedClient([fix_reply()])
    assert doctor(t1, c1, mem, ScriptedGradle(fixed)).fix().model_calls == 1
    t2, fixed2 = project(tmp_path / "two")
    c2 = RecordedClient([])
    rep = doctor(t2, c2, mem, ScriptedGradle(fixed2)).fix()
    assert rep.green and rep.rounds == 1 and c2.calls == []


def test_bad_memory_fix_is_reverted_and_model_takes_over(tmp_path):
    tmp, fixed = project(tmp_path)
    mem = FailureMemory()
    mem.record([ERR], "wrong", [{**PATCH, "replace": "fun f() { Scaffold2() }"}])
    c = RecordedClient([fix_reply()])
    rep = doctor(tmp, c, mem, ScriptedGradle(fixed)).fix()
    assert rep.green and [s["source"] for s in rep.steps] == ["memory", "model", ]
    assert rep.steps[0]["outcome"].startswith("reverted")
    assert "Scaffold2" not in (tmp / PATCH["path"]).read_text()
    assert mem.entries[signature([ERR])].misses == 0  # replaced by the proven fix


def test_invalid_patch_and_bad_reply_feed_back_then_recover(tmp_path):
    tmp, fixed = project(tmp_path)
    c = RecordedClient(["not json", fix_reply({**PATCH, "find": "does not exist"}), fix_reply()])
    rep = doctor(tmp, c, FailureMemory(), ScriptedGradle(fixed)).fix()
    assert rep.green and rep.rounds == 3
    assert "occurs 0 times" in c.calls[2].user and "previous reply was rejected" in c.calls[2].user


def test_round_cap_escalates(tmp_path):
    tmp, _ = project(tmp_path)
    c = RecordedClient([fix_reply()], repeat_last=True)
    g = ScriptedGradle(lambda p: False)
    rep = doctor(tmp, c, FailureMemory(), g, max_rounds=99).fix()
    assert not rep.green and rep.escalated and rep.rounds == 5


@pytest.mark.parametrize("bad", [{"path": "local.properties"}, {"path": "../x.kt"}, {"replace": "k=sk-ant-abc"}])
def test_doctor_refuses_unsafe_patches(tmp_path, bad):
    tmp, fixed = project(tmp_path)
    c = RecordedClient([fix_reply({**PATCH, **bad}), fix_reply()])
    rep = doctor(tmp, c, FailureMemory(), ScriptedGradle(fixed)).fix()
    assert rep.green and rep.steps[0]["outcome"] == "invalid reply"
    assert not (tmp.parent / "x.kt").exists()


def test_lint_rejected_patch_rolls_back(tmp_path):
    tmp, fixed = project(tmp_path)
    ed = EditThenLint(tmp, FakeLinter(lambda p, t: "ktlint: nope"))
    c = RecordedClient([fix_reply()], repeat_last=True)
    rep = BuildDoctor(AgentRunner(c), FailureMemory(), ScriptedGradle(fixed), ed, tmp, max_rounds=2).fix()
    assert not rep.green and (tmp / PATCH["path"]).read_text() == BAD_SRC


def test_doctor_context_excludes_files_outside_project(tmp_path):
    tmp, fixed = project(tmp_path)
    outside = tmp_path.parent / "secret.kt"
    outside.write_text("TOPSECRET")
    from appbuilder.agents.doctor import context_files
    assert context_files(tmp, [f"e: {outside}:1:1 boom"]) == {}


def test_data_engineer_may_write_room_schema_json(tmp_path):
    files = {"data/src/A.kt": "class A", "data/schemas/com.x.Db/1.json": "{}"}
    _, res = run_code_agent(AgentRunner(RecordedClient([change(":data", files)])), DATA_ENGINEER, ui_inputs(":data"), editor(tmp_path))
    assert res.applied


def test_nested_parens_with_real_migration_pass(tmp_path):
    db = "@Database(autoMigrations=[AutoMigration(from=1, to=2)], entities=[], version=2, exportSchema=true)\nabstract class D"
    _, res = run_code_agent(AgentRunner(RecordedClient([change(":data", {"data/src/A.kt": db}, db_version=2)])),
                            DATA_ENGINEER, {**ui_inputs(":data"), "db_version": 1}, editor(tmp_path))
    assert res.applied


def test_symlinked_target_is_rejected(tmp_path):
    (tmp_path / "local.properties").write_text("secret")
    d = tmp_path / "feature/tasks/src"
    d.mkdir(parents=True)
    (d / "A.kt").symlink_to(tmp_path / "local.properties")
    c = RecordedClient([change(":feature:tasks", {"feature/tasks/src/A.kt": "x"})])
    with pytest.raises(AgentOutputError, match="symlink"):
        run_code_agent(AgentRunner(c), UI_ENGINEER, ui_inputs(), editor(tmp_path))
    assert (tmp_path / "local.properties").read_text() == "secret"


@pytest.mark.parametrize("path", ["build.gradle.kts", "app/build.gradle.kts", "gradle/libs.versions.toml",
                                  "gradle.properties", "buildSrc/src/main/kotlin/X.kt.kts", "settings.gradle.kts"])
def test_doctor_cannot_patch_build_files(tmp_path, path):
    tmp, fixed = project(tmp_path)
    c = RecordedClient([fix_reply({**PATCH, "path": path}), fix_reply()])
    rep = doctor(tmp, c, FailureMemory(), ScriptedGradle(fixed)).fix()
    assert rep.green and rep.steps[0]["outcome"] == "invalid reply"
    with pytest.raises(ValueError):
        FailureMemory().record([ERR], "d", [{**PATCH, "path": path}])


def test_doctor_symlink_patch_target_rejected(tmp_path):
    tmp, fixed = project(tmp_path)
    outside = tmp_path.parent / "outside.kt"
    outside.write_text("fun f() { Scaffold() }")
    link = tmp / "app/src/Link.kt"
    link.parent.mkdir(parents=True)
    link.symlink_to(outside)
    c = RecordedClient([fix_reply({**PATCH, "path": "app/src/Link.kt"}), fix_reply()])
    rep = doctor(tmp, c, FailureMemory(), ScriptedGradle(fixed)).fix()
    assert rep.green and "symlink" in rep.steps[0]["outcome"]
    assert outside.read_text() == "fun f() { Scaffold() }"


def test_corrupt_or_poisoned_memory_file_is_ignored(tmp_path):
    f = tmp_path / "m.json"
    f.write_text("{not json")
    assert FailureMemory(f).entries == {}
    good = {"signature": "a", "sample": "s", "diagnosis": "d", "hits": 0, "misses": 0,
            "patches": [{"path": "build.gradle.kts", "find": "a", "replace": "b"}]}
    leak = {**good, "signature": "b", "sample": "token=abcd1234", "patches": [PATCH]}
    extra = {**good, "signature": "c", "evil": 1, "patches": [PATCH]}
    f.write_text(json.dumps({"entries": [good, leak, extra, "junk"]}))
    assert FailureMemory(f).entries == {}


def test_secrets_in_error_text_not_stored_or_sent(tmp_path):
    with pytest.raises(ValueError, match="secret"):
        FailureMemory().record(["Could not GET https://user:ghp_abcdefghijklmnopqrstu@repo/x"], "d", [PATCH])
    tmp, fixed = project(tmp_path)
    (tmp / PATCH["path"]).write_text(BAD_SRC + "val k = \"storePassword=hunter22\"\n")
    c = RecordedClient([fix_reply()])
    from appbuilder.agents.doctor import context_files
    assert context_files(tmp, [ERR.replace("/work/app/", str(tmp) + "/")]) == {}


def test_failed_revert_marks_tree_dirty(tmp_path):
    tmp, fixed = project(tmp_path)
    mem = FailureMemory()
    mem.record([ERR], "wrong", [{**PATCH, "replace": "fun f() { Scaffold2() }"}])
    state = {"n": 0}

    def check(path, text):  # accepts the patch, rejects restoring the original
        return "ktlint: no" if "Scaffold2" not in text and state["n"] else None

    class Ed(EditThenLint):
        def apply(self, edits):
            r = super().apply(edits)
            state["n"] += 1
            return r
    ed = Ed(tmp, FakeLinter(check))
    rep = BuildDoctor(AgentRunner(RecordedClient([])), mem, ScriptedGradle(fixed), ed, tmp).fix()
    assert rep.dirty and not rep.green and "revert failed" in rep.steps[-1]["outcome"]


def test_unchanged_errors_patch_is_reverted_and_feedback_given(tmp_path):
    tmp, _ = project(tmp_path)
    noop = {**PATCH, "replace": PATCH["find"] + " // x"}
    c = RecordedClient([fix_reply(noop), fix_reply()])
    g = ScriptedGradle(lambda p: "import androidx" in (p / PATCH["path"]).read_text())
    rep = doctor(tmp, c, FailureMemory(), g).fix()
    assert rep.green and rep.steps[0]["outcome"] == "no progress; reverted"
    assert "did not change" in c.calls[1].user
