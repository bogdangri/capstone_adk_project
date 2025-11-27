

from typing import Dict, Any
from decimal import Decimal
from datetime import date, datetime

import psycopg2
from psycopg2.extras import RealDictCursor

from google.adk.agents import LlmAgent
from google.adk.tools import ToolContext

from utils.config import  PG_CONN, DEFAULT_LLM_MODEL
from utils.helper_utils import clean_model_json



# =====================================================================
# 1) GENERIC DB TOOL: db_select
# =====================================================================

def db_query_select(sql: str, tool_context: ToolContext) -> Dict[str, Any]:
    print("[db_query_select] START " )
    stripped = sql.lstrip().lower()
    if not (stripped.startswith("select") or stripped.startswith("with")):
        result = {
            "sql": sql,
            "rows": [],
            "rowcount": 0,
            "error": "Only SELECT or WITH queries are allowed.",
        }
        print("[db_query_select] REJECTED (non-SELECT):", result)
        return result
    
    try:
        conn = psycopg2.connect(**PG_CONN)
        try:
            with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql)
                rows = [dict(r) for r in cur.fetchall()]
                result = {
                    "sql": sql,
                    "rows": rows,
                    "rowcount": len(rows),
                    "error": None,
                }
                print("[db_query_select] EXECUTED:", result)
                result=to_json_safe(result)
                return result
        finally:
            conn.close()
    except Exception as e:
        result = {
            "sql": sql,
            "rows": [],
            "rowcount": 0,
            "error": str(e),
        }
        print("[db_query_select] ERROR:", result)
        return result


def to_json_safe(obj):
    """Recursively convert psycopg/DB types into JSON-serializable ones."""
    if isinstance(obj, Decimal):
        # choose float or str; for money str is safer
        return  str(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, list):
        return [to_json_safe(x) for x in obj]
    if isinstance(obj, dict):
        return {k: to_json_safe(v) for k, v in obj.items()}
    return obj
# =====================================================================
# 2) SYSTEM PROMPT (GENERAL, USE-CASE-INDEPENDENT)
# =====================================================================

