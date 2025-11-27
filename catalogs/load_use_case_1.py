import os
import json
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

import google.generativeai as genai

load_dotenv()

PG_CONN = {
    "host": os.getenv("PGHOST", "localhost"),
    "port": int(os.getenv("PGPORT", "5434")),
    "dbname": os.getenv("PGDATABASE"),
    "user": os.getenv("PGUSER"),
    "password": os.getenv("PGPASSWORD"),
}


GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")


EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-004")


USE_CASES = [
    {
    "title": "Create or update domain code CODE_SIND",
    "locale": "EN",

    "request_text": (
        "Please create or update a domain code of type CODE_SIND.\n"
        "Input parameters:\n"
        "  COD_SIND = <v_code_sind>\n"
        "  Meaning  = <v_meaning>\n"
    ),

    "solution_text": (
        "Use SQL probe result for table public.domain_values.\n"
        "Inspect:\n"
        "  - count_rows  : number of records satisfying dmn_id=4 AND value=<v_code_sind>.\n"
        "  - rows[]      : retrieved rows\n"
        "  - next_id     : max_pk_plus_1\n\n"

        "If count_rows == 1, action = expire_and_insert:\n"
        "  UPDATE public.domain_values\n"
        "     SET date_out = CURRENT_DATE\n"
        "   WHERE id = sql_probe.rows[0].id;\n\n"

        "  INSERT new row with:\n"
        "       id = next_id,\n"
        "       dmn_id = 4,   -- fixed for CODE_SIND\n"  
        "       value = <v_code_sind>,\n"
        "       meaning = <v_meaning>,\n"
        "       date_in = CURRENT_DATE,\n"
        "       date_out = NULL,\n"
        "       creation_date = CURRENT_DATE,\n"
        "       created_by = 1111.\n\n"

        "If count_rows == 0, action = insert:\n"
        "  INSERT same structure as above using next_id.\n\n"

        "If count_rows > 1, no action is performed because the catalog contains duplicate active values."
    ),

    "sql_info_json": {
        "use_cases_sql": [
            {
                "id": "code_sind_upsert_001",
                "title": "Create or update CODE_SIND value",
                "target_table": "public.domain_values",
                "schema": "public",
                "pk": "id",

                "select_columns": [
                    "id",
                    "dmn_id",
                    "value",
                    "meaning",
                    "date_in",
                    "date_out"
                ],

                "where_template": (
                    "dmn_id = 4 AND value = %(v_code_sind)s"
                ),

                "sql_queries": {
                    "count_rows":
                        "SELECT COUNT(*) AS v_count_rows "
                        "FROM {target_table} "
                        "WHERE {where};",

                    "select_rows":
                        "SELECT {columns} "
                        "FROM {target_table} "
                        "WHERE {where};",

                    "max_pk_plus_1":
                        "SELECT max({pk})+1 AS max_pk_plus_1 "
                        "FROM {target_table};"
                },

                "execution_instructions": (
                    "1. Build WHERE clause from where_template using request parameters.\n"
                    "2. Execute count_rows.\n"
                    "3. If v_count_rows = 1 → call select_rows.\n"
                    "4. Always call max_pk_plus_1 to obtain next_id."
                )
            }
        ]
    },

    "tables_hint": ["public.domain_values"]
}
]


def get_conn():
    return psycopg2.connect(**PG_CONN)


def build_text_for_embedding(uc: dict) -> str:
    """
    Embed lowercase title + lowercase request_text.
    """
    title = uc.get("title", "").lower()
    request = uc.get("request_text", "").lower()
    return f"subject: {title} body_text: {request}".strip()


def embed_texts(texts):
 
    genai.configure(api_key=GOOGLE_API_KEY)

    vectors = []

    for t in texts:
        response = genai.embed_content(
            model=EMBEDDING_MODEL,  
            content=t
        )
        vectors.append(response['embedding'])

    return vectors


def upsert_use_cases(conn, rows):
    """
    rows: list of tuples:
      (locale, title, request_text, solution_text, tables_hint, sql_info_json, embedding_vector)
    """
    sql = """
    INSERT INTO setup.catalog_use_cases
      (locale, title, request_text, solution_text, tables_hint, sql_info_json, embedding)
    VALUES %s
    ON CONFLICT (title)
    DO UPDATE SET
      locale        = EXCLUDED.locale,
      request_text  = EXCLUDED.request_text,
      solution_text = EXCLUDED.solution_text,
      tables_hint   = EXCLUDED.tables_hint,
      sql_info_json = EXCLUDED.sql_info_json,
      embedding     = EXCLUDED.embedding;
    """
    with conn.cursor() as cur:
        execute_values(cur, sql, rows)
    conn.commit()


def main():

    if not GOOGLE_API_KEY:
        raise RuntimeError("GOOGLE_API_KEY is not set")
    # 1) Build the texts to embed (lower(title) + lower(request_text))
    texts = [build_text_for_embedding(uc) for uc in USE_CASES]

    # 2) Get embeddings from Google
    vectors = embed_texts(texts)

    # 3) Prepare rows for UPSERT
    rows = []
    for uc, vec in zip(USE_CASES, vectors):
        # Convert embedding list to pgvector literal, e.g. "[0.1,0.2,...]"
        embedding_vector = "[" + ",".join(str(x) for x in vec) + "]"
        rows.append((
            uc["locale"],
            uc["title"],
            uc["request_text"],
            uc["solution_text"],
            uc.get("tables_hint"),
            json.dumps(uc["sql_info_json"]),
            embedding_vector,
        ))

    # 4) UPSERT
    with get_conn() as conn:
        upsert_use_cases(conn, rows)

    print(f"Upserted {len(rows)} use-case(s) into setup.catalog_use_cases.")


if __name__ == "__main__":
    main()
