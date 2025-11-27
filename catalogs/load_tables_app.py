import os
import json
import textwrap
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv


load_dotenv()

PG_CONN = {
    "host": os.getenv("PGHOST", "localhost"),
    "port": int(os.getenv("PGPORT", "5434")),
    "dbname": os.getenv("PGDATABASE"),
    "user": os.getenv("PGUSER"),
    "password": os.getenv("PGPASSWORD"),
}


TABLES_TO_DOCUMENT = [
    ("public", "domains"),
    ("public", "domain_values"),
    ("public", "product_types"),
    ("public", "products"),
    ("public", "fee_tariff"),
]

def get_conn():
    return psycopg2.connect(**PG_CONN)

def fetch_columns(conn, schema, table):
    sql = """
    SELECT
        c.table_schema,
        c.table_name,
        c.column_name,
        c.ordinal_position,
        c.data_type,
        c.is_nullable,
        c.column_default
    FROM information_schema.columns c
    WHERE c.table_schema = %s AND c.table_name = %s
    ORDER BY c.ordinal_position;
    """
    with conn.cursor() as cur:
        cur.execute(sql, (schema, table))
        return cur.fetchall()

def friendly_description(schema, table, cols):
       
    pk_hint = "id"  # simple hint; improve by reading pg_catalog for real PKs if you like

    lines = []
    lines.append(f"Table: {schema}.{table}")
    lines.append("Columns:")

    for (_schema, _table, col, pos, dtype, nullable, default) in cols:
        req = "required" if nullable == "NO" else "optional"
        default_txt = f", default {default}" if default else ""
        lines.append(f"- {col} ({dtype}, {req}{default_txt})")

    return "\n".join(lines)


def upsert_catalog_rows(conn, rows):
    """
    rows: list of dicts with keys: schema_name, table_name, title, content
    """
    sql = """
    INSERT INTO setup.catalog_tables (schema_name, table_name, title, content)
    VALUES %s
    ON CONFLICT (schema_name, table_name)
    DO UPDATE SET
      title = EXCLUDED.title,
      content = EXCLUDED.content
    """
    
    values = [
        (
            r["schema_name"],
            r["table_name"],
            r["title"],
            r["content"]
        )
        for r in rows
    ]
    with conn.cursor() as cur:
        execute_values(cur, sql, values)
    conn.commit()

def main():
   

    with get_conn() as conn:
        rows_to_upsert = []
        contents = []
        meta = []

        for schema, table in TABLES_TO_DOCUMENT:
            cols = fetch_columns(conn, schema, table)
            content = friendly_description(schema, table, cols)
            contents.append(content)
            meta.append((schema, table, f"{schema}.{table}", content))

      
         # Build rows
        for (schema, table, title, content) in meta:
            rows_to_upsert.append({
                "schema_name": schema,
                "table_name": table,
                "title": title,
                "content": content  })

        upsert_catalog_rows(conn, rows_to_upsert)
        print(f"Upserted {len(rows_to_upsert)} rows into setup.catalog_tables.")

if __name__ == "__main__":
    main()
