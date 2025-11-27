import os
import json
import psycopg2
from psycopg2.extras import register_default_jsonb
import google.generativeai as genai
from dotenv import load_dotenv
from pathlib import Path
from utils.config import  PG_CONN, GOOGLE_API_KEY, EMBEDDING_MODEL


# --- SQL: reduced to only what we actually use ------------------------------

SQL_CONTEXT_QUERY = """
WITH
q AS (
  SELECT %s::vector AS emb
),
uc_raw AS (
  SELECT
    doc_id,
    title,
    request_text,
    solution_text,
    sql_info_json,
    tables_hint,
    1 - (embedding <=> (SELECT emb FROM q)) AS score
  FROM setup.catalog_use_cases
),
uc AS (
  SELECT *
  FROM uc_raw
  WHERE score >= 0.5              -- similarity threshold
  ORDER BY score DESC
  LIMIT 1                          -- top-K use-cases (1 for now)
),
hints AS (
  SELECT DISTINCT unnest(tables_hint) AS table_name
  FROM uc
  WHERE tables_hint IS NOT NULL
),
tbl AS (
  SELECT t.schema_name, t.table_name, t.title, t.content
  FROM setup.catalog_tables t
  JOIN hints h ON t.table_name = h.table_name
  WHERE t.schema_name = 'public'
)
SELECT jsonb_build_object(
  'request',
    jsonb_build_object(
      'request_id', %s::text,
      'subject'  , %s::text,
      'body_text', %s::text
    ),

  -- Flatten sql_info_json->'use_cases_sql'[0] and enrich with doc/meta info
  'use_cases_sql',
    COALESCE(
      (
        SELECT jsonb_agg(
                 (uc.sql_info_json->'use_cases_sql'->0)
                 || jsonb_build_object(
                      'doc_id',      uc.doc_id,
                      'doc_title',   uc.title,
                      'score',       round(uc.score::numeric, 4),
                      'tables_hint', uc.tables_hint,
                      'solution_instructions', uc.solution_text
                    )
               )
        FROM uc
      ),
      '[]'::jsonb
    ),

  'tables',
    COALESCE(
      (SELECT jsonb_agg(
         jsonb_build_object(
           'schema_name', schema_name,
           'table_name',  table_name,
           'title',       title,
           'content',     content
         )
         ORDER BY table_name
       )
       FROM tbl),
      '[]'::jsonb
    )
) AS context_bundle;
"""


# --- Embedding --------------------------------------------------------------

def embed_text(text: str) -> list[float]:
    """
    Create a single embedding vector from the input text
    """
    genai.configure(api_key=GOOGLE_API_KEY)

    response = genai.embed_content(
        model=EMBEDDING_MODEL,  
        content=text
    )

    if isinstance(response, dict):
        return response["embedding"]
    else:
        return response.embedding

# --- Get context_bundle from DB ---------------------------------------------

def get_context_bundle(
    search_text: str,
    request_id: str,
    subject: str,
    body_text: str,
) -> dict:
    """
    1. Embed search_text
    2. Run your SQL query with the embedding + request metadata
    3. Return the context_bundle as a Python dict
    """

    embedding = embed_text(search_text)
    conn = psycopg2.connect(**PG_CONN)

    register_default_jsonb(conn)

    try:
        with conn.cursor() as cur:
            cur.execute(
                SQL_CONTEXT_QUERY,
                (
                    embedding,          # %s -> %s::vector in SQL
                    request_id,         # %s (request_id)
                    subject,            # %s (subject)
                    body_text,          # %s (body_text)
                ),
            )
            row = cur.fetchone()
            if row is None:
                return {}

            context_bundle = row[0]

            if isinstance(context_bundle, str):
                return json.loads(context_bundle)
            return context_bundle

    finally:
        conn.close()


# --- Transform context_bundle -> dbquery ------------------------------------

def build_dbquery(context_bundle: dict, request: dict) -> dict:
    """
    Build the final dbquery structure:
      - request_id
      - tables_content: list of tables[*].content (full text; no truncation)
      - use_case_sql: first (top) entry from use_cases_sql
      - params: already-extracted params from input JSON
      - body_text: original content
    """
    if not context_bundle:
        return {
            "request_id": request.get("request_id", ""),
            "tables_content": [],
            "use_case_sql": None,
            "params": request.get("params", {}),
            "body_text": request.get("content", ""),
        }

    tables = context_bundle.get("tables", [])
    use_cases_sql = context_bundle.get("use_cases_sql", [])

    top_use_case_sql = use_cases_sql[0] if use_cases_sql else None

    tables_content = [t.get("content", "") for t in tables]

    return {
        "request_id": str(request.get("request_id", "")),
        "tables_content": tables_content,
        "use_case_sql": top_use_case_sql,
        "params": request.get("params", {}),
        "body_text": request.get("content", ""),
    }

