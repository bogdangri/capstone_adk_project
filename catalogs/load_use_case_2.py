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
        "title": "Update fee tariff",
        "locale": "EN",
        "request_text": (
            "Update fee tarif fee_id =<v_fee_id> , currency = <v_currency> \n"
            " with new percent  <percent_value> / new fixed value  <fix_value>.\n "
        ),
        "solution_text": (
            "Check sql_probe for table public.fee_tariff for parameters \n"
            "    count_rows : number of rows satisfied conditions   \n"
            "    rows[] : atributes of the rows satisfied conditions \n"
            "    next_id: maximum primary key , max_pk_plus_1  \n"
            "If count_rows==1 operation=expire and insert"
            "  UPDATE target_table set date_out = trunc(sysdate)  where id = sql_probe.rows[0].id  \n "
            "If request is reffering to procent then \n"
            "  INSERT new row with id=<max_pk_plus_1>, fee_id=<v_fee_id>, currency=<valuta>, \n "
            "  tariff_percent=<percent_value>, tariff_amount...s[0].max_amount, creation_date=CURRENT_DATE, created_by=1111.\n"
            "Else if request is reffering to fixed value then \n"
            "  INSERT new row with id=mnext_id, fee_id=<fee_id>, currency=<valuta>, \n "
            "  tariff_percent=0, tariff_amount=<fix_value>, ...s[0].max_amount, creation_date=CURRENT_DATE, created_by=1111.\n"
            "If count_rows is a value grater than 1 no action is performed \n"
        ),
        "sql_info_json": {
            "use_cases_sql": [
                {
                    "id": "fee_tariff_update_001",
                    "title": "Update fee tariff",
                    "target_table": "public.fee_tariff",
                    "schema": "public",
                    "pk": "id",
                    "select_columns": [
                        "id",
                        "fee_id",
                        "currency",
                        "min_amount",
                        "max_amount"
                    ],
                    "where_template": "fee_id = %(v_fee_id)s AND currency = %(v_currency)s",
                    "sql_queries": {
                        "count_rows": "SELECT COUNT(*) AS v_count_rows FROM <<target_table>> WHERE <<where>>;",
                        "select_rows": "SELECT <<columns>> FROM target_table>> WHERE <<where>>;",
                        "max_pk_plus_1": "SELECT max(<<pk>>)+1 AS max_pk_plus_1 FROM <<target_table>>;"
                    },
                    "execution_instructions": (
                        "Substitute <<target_table>>, <<columns>>, and <<where>>, <<pk>> using the datinformation you get "
                        "1) Always run the 'count_rows' query using the sql_queries['count_rows'] template. "
                        "2) If the result of count_rows (v_count_rows) is exactly 1:"
                        "    run the 'select_rows' query using sql_queries['select_rows']. "
                        "3) Always run 'max_pk_plus_1' query using sql_queries['max_pk_plus_1'] to get the next primary key."
                    )
                }
            ]
        },
        "tables_hint": ["fee_tariff"],
    },
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
