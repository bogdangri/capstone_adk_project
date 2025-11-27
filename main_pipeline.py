import asyncio
import json
from pathlib import Path


# 1) Your own modules
import normalize_request
from get_info_use_case import get_context_bundle  # from uploaded file :contentReference[oaicite:1]{index=1}
import gen_dml_script_file
from utils.helper_utils import clean_model_json
from utils.config import APP_NAME,USER_ID, SESSION_ID
from utils.logging_utils import log_pipeline_event, log_agent_events, extract_llm_interactions
from sequential_adk_agent import build_adk_agents


# 2) ADK imports
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types

pipeline_name = "main_pipeline"



def step1_normalize(input_file: Path) -> dict:
    log_pipeline_event(
        request_id="UNKNOWN", pipeline_name=pipeline_name, stage="step1_normalize:start",
        data={"input_file": str(input_file)}
    )
    
    normalized = normalize_request.normalize_request_file(str(input_file))
    request_id = normalized.get("request_id", "UNKNOWN")
    log_pipeline_event(
        request_id=request_id, pipeline_name=pipeline_name, stage="step1_normalize:normalized",
        data={"normalized": normalized}
    )
    return normalized

def step2_get_context(request_id :str, normalized: dict) -> dict:
    
    log_pipeline_event(
        request_id=request_id, pipeline_name=pipeline_name, stage="step2_get_context:start",
        data={"normalized": normalized}
    )
    
    search_text = normalized["normalized"]
    subject = normalized["title"]
    body_text = normalized["content"]

    context_bundle = get_context_bundle(
        search_text=search_text,
        request_id=request_id,
        subject=subject,
        body_text=body_text,
    )

    log_pipeline_event(
        request_id=request_id, pipeline_name=pipeline_name, stage="step2_get_context:end",
        data={"context_bundle": context_bundle}
    )
    #logger.debug(f"context_bundle: {json.dumps(context_bundle, indent=2, ensure_ascii=False)}")
    return context_bundle


def build_context_for_agents( request_id :str, normalized: dict,  context_bundle: dict,) -> dict:
    #logger.info("Step 3: building context for ADK agents")

    log_pipeline_event(
        request_id=request_id, pipeline_name=pipeline_name,stage="build_context_for_agents:start",
        data={"context_bundle": context_bundle}
    )



    body_text = normalized["content"]
    params = normalized.get("params", {})

    use_cases_sql = context_bundle.get("use_cases_sql", [])
    tables = context_bundle.get("tables", [])

    if not use_cases_sql:
        raise RuntimeError("No matching use_case_sql found in context_bundle")

    use_case_sql = use_cases_sql[0]   # take best match

    # Collect table descriptions as plain text for the LLM
    tables_content = []
    for t in tables:
        tbl_desc = f"Table: {t['schema_name']}.{t['table_name']}\n{t['content']}"
        tables_content.append(tbl_desc)

    context_for_agents = {
        "request_id": request_id,
        "tables_content": tables_content,
        "use_case_sql": use_case_sql,
        "params": params,
        "body_text": body_text,
    }

    # log_pipeline_event(
    #     request_id=request_id, pipeline_name=pipeline_name,stage="build_context_for_agents:end",
    #     data={"context_for_agents": context_for_agents}
    # )
    #logger.debug("Context for ADK agents: %s", json.dumps(context_for_agents, indent=2, ensure_ascii=False))
    return context_for_agents


