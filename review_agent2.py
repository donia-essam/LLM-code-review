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
    You are a strictly accurate Python static analysis security agent. 
    Your ONLY task is to report REAL bugs that exist in the provided Python code for these 3 specific categories:
    1. 'unused_variable': Variables defined or assigned but NEVER referenced/used anywhere later in the scope.
    2. 'null_safety_violation': Calling methods, accessing attributes, or performing operations on variables that can be None/null without prior None checks.
    3. 'off_by_one_bound': Incorrect loop boundaries, index access errors like array[len(array)], or incorrect range limits.

    CRITICAL RULES:
    - IF THE CODE IS CLEAN OR HAS NO BUGS, RETURN AN EMPTY ARRAY: {"comments": []}.
    - Do NOT fabricate, guess, or invent bugs. If you are not 100% sure a bug exists, do NOT report it.
    - ENTITY FORMAT RULE: The 'entity' field MUST strictly be a single identifier ONLY (e.g., variable name, function name, or loop variable like 'i', 'temp_var', 'current'). NEVER include code expressions, mathematical operators, or function calls in the 'entity' field (e.g., write 'current' instead of 'range(len(current + 1))').

    Return strictly JSON matching this structure:
    {
      "comments": [
        {
          "file": "filename",
          "line": 10,
          "entity": "single_identifier_name",
          "claim": "unused_variable"
        }
      ]
    }
    Return ONLY valid JSON. No markdown backticks, no explanations.
    """
    
    try:
        response = client.chat.completions.create(
            model="deepseek-v4-pro",  
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Analyze this Python code from file '{os.path.basename(file_name)}':\n\n{code_content}"}
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
    
    target_subdirs = [
        "clean", 
        "clean_negative_controls", 
        "mutated", 
        "mutated_null", 
        "mutated_offbyone"
    ]
    
    all_results = []
    
    for subdir in target_subdirs:
        search_path = os.path.join(base_data_dir, subdir, "**", "*.py")
        found_files = glob.glob(search_path, recursive=True)
        
        selected_files = found_files[:36]  
        print(f" Found {len(found_files)} total files in '{subdir}' -> Selected {len(selected_files)} for Pro benchmark.")

        for idx, file_path in enumerate(selected_files, 1):
            print(f"[{subdir} - {idx}/{len(selected_files)}] Processing: {file_path}")
            
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    code_content = f.read()
            except Exception as e:
                print(f"Skipping file (Read Error): {file_path}. Details: {e}")
                continue
                
            for run_number in range(1, 2):
                review_json = review_python_code_with_llm(file_path, code_content)
                
                run_entry = {
                    "file_path": file_path,
                    "subdir": subdir,
                    "run_id": run_number,
                    "model": "deepseek-v4-pro",
                    "output": review_json
                }
                all_results.append(run_entry)

    output_filename = "scale_up_results_pro.json"
    with open(output_filename, "w", encoding="utf-8") as out_file:
        json.dump(all_results, out_file, indent=2)
        
    print(f"\n Benchmark for DeepSeek-Pro completed successfully! Results saved to '{output_filename}'")
    