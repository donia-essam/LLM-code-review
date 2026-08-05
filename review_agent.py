import os
import json
import glob
from typing import List
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from openai import OpenAI

load_dotenv()
api_key = os.getenv("OPENCODE_API_KEY", "").strip()

class CodeReviewComment(BaseModel):
    file: str = Field(description="The name of the file being reviewed.")
    line: int = Field(description="The exact line number where the issue is found.")
    entity: str = Field(description="The name of the variable, function, or loop bound causing the issue.")
    claim: str = Field(description="The bug type. Must be exactly one of: 'unused_variable', 'null_safety_violation', or 'off_by_one_bound'")

class CodeReviewResponse(BaseModel):
    comments: List[CodeReviewComment]

def review_python_code_with_llm(file_name: str, code_content: str) -> dict:
    if not api_key:
        print("  Warning: OPENCODE_API_KEY is empty! Check your .env file.")
        return {"comments": []}
    
    client = OpenAI(
        base_url="https://opencode.ai/zen/go/v1",
        api_key=api_key
    )
    
    system_prompt = """
    You are an expert static analysis assistant. 
    Analyze the provided Python code and list ALL potential bugs or issues related to:
    1. 'unused_variable'
    2. 'null_safety_violation'
    3. 'off_by_one_bound'
    
    Return strictly JSON matching this structure:
    {
      "comments": [
        {
          "file": "filename",
          "line": 10,
          "entity": "variable_or_function_name",
          "claim": "unused_variable"
        }
      ]
    }
    Do not include any Markdown blocks, backticks, or conversational text. Return ONLY valid JSON.
    """
    
    try:
        response = client.chat.completions.create(
            model="deepseek-v4-flash",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Review this Python code from file '{os.path.basename(file_name)}':\n\n{code_content}"}
            ]
        )
        
        raw_text = response.choices[0].message.content.strip()
        
        if raw_text.startswith("```"):
            raw_text = raw_text.strip("`").replace("json", "", 1).strip()
            
        return json.loads(raw_text)
    except Exception as e:
        print(f"[Error calling OpenCode API for {os.path.basename(file_name)}]: {e}")
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


    python_files = python_files[:122]

    print(f"\n Starting Test Benchmark on {len(python_files)} files using OpenCode...")
    
    for idx, file_path in enumerate(python_files, 1):
        print(f"[{idx}/{len(python_files)}] Processing: {file_path}")
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                code_content = f.read()
        except Exception as e:
            print(f"Skipping file (Read Error): {file_path}. Details: {e}")
            continue
            
        for run_number in range(1, 2):
            print(f"   -> Run {run_number}...")
            review_json = review_python_code_with_llm(file_path, code_content)
            
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
        
    print(f"\n Test completed successfully! Results saved to '{output_filename}'")