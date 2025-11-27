import os
import json
import re
from pathlib import Path
from dotenv import load_dotenv

import google.generativeai as genai

from utils.config import  DEFAULT_LLM_MODEL

load_dotenv()


# We now use GOOGLE_API_KEY instead of OPENAI_API_KEY
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")


# --------- LLM AGENT CONFIG --------- #

DESCRIPTION = (
    "You are an information normalizer for structured business requests "
    "written in natural language."
)

INSTRUCTIONS = """

INPUT
You receive a single JSON object as text. It has exactly these fields:
- request_id
- title
- content

The value of "content" is a free-text request (body text) that may contain key-value pairs.

YOUR TASK
From this input you must produce ONE JSON object with exactly these keys:
- "request_id"  (same value as in the input)
- "normalized"  (a normalized version of the content)
- "params"      (an array of values in order of appearance)

DETECTING KEY - VALUE PAIRS
- Detect pairs of the form:  lhs = rhs  or  lhs : rhs
- They may appear:
  - inline,
  - on bullet lines starting with "-",
  - separated by commas or semicolons.

PROCESS THE LEFT-HAND SIDE (lhs)
- Remove leading and trailing quotes ' and " from lhs.
- Trim leading and trailing spaces.
- Replace any remaining spaces with "_".
- Convert to lowercase.
- This produces lhs_sanitized.
- Example:  - "Fixed value" = 20   → lhs_sanitized = fixed_value

PLACEHOLDERS IN "normalized"
- In the "normalized" field, keep the original text structure from "content".
- For every detected key–value pair:
  - Keep the original lhs and delimiters (=, :, commas, bullets, etc.).
  - Replace only the RHS (rhs) with a placeholder.
- The placeholder format is:  <v_<lhs_sanitized>>
  - Example:  fixed_value = 20   becomes   fixed_value = <v_fixed_value>
- If there is a value without a valid lhs, use:
  - <v_arg1>, <v_arg2>, <v_arg3>, ... in order of appearance.

EXTRACTING "params"
- "params" is an array of RHS values in the exact order they appear in the text.
- Extract the raw RHS value before replacing it with a placeholder.
- Remove surrounding quotes and extra punctuation.
- Convert values as follows:
  - Plain numbers: "20" → 20
  - Percentages: "12%" → 0.12 (divide by 100)
  - Numbers with currency or units: "20 ROL" → 20
- Keep the JavaScript / JSON types:
  - numbers as numbers
  - strings as strings

EDGE CASES
- If no subject or body is present, use an empty string "" for "normalized".
- If no key-value pairs exist, "params" should be an empty array [] and "normalized" can equal the original "content".

OUTPUT FORMAT
- Return ONLY a single JSON object with this exact structure:
  {
    "request_id": "<same as input>",
    "normalized": "<normalized_content>",
    "params": [ <values in appearance order> ]
  }
- Do NOT add explanations, comments, or extra fields.
- Do NOT wrap the JSON in backticks or markdown.
""".strip()



# --------- HELPER FUNCTIONS --------- #



def clean_text(value: str) -> str:
    """
    Remove unwanted special characters from a string:
    - double quotes "
    - single quotes '
    - newline characters \n
    """
    if not isinstance(value, str):
        return value

    return (
        value.replace('"', '')
             .replace("'", '')
             .replace("\n", ' ')
             .strip()
    )

def build_params_dict(normalized_text: str, params_list: list) -> dict:
    """
    Build a dict of placeholder_name -> value from:
    - normalized_text (containing <v_...> placeholders)
    - params_list (values in order of appearance)

    """
    if not isinstance(normalized_text, str):
        return {}

    # Extract placeholder names in order of appearance: v_currency, v_arg1, etc.
    placeholders = [m.group(1) for m in re.finditer(r"<(v_[^>]+)>", normalized_text)]

    params_dict = {}
    for name, value in zip(placeholders, params_list):
        # If same placeholder appears multiple times, last value wins (usually same value anyway)
        params_dict[name] = value

    return params_dict

def load_request_json(file_name: str) -> dict:
    """
    Read JSON from Data_files/<file_name> and return it as a dict.
    """
    base_dir = Path(__file__).resolve().parent
    file_path = base_dir / "Data_files" / file_name

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data


def normalize_input_shape(raw: dict) -> dict:
    """
    Make sure the object we send to the LLM has exactly:
    - request_id
    - title
    - content (string)
   
    """
    request_id = raw.get("request_id", "")
    title = raw.get("title", "")

    content = raw.get("content","")
    
    return {
        "request_id": request_id,
        "title": title,
        "content": content,
    }


def build_model() -> genai.GenerativeModel:
    """
    Configure the Gemini client and build the model with system instructions.
    """
    api_key = GOOGLE_API_KEY
    genai.configure(api_key=api_key)

    model = genai.GenerativeModel(
        model_name=DEFAULT_LLM_MODEL,
        system_instruction=f"{DESCRIPTION}\n\n{INSTRUCTIONS}",
    )
    return model


def call_normalizer(model: genai.GenerativeModel, request_obj: dict) -> dict:
    """
    Send the request object to the LLM and parse its JSON response.
    The agent is expected to return a JSON object as plain text.
    """
    # We send the JSON string as the content
    prompt = json.dumps(request_obj, ensure_ascii=False)

    response = model.generate_content(prompt)
    raw_text = (response.text or "").strip()

    # Expecting valid JSON as per the instructions
    normalized_result = json.loads(raw_text)
    return normalized_result



def normalize_request_file(file_name: str) -> dict:
    # read JSON, clean text, build final_output dict
   
    # 1. Load JSON file
    raw_data = load_request_json(file_name)

    print("=== Raw file content ===")
    print(json.dumps(raw_data, indent=2, ensure_ascii=False))
    print()

    # 2. Normalize the shape of the input for the agent
    request_for_llm = normalize_input_shape(raw_data)

    print("=== Request sent to LLM ===")
    print(json.dumps(request_for_llm, indent=2, ensure_ascii=False))
    print()

    # 3. Build the LLM agent
    model = build_model()

    # 4. Call the agent
    normalized_output = call_normalizer(model, request_for_llm)
    print(normalized_output)

        # 5. Build params dict from normalized text + params list
    raw_normalized = normalized_output.get("normalized", "")
    params_list = normalized_output.get("params", [])
    params_dict = build_params_dict(raw_normalized, params_list)

    # 6. Build final normalized field (title + cleaned normalized body)
    cleaned_normalized = clean_text(raw_normalized)
    title_clean = clean_text(request_for_llm.get("title", ""))

    final_normalized = f"title:{title_clean} request_text:{cleaned_normalized}"

    # 7. Build final output JSON:
    #    - all fields from request_for_llm
    #    - plus normalized (our combined field)
    #    - plus params as a dict
    final_output = {
        "request_id": request_for_llm["request_id"],
        "title": request_for_llm["title"],
        "content": request_for_llm["content"],
        "normalized": final_normalized,
        "params": params_dict,
    }
    
    return final_output
    
