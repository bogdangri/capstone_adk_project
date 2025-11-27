
import os
from dotenv import load_dotenv
from datetime import datetime, timezone



def get_local_timestamp_string() -> str:
  
    utc_dt = datetime.now(timezone.utc)
    local_dt = utc_dt.astimezone()

    # format as yyyymmddhhmmss
    return local_dt.strftime("%Y%m%d%H%M%S")

load_dotenv()

#APP_NAME = "db_setup_automation_project"

APP_NAME="agents"

PG_CONN = {
    "host": os.getenv("PGHOST", "localhost"),
    "port": int(os.getenv("PGPORT", "5434")),
    "dbname": os.getenv("PGDATABASE","adk_db"),
    "user": os.getenv("PGUSER","db_user"),
    "password": os.getenv("PGPASSWORD","db_password"),
}



GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-004")
DEFAULT_LLM_MODEL = os.getenv("LLM_MODEL", "gemini-2.5-flash-lite")

USER_ID = "pipeline_user"
SESSION_ID = "pipeline_session_{}".format(get_local_timestamp_string())

