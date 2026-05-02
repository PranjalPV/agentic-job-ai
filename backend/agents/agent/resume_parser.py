import os
import fitz  # PyMuPDF
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from google import genai

load_dotenv()

class ResumeParsedData(BaseModel):
    skills: list[str] = Field(description="A list of technical skills.")
    experience_level: str = Field(description="Junior, Mid, or Senior.")
    summary: str = Field(description="Short summary.")

def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        with fitz.open(pdf_path) as doc:
            for page in doc:
                text += page.get_text()
        return text
    except Exception as e:
        print(f"❌ PDF Error: {e}")
        return ""

def parse_resume(state):
    # 1. Check if API Key exists
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ ERROR: GEMINI_API_KEY not found in .env file!")
        return state

    client = genai.Client(api_key=api_key)
    pdf_path = state.get("resume_pdf_path")
    resume_text = extract_text_from_pdf(pdf_path)

    if not resume_text:
        print("❌ ERROR: Resume text is empty. Check your PDF path.")
        return state

    try:
        # 2. Call Gemini
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=f"Extract skills from this resume:\n\n{resume_text}",
            config={
                "response_mime_type": "application/json",
                "response_schema": ResumeParsedData,
            },
        )

        # 3. Check if response is valid
        if response.parsed:
            state["resume_text"] = resume_text
            state["parsed_resume"] = {
                "skills": response.parsed.skills,
                "experience_level": response.parsed.experience_level,
                "summary": response.parsed.summary
            }
        else:
            print("⚠️ Gemini returned an empty response. Check if the prompt was blocked.")

    except Exception as e:
        print(f"❌ Gemini API Error: {e}")
    return state

# --- Main Execution ---
# if __name__ == "__main__":
#     # Ensure this path is correct for your Windows machine
#     path = r"D:\PV\agentic-job-ai\resume_pdf\pranjal resume 1.0.pdf"
    
#     initial_state = {"resume_pdf_path": path}
#     result_state = parse_resume(initial_state)
    
#     # Use .get() to avoid the KeyError if parsing failed
#     parsed = result_state.get("parsed_resume")
#     if parsed:
#         print("--- Extracted Skills ---")
#         print(parsed["skills"])
#     else:
#         print("❌ Could not extract skills. Check the error messages above.")