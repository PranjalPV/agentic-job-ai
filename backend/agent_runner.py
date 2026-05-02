import sys
import os
import tempfile

sys.path.append(os.path.dirname(__file__))

# from graph.workflow import build_graph
from agents.graph.workflow import build_graph

# Build once (good)
app_graph = build_graph()

def run_agent_on_pdf(file_bytes):
    if not file_bytes:
        raise ValueError("Empty PDF bytes")

    temp_path = None
    try:
        # 1) Save to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(file_bytes)
            temp_path = tmp.name

        # 2) State for your agent
        state = {
            "resume_pdf_path": temp_path
        }
        print("🔥 BEFORE INVOKE")
        # 3) Run agent
        result = app_graph.invoke(state)

        # (Optional but recommended) keep only what you need
        result["ranked_jobs"] = result.get("ranked_jobs", [])[:5]
        print("result")
        print(result["ranked_jobs"])
        return result

    finally:
        # 4) Cleanup temp file
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)