async def run_adk_pipeline(request_id:str, context_for_agents: dict) -> dict:
    #logger.info("Step 4: running ADK SequentialAgent pipeline")
    log_pipeline_event(
        request_id=request_id, pipeline_name=pipeline_name, stage="run_adk_pipeline:start",
        data={"context_for_agents": str(context_for_agents)}
    )
    
    

       # 1) Build workflow agent
    pipeline_agent = build_adk_agents()

    events_collected = []



    # 2) Session + Runner
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=SESSION_ID,
    )

    log_pipeline_event(
        request_id=request_id, pipeline_name=pipeline_name, stage="run_adk_pipeline:await_session_created",
        data={"context_for_agents": str(context_for_agents)}
    )

    runner = Runner(
        agent=pipeline_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )

    log_pipeline_event(
        request_id=request_id, pipeline_name=pipeline_name, stage="run_adk_pipeline:runner_created",
        data={"context_for_agents": str(context_for_agents)}
    )

    # 3) First event from "user" with context JSON
    initial_message = json.dumps(context_for_agents, ensure_ascii=False)

    log_pipeline_event(
        request_id=request_id, pipeline_name=pipeline_name, stage="run_adk_pipeline:initial_message",
        data={"initial_message": str(initial_message)}
    )

    user_content = types.Content(
        role="user",
        parts=[types.Part(text=initial_message)],
    )
 
    

    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=SESSION_ID,    
        new_message=user_content,
    ):
        events_collected.append(event)



    log_pipeline_event(
        request_id=request_id, pipeline_name=pipeline_name, stage="run_adk_pipeline:async_for_event",
        data={"context_for_agents": str(context_for_agents)}
    )
        
    # convert events to dicts (if extract_llm_interactions exists)
    events_payload = extract_llm_interactions(events_collected)

   
    log_agent_events(
         session_id=SESSION_ID,
         agent_name="dml_pipeline",
         log_data=events_payload
        )
    
    # 5) After pipeline finishes, read final state
    session = await session_service.get_session(  app_name=APP_NAME,
                                                  user_id=USER_ID,
                                                  session_id=SESSION_ID,
                                                )
    state = session.state or {}

    log_pipeline_event(
        request_id=request_id,
        pipeline_name=pipeline_name,
        stage="run_adk_pipeline:full_state_dump",
        data={
            "state_keys": str(list(state.keys())),
            "state_repr": str(state),
        }
    )

    # 🔍 NEW: inspect / log the first agent output
    # replace "sql_probe" with the actual output_key of your first agent
    sql_probe = state.get("sql_probe")
    
    log_pipeline_event(
        request_id=request_id,
        pipeline_name=pipeline_name,
        stage="run_adk_pipeline:state_after_agents",
        data={"sql_probe": str(sql_probe)}
    )

    plan = state.get("plan")
    if not plan:
        raise RuntimeError("No 'plan' found in session.state after ADK pipeline")
    plan= clean_model_json(plan)
    
    log_pipeline_event(
        request_id=request_id, pipeline_name=pipeline_name, stage="run_adk_pipeline:get_sesion",
        data={"plan": str(plan)}
    )




    # plan may be JSON string; normalize to dict
    if isinstance(plan, str):

        plan = json.loads(plan)



    log_pipeline_event(
        request_id=request_id, pipeline_name=pipeline_name, stage="run_adk_pipeline:end",
        data={"plan": str(plan)}
    )
    
    
    return plan

def step6_write_sql(request_id:str, plan: dict, input_file: Path) -> Path:
    log_pipeline_event(
        request_id=request_id, pipeline_name=pipeline_name, stage="step6_write_sql:start",
        data={"plan": str(plan)}
    )
    output_dir = input_file.parent
    script_path = gen_dml_script_file.write_sql_script(plan, output_dir)



    log_pipeline_event(
        request_id=request_id, pipeline_name=pipeline_name, stage="step6_write_sql:end",
        data={"output_dir": str(output_dir)}
    )
    return script_path


def run_pipeline_for_file(input_file: str) -> Path:
    
    base_dir = Path(__file__).resolve().parent
    input_path = base_dir / "Data_files" / input_file

    # 1) normalize
    normalized = step1_normalize(input_path)

    request_id = str(normalized["request_id"])

    # 2) get context bundle from Postgres
    context_bundle = step2_get_context(request_id ,normalized)

    # 3) build context for ADK agents
    context_for_agents = build_context_for_agents(request_id , normalized, context_bundle)

    # 4) run ADK sequential pipeline
    plan = asyncio.run(run_adk_pipeline(request_id , context_for_agents))

    # 5) write SQL script
    script_path = step6_write_sql(request_id ,plan, input_path)
    print(f"Done. Generated SQL script: {script_path}")
    return script_path


if __name__ == "__main__":
    
  
    script_path = run_pipeline_for_file("input_req_123458.json")
   # print(f"Done. Generated SQL script: {script_path}")