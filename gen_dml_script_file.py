import os
from datetime import datetime

# ----------------------------------------------------------------------
# Helper functions
# ----------------------------------------------------------------------

def esc(s: str) -> str:
    """Escape single quotes for SQL string literals."""
    return str(s or "").replace("'", "''")


def to_sql_literal(v):
    """
    Render a Python value as a SQL literal:
    - Keeps NULL, CURRENT_DATE, CURRENT_TIMESTAMP, NOW(),INTEGER,NUMERIC,FLOAT bare
    """
    if v is None:
        return "NULL"

    t = str(v).strip()
    tu = t.upper()

    if tu in ("NULL", "CURRENT_DATE", "CURRENT_TIMESTAMP", "NOW()","NUMERIC","INTEGER","FLOAT"):
        return t  # no quoting

    return f"'{esc(t)}'"


def build_where(keys: dict) -> str:
    """Convert a dict of key/value into SQL WHERE conditions."""
    if not keys:
        return "1=0"
    return " AND ".join(f"{k}={to_sql_literal(v)}" for k, v in keys.items())


# ----------------------------------------------------------------------
# Main renderer
# ----------------------------------------------------------------------

def generate_sql(plan: dict) -> str:
    request_id = str(plan.get("request_id", "unknown"))
    #scope_text = plan.get("scope") or plan.get("Scope") or plan.get("context") or "N/A"
    scope_text = str(plan.get("title", "N/A"))
    user_text = "automation_agent"
    started_at = datetime.utcnow().isoformat()

    border = "*" * 100
    top_line = f"/* {border}"
    bottom_line = f"{border} */"

    header_comment = (
        f"{top_line}\n"
        f" * Request: {esc(request_id)}\n"
        f" * Scope  : {esc(scope_text)}\n"
        f" * User   : {esc(user_text)}\n"
        f" * Start  : {esc(started_at)}\n"
        f" {bottom_line}"
    )

    # ---- Body of DO block ----
    body = f"""
-- Generated as a PostgreSQL PL/pgSQL DO-block
DECLARE
  v_request_id text := '{esc(request_id)}';
  v_started_at timestamptz := now();
  v_rows int;
  v_err_text text;
  v_err_state text;
BEGIN
  RAISE NOTICE 'Request % started at %', v_request_id, v_started_at;
"""

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    for act in plan.get("actions", []):
        table = act["target_table"]
        action = act.get("action", "").lower()
        keys = act.get("keys", {})
        reason = str(act.get("reason", ""))
        fields = dict(act.get("fields", {}))

        # remove fields not needed
        fields.pop("data_in", None)
        fields.pop("data_out", None)

        if action == "insert":
            insert_fields = {**fields, "data_in": "CURRENT_DATE", "data_out": "NULL"}
            cols = list(insert_fields.keys())
            vals = [to_sql_literal(insert_fields[c]) for c in cols]

            body += f"""
               /* {esc(reason)} */
                 INSERT INTO {table} ({", ".join(cols)})
                 VALUES ({", ".join(vals)});
                 GET DIAGNOSTICS v_rows = ROW_COUNT;
                 RAISE NOTICE 'Inserted % row(s) into %', v_rows, '{esc(table)}';
            """

        elif action == "update":
            set_parts = [f"{k}={to_sql_literal(v)}" for k, v in fields.items()]
            if not set_parts:
                raise ValueError(f"Nothing to update for table {table}")

            where = build_where(keys)

            body += f"""
                   /* {esc(reason)} */
                   UPDATE {table} SET {", ".join(set_parts)} WHERE {where};
                   GET DIAGNOSTICS v_rows = ROW_COUNT;
                   RAISE NOTICE 'Updated % row(s) in %', v_rows, '{esc(table)}';
            """

        elif action == "expire_and_insert":
            where = build_where(keys)
            insert_fields = {**fields, "data_in": "CURRENT_DATE", "data_out": "NULL"}
            cols = list(insert_fields.keys())
            vals = [to_sql_literal(insert_fields[c]) for c in cols]

            body += f"""
  /* {esc(reason)} */
  -- 1) expire current row(s)
  UPDATE {table}
     SET data_out = CURRENT_DATE
   WHERE {where}
     AND data_out IS NULL;
  GET DIAGNOSTICS v_rows = ROW_COUNT;
  RAISE NOTICE 'Expired % row(s) in % for keys [{esc(where)}]', v_rows, '{esc(table)}';

  IF v_rows = 0 THEN
    RAISE EXCEPTION 'No active row to expire in % for keys [%]', '{esc(table)}', '{esc(where)}'
      USING ERRCODE = 'no_data_found';
  END IF;

  -- 2) insert new version
  INSERT INTO {table} ({", ".join(cols)}) VALUES ({", ".join(vals)});
  GET DIAGNOSTICS v_rows = ROW_COUNT;
  RAISE NOTICE 'Inserted % row(s) into %', v_rows, '{esc(table)}';
"""

        else:
            body += f"""
  -- TODO unsupported action: {esc(action)} on {esc(table)}
"""

    # ------------------------------------------------------------------
    # Close block
    # ------------------------------------------------------------------
    body += """
  RAISE NOTICE 'Request % completed successfully', v_request_id;

EXCEPTION
  WHEN OTHERS THEN
    GET STACKED DIAGNOSTICS
      v_err_text  = MESSAGE_TEXT,
      v_err_state = RETURNED_SQLSTATE;
    RAISE NOTICE 'Request % failed: % (SQLSTATE=%)', v_request_id, v_err_text, v_err_state;
    RAISE;
END;
"""

    # Final SQL text
    sql = f"DO $$\n{header_comment}\n{body}\n$$ LANGUAGE plpgsql;\n"
    return sql


# ----------------------------------------------------------------------
# Write file
# ----------------------------------------------------------------------

def write_sql_script(plan: dict, folder="db_setup_automation_project"):
    
    
    request_id = str(plan.get("request_id", "unknown"))
    filename = f"req-{request_id}.sql"
    full_path = os.path.join(folder, filename)

    sql = generate_sql(plan)

    with open(full_path, "w", encoding="utf-8") as f:
        f.write(sql)

        print(f" SQL script saved to: {full_path}")

    return {"request_id": request_id, "filename": filename, "path": full_path, "fileContent": sql}



