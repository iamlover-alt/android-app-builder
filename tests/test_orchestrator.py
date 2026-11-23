import json

import pytest

from appbuilder.orchestrator import (GraphError, Orchestrator, RunLog, SchemaRegistry, Task, TaskGraph)

PRD = {"id": "p1", "app_name": "Todo", "target_sdk": 36, "mvp_cut": ["s1"],
       "stories": [{"id": "s1", "as_a": "user", "i_want": "tasks", "so_that": "I remember",
                    "acceptance": ["Given x When y Then z"]}]}
MG = {"modules": [{"path": ":app", "layer": "app", "depends_on": []}]}


def graph():
    return TaskGraph(
        [Task("prd", "strategist", ["goal"], ["prd"]),
         Task("arch", "architect", ["prd"], ["module-graph"])],
        external={"goal"})


def good_agents():
    return {"strategist": lambda t, i, f: {"prd": PRD},
            "architect": lambda t, i, f: {"module-graph": MG}}


def test_registry_loads_all_schemas():
    assert {"prd", "module-graph", "task", "test-report"} <= set(SchemaRegistry().names())


def test_happy_path_runs_in_dependency_order_and_logs():
    o = Orchestrator(graph(), good_agents())
    o.seed("goal", "a todo app")
    r = o.run()
    assert r.ok and r.artifacts["module-graph"] == MG
    ready = [e["artifact"] for e in o.log.of("artifact_ready")]
    assert ready == ["goal", "prd", "module-graph"]


def test_task_waits_for_input_artifact():
    o = Orchestrator(graph(), good_agents())
    r = o.run()  # goal never seeded
    assert not r.ok and all(t.status == "blocked" for t in r.tasks.values())


def test_invalid_handoff_triggers_fix_round_with_feedback():
    seen = []

    def flaky(t, i, f):
        seen.append(list(f))
        return {"prd": {"id": "p1"}} if not f else {"prd": PRD}

    o = Orchestrator(graph(), {**good_agents(), "strategist": flaky})
    o.seed("goal", "g")
    r = o.run()
    assert r.ok and r.tasks["prd"].fix_rounds == 1
    assert seen[0] == [] and any("app_name" in e for e in seen[1])


def test_target_sdk_below_36_rejected():
    bad = dict(PRD, target_sdk=34)
    errs = SchemaRegistry().errors("prd", bad)
    assert errs and "target_sdk" in errs[0]


def test_five_round_cap_escalates_and_blocks_descendants():
    calls = []

    def always_bad(t, i, f):
        calls.append(1)
        return {"prd": {}}

    o = Orchestrator(graph(), {**good_agents(), "strategist": always_bad})
    o.seed("goal", "g")
    r = o.run()
    assert len(calls) == 6  # first attempt + 5 fix rounds
    assert r.tasks["prd"].status == "escalated" and r.tasks["prd"].fix_rounds == 5
    assert r.tasks["arch"].status == "blocked"
    esc = r.escalations[0]
    assert esc.task_id == "prd" and esc.rounds == 5 and esc.evidence
    assert len(o.log.of("escalation")) == 1


def test_agent_exception_counts_as_failed_round():
    n = {"c": 0}

    def boom(t, i, f):
        n["c"] += 1
        if n["c"] < 3:
            raise RuntimeError("model timeout")
        return {"prd": PRD}

    o = Orchestrator(graph(), {**good_agents(), "strategist": boom})
    o.seed("goal", "g")
    r = o.run()
    assert r.ok and r.tasks["prd"].fix_rounds == 2


def test_missing_and_undeclared_outputs_rejected():
    o = Orchestrator(graph(), {**good_agents(), "strategist": lambda t, i, f: {"extra": 1}}, max_fix_rounds=0)
    o.seed("goal", "g")
    r = o.run()
    ev = r.escalations[0].evidence
    assert any("missing output" in e for e in ev) and any("undeclared" in e for e in ev)


def test_cap_cannot_exceed_five():
    with pytest.raises(ValueError):
        Orchestrator(graph(), good_agents(), max_fix_rounds=6)


def test_graph_rejects_cycle_duplicates_and_orphans():
    with pytest.raises(GraphError, match="cycle"):
        TaskGraph([Task("a", "x", ["b"], ["a"]), Task("b", "x", ["a"], ["b"])])
    with pytest.raises(GraphError, match="duplicate"):
        TaskGraph([Task("a", "x", [], ["a"]), Task("a", "x", [], ["b"])])
    with pytest.raises(GraphError, match="produced by both"):
        TaskGraph([Task("a", "x", [], ["o"]), Task("b", "x", [], ["o"])])
    with pytest.raises(GraphError, match="nothing produces"):
        TaskGraph([Task("a", "x", ["ghost"], ["o"])])


def test_unknown_agent_and_schemaless_output_rejected_unless_opaque():
    with pytest.raises(ValueError, match="no agent"):
        Orchestrator(graph(), {})
    g = TaskGraph([Task("b", "builder", [], ["apk"])])
    with pytest.raises(ValueError, match="no schema"):
        Orchestrator(g, {"builder": lambda t, i, f: {"apk": "x"}})
    o = Orchestrator(g, {"builder": lambda t, i, f: {"apk": "x"}}, opaque={"apk"})
    assert o.run().ok


def test_run_log_is_jsonl_and_omits_artifact_bodies(tmp_path):
    p = tmp_path / "runs" / "log.jsonl"
    o = Orchestrator(graph(), good_agents(), log=RunLog(p))
    o.seed("goal", "SECRET-GOAL-TEXT")
    o.run()
    text = p.read_text()
    rows = [json.loads(line) for line in text.splitlines()]
    assert rows[0]["event"] == "artifact_ready" and rows[-1]["event"] == "run_end"
    assert [r["seq"] for r in rows] == list(range(len(rows)))
    assert "SECRET-GOAL-TEXT" not in text and "Todo" not in text
