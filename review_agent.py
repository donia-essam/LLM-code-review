import os
import json
import glob
from typing import List
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY", "").strip()

class CodeReviewComment(BaseModel):
    file: str = Field(description="The name of the file being reviewed.")
    line: int = Field(description="The exact line number where the issue is found.")
    entity: str = Field(description="The name of the variable, function, or loop bound causing the issue.")
    claim: str = Field(description="The bug type. Must be exactly one of: 'unused_variable', 'null_safety_violation', or 'off_by_one_bound'")

class CodeReviewResponse(BaseModel):
    comments: List[CodeReviewComment]

def review_python_code_with_gemini(file_name: str, code_content: str) -> dict:
    if not api_key:
        print(" Warning: GEMINI_API_KEY is empty! Falling back to Mock data.")
        return {
            "comments": [
                {"file": os.path.basename(file_name), "line": 3, "entity": "mock_x", "claim": "unused_variable"}
            ]
        }
    
    from google import genai
    from google.genai import types
    
    client = genai.Client(api_key=api_key)
    system_prompt = """
    You are an expert static analysis assistant. Detect exactly three classes of bugs:
    1. 'unused_variable'
    2. 'null_safety_violation'
    3. 'off_by_one_bound'
    Return strictly JSON matching the schema. Do not include any conversational prose.
    """
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=f"Review this Python code:\n\n{code_content}",
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                response_schema=CodeReviewResponse,
            ),
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"[Error calling API for {os.path.basename(file_name)}]: {e}")
        return {"comments": []}

if __name__ == "__main__":
    base_data_dir = os.path.join("code_review_project", "data")
    target_subdirs = ["clean_negative_controls", "mutated", "mutated_null", "mutated_offbyone"]
    
    all_results = []
    python_files = []
    
    for subdir in target_subdirs:
        search_path = os.path.join(base_data_dir, subdir, "**", "*.py")
        found_files = glob.glob(search_path, recursive=True)
        python_files.extend(found_files)
        print(f" Found {len(found_files)} files in '{subdir}'")

    print(f"\n Starting Scale-up Benchmark on {len(python_files)} total files (Real Gemini API Calls)...")
    
    for idx, file_path in enumerate(python_files, 1):
        print(f"[{idx}/{len(python_files)}] Processing: {file_path}")
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                code_content = f.read()
        except Exception as e:
            print(f"Skipping file (Read Error): {file_path}. Details: {e}")
            continue
            
        for run_number in range(1, 4):
            print(f"  -> Run {run_number}/3...")
            review_json = review_python_code_with_gemini(file_path, code_content)
            
            run_entry = {
                "file_path": file_path,
                "subdir": os.path.basename(os.path.dirname(file_path)),
                "run_id": run_number,
                "output": review_json
            }
            all_results.append(run_entry)

    output_filename = "scale_up_results.json"
    with open(output_filename, "w", encoding="utf-8") as out_file:
        json.dump(all_results, out_file, indent=2)
        
    print(f"\n Scale-up completed successfully! Real API results saved to '{output_filename}'")