"""DR-7: the whole pipeline on fakes; checks the event order the dashboard expects."""

from blindrun.adapters import (
    CachedSearch,
    FakeEar,
    FakeLLM,
    FakeSandbox,
    FakeVCS,
    InProcEvents,
    MemoryStore,
)
from blindrun.pipeline.orchestrator import Deps, new_run_id, run_flow
from blindrun.types import RunStatus


def make_deps() -> Deps:
    world = {
        "fixed": False,
        "aria_yaml": "- button 'Add to cart'\n- group:\n  - button\n  - button\n  - button\n",
    }
    return Deps(
        llm=FakeLLM(world=world),
        ear=FakeEar(world=world),
        sandbox=FakeSandbox(world=world),
        search=CachedSearch(),
        vcs=FakeVCS(),
        store=MemoryStore(),
        events=InProcEvents(),
        world=world,
    )


async def test_size_picker_run():
    deps = make_deps()
    run_id = new_run_id()
    status = await run_flow(
        deps,
        run_id,
        {
            "project_id": "demo-shop",
            "url": "http://shop.test/product/1",
            "task": "buy the cheapest item",
            "fix": True,
            "repo": "demo/shop",
        },
    )
    assert status == RunStatus.done

    events = deps.events.replay(run_id)
    types = [e.type for e in events]
    assert types[0] == "run.started"
    assert "plan.ready" in types
    assert types.count("ear.phrase") >= 7  # the broken transcript streams live
    assert "ear.done" in types and "finding.new" in types
    assert types.count("fix.branch") == 3  # three candidates, three branches
    assert "fix.verified" in types
    assert types[-1] == "run.finished"  # the terminal event the dashboard closes on
    assert types.index("pr.opened") > types.index("fix.verified")  # PR opens after verification

    # seq strictly increasing per run (the SSE resume contract)
    seqs = [e.seq for e in events]
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)

    # the verify event must say the task now completes by ear
    verified = next(e for e in events if e.type == "fix.verified")
    assert verified.data["passed"] is True

    # findings landed in the store with routes set by policy
    findings = deps.store.findings[run_id]
    assert {f.route.value for f in findings} >= {"auto_fix", "human"}


async def test_report_only_mode():
    deps = make_deps()
    run_id = new_run_id()
    status = await run_flow(
        deps,
        run_id,
        {"project_id": "demo-shop", "url": "http://shop.test", "task": "buy the cheapest item", "fix": False},
    )
    assert status == RunStatus.done
    types = [e.type for e in deps.events.replay(run_id)]
    assert "fix.branch" not in types and "pr.opened" not in types
