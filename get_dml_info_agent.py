
from dotenv import load_dotenv

from utils.config import  DEFAULT_LLM_MODEL

from google.adk.agents import LlmAgent


DML_PLANNER_SYSTEM_PROMPT = """
You are a precise data-change planner for a PostgreSQL database.

INPUT YOU WILL RECEIVE (single JSON object named context_bundle):
{
  "request": {"request_id":"<string|null>","subject":"<string|null>","normalized":"<string>", "language":"<string|null>"},
  "use_cases": [ { "title","solution_instruction","tables_hint","score","unique_condition" } ... ],
  "tables":    [ { "schema_name","table_name","title","content" } ... ],
  "sql_probe": {
    "table_name":"<string|null>",
    "count_rows": <number|null>,
    "rows": [ { "<col>": "<value>", ... } ... ],
    "max_pk_plus_1": "<string|null>"
  }
}

WHAT TO DO:
1) Read request.normalized to understand the business ask.
2) Use use_cases[*].solution_instructions as procedural guidance (branching rules).
3) Use tables[*].content (natural-language docs) to map keys and fields (no invented columns).
4) Use sql_probe to decide for table mentioned in table_name existence of rows (count_rows/rows) and next PK (max_pk_plus_1). 

  
OPERATE ONLY ON THESE TABLES:
- Only the tables listed in context_bundle.tables[].table_name. Do not use any table not listed there.

OUTPUT (STRICT JSON, no prose, no code fences):
{
  "request_id": "<copy request.request_id or null>",
  "subject":"<copy request.subject or null>",
  "actions": [
    {
      "target_table": "<schema-qualified table name from tables[].table_name>",
      "action": "insert" | "update" | "expire_and_insert",
      "keys":   { "<col>": "<string>", ... },
      "fields": { "<col>": "<string|null>", ... },
      "reason": "<short explanation>",
      "pk_key": "<primary key column name>",
      "history": "0" | "1",
      "history_columns": "<comma-separated list or empty string>"
    }
  ]
}

PLANNING RULES:
- Use only tables listed in the tables[] input.
- Use only columns documented in tables[].content.
- Versioning → expire_and_insert.
- No versioning + row exists → update.
- No versioning + no row → insert.
- Use sql_probe.max_pk_plus_1 for numeric PK if available.
- If info insufficient: return { "request_id": "...", "actions": [] }.

STRICTNESS:
- All values in "keys" and "fields" must be strings, numeric, or null.
- For numeric columns (integer, bigint, smallint, numeric, real, double precision) you MUST output JSON numbers, 
  not quoted strings. Example: "id": 4 not "id": "4".
- Return valid JSON only.
"""
# =====================================================================
  
# ----------------------------------------------------------
# Transform your manual JSON → context_bundle for planner
# ----------------------------------------------------------
def convert_input_to_context_bundle(data: dict) -> dict:

    # ----- REQUEST -----
    request = {
        "request_id": data.get("request_id"),
        "subject": data.get("use_case_sql", {}).get("title"),
        "normalized": data.get("body_text", ""),
        "language": None,
    }

    # ----- TABLES -----
    # tables_content[] = array of natural-language descriptions
    tables = []
    for entry in data.get("tables_content", []):
        tables.append({
            "schema_name": data["use_case_sql"]["schema"],
            "table_name": data["use_case_sql"]["target_table"],
            "title": data["use_case_sql"]["title"],
            "content": entry
        })

    # ----- USE CASES -----
    uc = data.get("use_case_sql", {})
    use_cases = [{
        "title": uc.get("title"),
        "solution_text": uc.get("solution_instructions"),
        "tables_hint": uc.get("tables_hint", []),
        "score": uc.get("score"),
        "unique_condition": uc.get("where_template")
    }]

    # ----- SQL PROBE -----
    res = data.get("result", {})
    sql_probe = {
        "table_name": res.get("table_name"),
        "count_rows": res.get("v_count_rows"),
        "rows": [],  # no row details available
        "max_pk_plus_1": res.get("max_pk_plus_1"),
    }

    # ----- FINAL BUNDLE -----
    context_bundle = {
        "request": request,
        "use_cases": use_cases,
        "tables": tables,
        "sql_probe": sql_probe
    }

    return context_bundle


# =====================================================================
# 5) Build DML-Planner Agent factory
# # ===================================================================


def build_dml_planner_agent(
    model_name: str = DEFAULT_LLM_MODEL,
    output_key: str = "plan",
) -> LlmAgent:
    """
    Factory for the DML planner agent.
    """
    return LlmAgent(
        name="dml_info_agent",
        model=model_name,
        instruction=DML_PLANNER_SYSTEM_PROMPT,
        output_key=output_key,
    )  