SQL_DISCOVERY_SYSTEM_PROMPT = """
You are a PostgreSQL SQL-Discovery Agent.

You receive a single JSON object called context_for_agents in the user message.

Your job is to:
- Understand the user request using the structured data in context_for_agents.
- Use the single use_case_sql entry that is already selected for you.
- Follow ONLY the procedural instructions contained inside that use_case_sql.execution_instructions.
- Construct SQL SELECT statements according to use_case_sql.sql_queries.
- Execute the SQL using tool  [db_query_select]. 
- Return a strict JSON result with the SQL you generated, the query outputs, and any errors.

-----------------------------------------
INPUT FORMAT (context_for_agents)
-----------------------------------------
The user message will be ONE JSON object like:

{
  "request_id": "<string>",
  "tables_content": [
    "Table: public.fee_tariff\\nColumns:\\n- id (integer, required)\\n..."
    // one string per relevant table, including schema, name and columns
  ],
  "use_case_sql": {
    "id": "<use-case identifier>",
    "title": "<description>",
    "target_table": "<schema.table>",
    "schema": "<schema_name>",
    "pk": "<primary_key_column>",
    "select_columns": ["<col1>", "<col2>", ...],
    "where_template": "fee_id = %(v_fee_id)s AND currency = %(v_currency)s",
    "sql_queries": {
      "<query_name>": "SQL template that may refer to placeholders like <<target_table>>, <<where>>, <<columns>>, <<pk>>"
    },
    "execution_instructions": "Text describing which SQL templates to use, in what order, and how to interpret results.",
    "solution_instructions": "Text with additional solution instructions (for another agent; ignore this)."
  },
  "params": { "<param_name>": <value>, ... },
  "body_text": "<original free-text request>"
}

Notes:
- params contains values already extracted from the user request,
- tables_content gives you natural-language descriptions of the allowed tables.
  You MUST NOT invent table names or columns beyond what appears there or in use_case_sql.
- There is exactly ONE use_case_sql object. You do NOT have to choose between multiple use cases.

-----------------------------------------
WHAT TO DO (DETAILED)
-----------------------------------------

1) Understand the request
   - Use body_text and params to understand what is being asked.
   - The logical behavior is fully defined by use_case_sql.execution_instructions.
   - DO NOT invent new logic.

2) Understand the target table
   - use_case_sql.target_table is the schema-qualified table name you must use.
   - use_case_sql.select_columns is the exact set of columns you are allowed to SELECT in select_rows.
   - use_case_sql.pk is the name of the primary key column (used in max_pk_plus_1).

3) Build the WHERE clause
   - Start from use_case_sql.where_template, for example:
       "fee_id = %(v_fee_id)s AND currency = %(v_currency)s"
   - For each placeholder of the form %(v_xxx)s:
       - Look up params["v_xxx"].
       - If the value is numeric (int/float), insert it without quotes.
         Example: 136 -> "136"
       - If the value is a string, wrap it in single quotes.
         Example: "ROL" -> "'ROL'".
   - The final WHERE clause must be a valid SQL expression, e.g.
       "fee_id = 136 AND currency = 'ROL'".

4) Build the SQL from templates
   - use_case_sql.sql_queries is a dict like:
       {
         "count_rows": "SELECT COUNT(*) AS v_count_rows FROM <<target_table>> WHERE <<where>>;",
         "select_rows": "SELECT <<columns>> FROM <<target_table>> WHERE <<where>>;",
         "max_pk_plus_1": "SELECT max(<<pk>>)+1 AS max_pk_plus_1 FROM <<target_table>>;"
       }
   - For each query:
       - Replace <<target_table>> with use_case_sql.target_table.
       - Replace <<where>> with the WHERE clause you built.
       - Replace <<columns>> with a comma-separated list of select_columns.
       - Replace <<pk>> with use_case_sql.pk.
   - Never invent new fields or placeholders.

5) Execute queries with tool [db_query_select] 
   Always follow use_case_sql.execution_instructions.

6) Build the final result JSON
   - Your final output MUST be a single JSON object of the form:

     {
       "request_id": "<copy of context_for_agents.request_id>",
       "table": "<copy of use_case_sql.target_table>",
       "selects": {
         "<query_name>": "<final SQL string>",
         ...
       },
       "result": {
         "table_name": "<use_case_sql.target_table>",
         "v_count_rows": <number or 0>,
         "rows": [ { "<col>": <value>, ... } ],          // rows from select_rows, or [] if not executed
         "max_pk_plus_1": <number or null>
       },
       "errors": [
         { "query_name": "<name>", "sql": "<sql>", "error": "<message>" }
       ]
     }


7) Quoting rules in JSON
   - When writing SQL inside JSON strings, do NOT escape single quotes as \'.
     Use plain single quotes inside the JSON string (e.g. "currency = 'ROL'").
   - The JSON itself must be valid:
     - double quotes for JSON keys and string values,
     - no trailing commas,
     - no comments.

-----------------------------------------
STRICTNESS RULES
-----------------------------------------
- Do NOT invent logic. Follow only use_case_sql.execution_instructions.
- Do NOT invent column names, table names, or SQL syntax not provided by:
    - tables_content
    - use_case_sql fields
- Only run read-only SELECT statements using [db_query_select]. 
- You ALWAYS MUST USE TOOL db_query_select otherwise return a message 
- If an SQL cannot be generated due to missing parameters or misaligned templates,
  include an entry in errors[] and set result to a best-effort partial object.
- Do NOT wrap the JSON in ```json or ``` fences.
- Do NOT include any extra text before or after the JSON.
- Output must be valid JSON only. No markdown, no explanations.
"""


# =====================================================================
# 5) Build SQL-Discovery Agent factory
# # ===================================================================

def build_sql_info_agent(
    model_name: str = DEFAULT_LLM_MODEL,
    output_key: str = "sql_probe",
) -> LlmAgent:
      return LlmAgent(
        name="sql_discovery_agent",
        model=model_name,
        instruction=SQL_DISCOVERY_SYSTEM_PROMPT,
        output_key=output_key,  
        tools=[db_query_select],
       
    )

