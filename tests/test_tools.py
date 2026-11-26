from pathlib import Path

import pytest

from appbuilder.tools import (CommandLinter, CommandResult, EditThenLint, EmulatorTool, FakeEmulator, FakeGradle,
                              FakeLinter, FakeRunner, GradleTool, SubprocessRunner, WorkspaceError)


def bad_if_todo(p, t):
    return f"{p.name}: TODO" if "TODO" in t else None


def test_edit_kept_when_lint_passes(tmp_path):
    t = EditThenLint(tmp_path, FakeLinter(bad_if_todo))
    r = t.apply({"a/Main.kt": "fun main() {}"})
    assert r.applied and not r.rolled_back
    assert (tmp_path / "a/Main.kt").read_text() == "fun main() {}"


def test_rollback_restores_existing_and_removes_new(tmp_path):
    (tmp_path / "Old.kt").write_text("old")
    t = EditThenLint(tmp_path, FakeLinter(bad_if_todo))
    r = t.apply({"Old.kt": "TODO", "new/New.kt": "ok"})
    assert not r.applied and r.rolled_back and r.lint.messages
    assert (tmp_path / "Old.kt").read_text() == "old"
    assert not (tmp_path / "new/New.kt").exists()


def test_rollback_restores_deleted_file(tmp_path):
    (tmp_path / "Gone.kt").write_text("keep")
    t = EditThenLint(tmp_path, FakeLinter(lambda p, t: "always fails"))
    t.apply({"Gone.kt": None, "B.kt": "x"})
    assert (tmp_path / "Gone.kt").read_text() == "keep"


def test_rollback_when_linter_raises(tmp_path):
    (tmp_path / "A.kt").write_text("orig")
    def boom(p, t): raise RuntimeError("linter crashed")
    with pytest.raises(RuntimeError):
        EditThenLint(tmp_path, FakeLinter(boom)).apply({"A.kt": "new"})
    assert (tmp_path / "A.kt").read_text() == "orig"


@pytest.mark.parametrize("bad", ["../escape.kt", "/etc/passwd", "a/../../x"])
def test_path_escape_rejected_before_any_write(tmp_path, bad):
    with pytest.raises(WorkspaceError):
        EditThenLint(tmp_path, FakeLinter()).apply({"ok.kt": "x", bad: "y"})
    assert not (tmp_path / "ok.kt").exists()


def test_symlink_escape_rejected(tmp_path):
    outside = tmp_path / "outside"; outside.mkdir()
    ws = tmp_path / "ws"; ws.mkdir()
    (ws / "link").symlink_to(outside)
    with pytest.raises(WorkspaceError):
        EditThenLint(ws, FakeLinter()).apply({"link/x.kt": "y"})


def test_command_linter_failure_rolls_back(tmp_path):
    runner = FakeRunner(default=CommandResult(("ktlint",), 1, "A.kt:1: bad style"))
    t = EditThenLint(tmp_path, CommandLinter(runner))
    r = t.apply({"A.kt": "x"})
    assert r.rolled_back and "bad style" in r.lint.messages[0]
    assert runner.calls[0] == ("ktlint", "A.kt")
    assert not (tmp_path / "A.kt").exists()


def test_gradle_success_and_error_parsing(tmp_path):
    out = "e: file:///A.kt:3:1 Unresolved reference: foo\n> Task :app:compileDebugKotlin FAILED\nFAILURE: Build failed"
    r = FakeRunner(default=CommandResult(("./gradlew",), 1, out))
    res = GradleTool(r).run(tmp_path, "assembleDebug")
    assert not res.ok and any("Unresolved reference" in e for e in res.errors)
    assert r.calls[0][:2] == ("./gradlew", "assembleDebug")
    assert GradleTool(FakeRunner()).run(tmp_path, ":app:assembleDebug").ok


@pytest.mark.parametrize("task", ["publish", "assembleDebug; rm -rf /", "--init-script=x", "$(id)"])
def test_gradle_rejects_unlisted_or_injected_tasks(tmp_path, task):
    with pytest.raises(ValueError):
        GradleTool(FakeRunner()).run(tmp_path, task)


def test_emulator_flow_and_validation(tmp_path):
    apk = tmp_path / "app.apk"; apk.write_bytes(b"x")
    r = FakeRunner(default=CommandResult(("adb",), 0, "OK (3 tests)"))
    res = EmulatorTool(r, tmp_path, serial="emulator-5554").run(apk, "com.example.app")
    assert res.ok and r.calls[0][:3] == ("adb", "-s", "emulator-5554") and len(r.calls) == 2
    with pytest.raises(ValueError):
        EmulatorTool(r, tmp_path).run(apk, "com.x; reboot")
    assert not EmulatorTool(r, tmp_path).run(tmp_path / "missing.apk", "com.example.app").ok
    bad = FakeRunner(default=CommandResult(("adb",), 0, "FAILURES!!!"))
    assert not EmulatorTool(bad, tmp_path).run(apk, "com.example.app").ok


def test_fakes_are_marked_unverified(tmp_path):
    e = FakeEmulator().run(tmp_path / "a.apk", "com.example.app")
    assert e.ok and e.verified_on_emulator is False
    g = FakeGradle(failures={"assembleDebug": ("boom",)})
    assert not g.run(tmp_path, "assembleDebug").ok and g.run(tmp_path, "build").ok


def test_subprocess_runner_scrubs_env_and_times_out(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-secret")
    r = SubprocessRunner().run(["env"], tmp_path, 10)
    assert r.ok and "ANTHROPIC_API_KEY" not in r.stdout
    assert SubprocessRunner().run(["sleep", "5"], tmp_path, 0.2).timed_out
    assert SubprocessRunner().run(["nonexistent-bin-xyz"], tmp_path, 5).returncode == 127
    with pytest.raises(TypeError):
        SubprocessRunner().run("echo hi", tmp_path, 5)
