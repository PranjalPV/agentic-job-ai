"""
Run the full agent on a local PDF from the terminal (no website or Supabase needed).

    python -m agents.main path/to/resume.pdf [--out result.json]

Needs GEMINI_API_KEY, GROQ_API_KEY and at least one job source key in backend/.env.
"""
import argparse
import json
import logging
import sys
import time
import uuid
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from agents.config import Settings
from agents.errors import UserFacingError
from agents.graph.runtime import set_current_context
from agents.graph.state import AgentContext
from agents.graph.workflow import build_graph
from agents.results import build_result
from agents.services import build_services, extract_text_from_pdf_bytes


def stream(graph, graph_input, config, context):
    set_current_context(context)
    for _namespace, mode, chunk in graph.stream(
        graph_input, config, stream_mode=["custom"], subgraphs=True
    ):
        if mode == "custom" and isinstance(chunk, dict) and chunk.get("message"):
            print(f"  • {chunk['message']}")


def ask_selection(jobs):
    print("\nTop jobs:")
    for job in jobs:
        print(f"  [{job['id']}] {job['title']} at {job['company']}")
    raw = input("\nJob ids for cover letters (e.g. 0,2), or Enter to skip: ").strip()
    return [int(part) for part in raw.replace(" ", "").split(",") if part.isdigit()]


def main():
    parser = argparse.ArgumentParser(description="Run the job agent on a resume PDF")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--out", type=Path, default=Path("result.json"))
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING)
    # Windows consoles default to cp1252 and can't print the symbols below
    for output in (sys.stdout, sys.stderr):
        try:
            output.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    settings = Settings()
    missing = [m for m in settings.missing() if not m.startswith("SUPABASE")]
    if missing:
        sys.exit(f"Missing settings in backend/.env: {', '.join(missing)}")

    graph = build_graph(checkpointer=InMemorySaver())
    context = AgentContext(services=build_services(settings), location=settings.job_location)
    config = {"configurable": {"thread_id": str(uuid.uuid4()), "context": context}}

    started = time.perf_counter()
    try:
        resume_text = extract_text_from_pdf_bytes(args.pdf.read_bytes())
        print("Analyzing resume...")
        stream(graph, {"user_id": "local", "resume_path": str(args.pdf), "resume_text": resume_text},
               config, context)

        snapshot = graph.get_state(config)
        if snapshot.interrupts:
            selected = ask_selection(snapshot.interrupts[0].value["jobs"])
            stream(graph, Command(resume=selected), config, context)
    except UserFacingError as e:
        sys.exit(f"❌ {e}")

    values = graph.get_state(config).values
    if not values.get("ranked_jobs"):
        sys.exit("❌ No matching jobs were found for this resume.")

    args.out.write_text(json.dumps(build_result(values), indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n✅ Done in {time.perf_counter() - started:.1f}s (including your selection time)")
    print(f"   Result saved to {args.out}")


if __name__ == "__main__":
    main()
