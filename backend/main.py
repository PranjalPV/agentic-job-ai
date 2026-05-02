from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client
import os
from dotenv import load_dotenv
from agent_runner import run_agent_on_pdf

# ----------------------------
# Load ENV
# ----------------------------
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

print("🔗 SUPABASE URL:", SUPABASE_URL)
print("🔑 KEY LOADED:", "YES" if SUPABASE_KEY else "NO")

# ----------------------------
# App Init
# ----------------------------
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173"
    ],
    allow_origin_regex=r"https://.*\.netlify\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ----------------------------
# Request Schema
# ----------------------------
class AnalyzeRequest(BaseModel):
    user_id: str
    file_path: str


# ----------------------------
# Analyze API
# ----------------------------
@app.post("/analyze")
async def analyze(req: AnalyzeRequest):
    try:
        print("\n============================")
        print("📩 NEW REQUEST")
        print("User:", req.user_id)
        print("File:", req.file_path)

        # ----------------------------
        # STEP 1: Download PDF
        # ----------------------------
        try:
            print("⬇️ Downloading file from Supabase...")

            bucket = supabase.storage.from_("resumes")
            res = bucket.download(req.file_path)

            # Handle different return types
            if hasattr(res, "data"):
                file_bytes = res.data
            else:
                file_bytes = res

            if not file_bytes:
                raise Exception("Downloaded file is empty")

            print(f"✅ FILE DOWNLOADED ({len(file_bytes)} bytes)")

        except Exception as e:
            print("❌ DOWNLOAD FAILED:", e)
            return {"status": "error", "message": "File download failed"}

        # ----------------------------
        # STEP 2: Run Agent
        # ----------------------------
        try:
            print("🤖 Running AI agent...")
            result = run_agent_on_pdf(file_bytes)

            if not result:
                raise Exception("Agent returned empty result")

            print("✅ AGENT SUCCESS")

        except Exception as e:
            print("❌ AGENT FAILED:", e)

            # fallback result (important)
            result = {
                "ranked_jobs": [],
                "skill_gaps": [],
                "roadmaps": []
            }

        # ----------------------------
        # STEP 3: Prepare Output
        # ----------------------------
        filtered_result = {
            "top_jobs": result.get("ranked_jobs", [])[:5],
            "skill_gaps": result.get("skill_gaps", []),
            "roadmap": result.get("roadmaps", [])
        }

        print("📦 FILTERED RESULT READY")
        print("Jobs count:", len(filtered_result["top_jobs"]))

        # ----------------------------
        # STEP 4: Store in DB
        # ----------------------------
        try:
            print("💾 Storing result in Supabase DB...")

            response = supabase.table("results").insert({
                "user_id": req.user_id,
                "resume_path": req.file_path,
                "result_json": filtered_result
            }).execute()

            print("✅ DB INSERT SUCCESS")
            print("DB RESPONSE:", response)

        except Exception as e:
            print("❌ DB INSERT FAILED:", e)
            return {"status": "error", "message": "DB insert failed"}

        print("🎉 PROCESS COMPLETE")
        print("============================\n")

        return {"status": "done", "data": filtered_result}

    except Exception as e:
        print("🔥 UNEXPECTED ERROR:", str(e))
        return {"status": "error", "message": str(e)}
