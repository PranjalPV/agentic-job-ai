# from graph.workflow import build_graph
from agents.graph.workflow import build_graph 
import json

def test_agent():
    app = build_graph()

    state = {
        "resume_pdf_path": r"./test_resume.pdf"
    }

    print("Running agent...\n")

    result = app.invoke(state)

    print("\n✅ FINAL RESULT:\n")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    test_agent()