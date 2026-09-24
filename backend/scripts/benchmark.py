"""
Measure the pipeline so resume claims are backed by numbers you produced yourself.

Simulated (no API keys, every external call takes --latency seconds):
    python scripts/benchmark.py --runs 5

Live, on your own resume (needs keys in backend/.env):
    python scripts/benchmark.py --pdf path/to/resume.pdf --letters 2

Reports wall-clock time vs. the total time of all external calls
(= how long the same calls would take one after another), number of
calls per type, and how much work is skipped when resuming a crashed run.
Results are written to benchmark_results.json.
"""
import argparse
import json
import statistics
import sys
import tempfile
import threading
import time
import uuid
from collections import Counter
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402
from langgraph.checkpoint.sqlite import SqliteSaver  # noqa: E402
from langgraph.types import Command  # noqa: E402

from agents.graph.state import AgentContext  # noqa: E402
from agents.graph.workflow import build_graph  # noqa: E402


class CallTimer:
    """Wraps service functions and records how long every call takes."""

    def __init__(self):
        self.durations = []
        self.kinds = Counter()
        self.lock = threading.Lock()

    def wrap(self, kind, fn):
        def timed(*args, **kwargs):
            started = time.perf_counter()
            try:
                return fn(*args, **kwargs)
            finally:
                with self.lock:
                    self.durations.append(time.perf_counter() - started)
                    self.kinds[kind] += 1
        return timed

    def instrument(self, services):
        return replace(
            services,
            parse_resume=self.wrap("parse_resume", services.parse_resume),
            llm_json=self.wrap("llm_json", services.llm_json),
            llm_text=self.wrap("llm_text", services.llm_text),
            embed=self.wrap("embed", services.embed),
            job_sources={name: self.wrap(f"search_{name}", fn) for name, fn in services.job_sources.items()},
        )


def run_once(services, graph_input, letters, checkpointer=None):
    timer = CallTimer()
    context = AgentContext(services=timer.instrument(services))
    graph = build_graph(checkpointer=checkpointer or InMemorySaver())
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    started = time.perf_counter()
    for _ in graph.stream(graph_input, config, context=context):
        pass
    analysis_seconds = time.perf_counter() - started

    snapshot = graph.get_state(config)
    values = snapshot.values
    letters_seconds = 0.0
    if snapshot.interrupts and letters:
        job_ids = [job["id"] for job in snapshot.interrupts[0].value["jobs"]][:letters]
        started = time.perf_counter()
        for _ in graph.stream(Command(resume=job_ids), config, context=context):
            pass
        letters_seconds = time.perf_counter() - started
        values = graph.get_state(config).values

    total_call_seconds = sum(timer.durations)
    wall_seconds = analysis_seconds + letters_seconds
    return {
        "analysis_seconds": round(analysis_seconds, 3),
        "cover_letter_seconds": round(letters_seconds, 3),
        "wall_seconds": round(wall_seconds, 3),
        "sum_of_call_seconds": round(total_call_seconds, 3),
        "speedup_vs_sequential_calls": round(total_call_seconds / wall_seconds, 2) if wall_seconds else None,
        "calls": dict(timer.kinds),
        "jobs_found": len(values.get("job_results", [])),
        "jobs_analyzed": len(values.get("ranked_jobs", [])),
        "search_attempts": values.get("search_attempts"),
        "cover_letters": len(values.get("cover_letters", [])),
        "letter_drafts": [letter["drafts"] for letter in values.get("cover_letters", [])],
    }


def resume_savings(make_services, graph_input):
    """Crash one job analysis, restart from the SQLite checkpoint, count repeated calls."""
    from conftest import FakeServices

    fake = make_services()
    if not isinstance(fake, FakeServices):
        return None

    failing = {"done": False}
    original = fake.missing_skills

    def crash_once(title):
        if not failing["done"]:
            failing["done"] = True
            time.sleep(fake.latency * 3)
            raise RuntimeError("simulated crash")
        return original(title)

    fake.missing_skills = crash_once
    context = AgentContext(services=fake.as_services())
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    with tempfile.TemporaryDirectory() as tmp:
        db = str(Path(tmp) / "checkpoints.sqlite")
        with SqliteSaver.from_conn_string(db) as saver:
            try:
                for _ in build_graph(checkpointer=saver).stream(graph_input, config, context=context):
                    pass
            except RuntimeError:
                pass
        calls_before = len(fake.calls)

        with SqliteSaver.from_conn_string(db) as saver:
            for _ in build_graph(checkpointer=saver).stream(None, config, context=context):
                pass
        calls_after_resume = len(fake.calls) - calls_before

    return {
        "calls_before_crash": calls_before,
        "calls_repeated_on_resume": calls_after_resume,
        "calls_a_full_restart_would_repeat": calls_before + calls_after_resume - 1,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, help="run live on this resume (needs API keys)")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--latency", type=float, default=0.5, help="simulated seconds per external call")
    parser.add_argument("--letters", type=int, default=2, help="cover letters to generate per run")
    parser.add_argument("--out", type=Path, default=ROOT / "benchmark_results.json")
    args = parser.parse_args()

    if args.pdf:
        from agents.config import Settings
        from agents.services import build_services, extract_text_from_pdf_bytes

        settings = Settings()
        services = build_services(settings)
        graph_input = {"user_id": "benchmark", "resume_path": str(args.pdf),
                       "resume_text": extract_text_from_pdf_bytes(args.pdf.read_bytes())}
        make_services = lambda: services  # noqa: E731
        mode = "live"
    else:
        from conftest import FakeServices

        graph_input = {"user_id": "benchmark", "resume_path": "sample.pdf", "resume_text": "Python SQL analyst"}
        make_services = lambda: FakeServices(latency=args.latency)  # noqa: E731
        mode = f"simulated ({args.latency}s per call)"

    runs = []
    for i in range(args.runs):
        services = make_services()
        services = services.as_services() if hasattr(services, "as_services") else services
        result = run_once(services, graph_input, args.letters)
        runs.append(result)
        print(f"run {i + 1}: {result['wall_seconds']}s wall, "
              f"{result['sum_of_call_seconds']}s of external calls, "
              f"{result['speedup_vs_sequential_calls']}x, calls={result['calls']}")

    summary = {
        "mode": mode,
        "runs": runs,
        "median_wall_seconds": statistics.median(r["wall_seconds"] for r in runs),
        "median_sum_of_call_seconds": statistics.median(r["sum_of_call_seconds"] for r in runs),
        "median_speedup": statistics.median(r["speedup_vs_sequential_calls"] for r in runs),
        "resume_after_crash": resume_savings(make_services, graph_input),
    }
    args.out.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"\nMode: {mode}")
    print(f"Median wall time:              {summary['median_wall_seconds']}s")
    print(f"Median time if run one by one: {summary['median_sum_of_call_seconds']}s")
    print(f"Median speed-up:               {summary['median_speedup']}x")
    if summary["resume_after_crash"]:
        r = summary["resume_after_crash"]
        print(f"Resume after crash: repeated {r['calls_repeated_on_resume']} calls "
              f"instead of {r['calls_a_full_restart_would_repeat']}")
    print(f"Saved to {args.out}")


if __name__ == "__main__":
    main()
