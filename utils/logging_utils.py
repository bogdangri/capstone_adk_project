import json
from typing import Any, Dict, List

import psycopg2
from psycopg2.extras import Json
from datetime import datetime, timezone
from utils.config import APP_NAME, PG_CONN
from google.adk.events import Event

def date_to_local_iso(ts):
    if isinstance(ts, (int, float)):
      
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    elif hasattr(ts, "isoformat"):
        dt = ts
      
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    else:
        return str(ts)
   
    return dt.astimezone().isoformat()


def extract_llm_interactions(events: List[Event]) -> List[Dict[str, Any]]:
    llm_logs = []

    for event in events:
        # Determine "prompt" vs "response"
        author = getattr(event, "author", None)

        # Parse parts
        content = getattr(event, "content", None)

        if content is not None:
           
            raw_parts = getattr(content, "parts", None)

            if isinstance(raw_parts, list):
                parts = raw_parts
            elif raw_parts is None:
                parts = []
            else:
             
                parts = [raw_parts]

    
        # Split into prompt-like vs response-like for compatibility
        if author == "user":
            prompt_contents = [{"role": "user", "text": getattr(p, "text", None)} for p in parts]
            response_contents = []
        else:
            prompt_contents = []
            response_contents = [{"role": "model", "text": getattr(p, "text", None)} for p in parts]

        log_entry = {
            "timestamp": date_to_local_iso(event.timestamp),
            "agent_name": getattr(event, "agent_name", None),
            "model_name": getattr(event, "model_name", None),

            "prompt_contents": prompt_contents,
            "response_contents": response_contents  
       }

      
        llm_logs.append(log_entry)

    return llm_logs


def log_agent_events(session_id: str, agent_name:str, log_data: List[Dict[str, Any]]):
    
   
    if not log_data:
       
        return
    
    try:
       
        conn = psycopg2.connect(**PG_CONN)
        cur = conn.cursor()
        
        insert_query = """
            INSERT INTO logs.agent_llm_logs (session_id, app_name, agent_name, log_data) 
            VALUES (%s, %s, %s, %s);
        """
        cur.execute(
            insert_query,
            (session_id, APP_NAME, agent_name, Json(log_data))  # Json(...) handles dict/list -> JSONB
        )
        
        conn.commit()
        cur.close()
        #print(f" Successfully logged {len(log_data)} LLM interactions for session: {session_id}")
        
    except (Exception, psycopg2.Error) as error:
        print(f" log_agent_events :  Error while connecting to PostgreSQL or inserting data: {error}")
    finally:
        if conn is not None:
            conn.close()


def log_pipeline_event( request_id: str, pipeline_name: str, stage: str, data: dict) -> None:

    conn = psycopg2.connect(**PG_CONN)

    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO logs.db_pipeline_logs
                (request_id, app_name, pipeline_name, stage, log_data)
                VALUES (%s, %s, %s, %s,  %s::jsonb)
            """,
            (
                request_id,
                APP_NAME,
                pipeline_name,
                stage,
                json.dumps(data)
            ))
            conn.commit()
            cur.close()
    except (Exception, psycopg2.Error) as error:
        print(f" log_pipeline_event : Error while connecting to PostgreSQL or inserting data: {error}")
    finally:
        if conn is not None:
            conn.close()
