# main_pipeline.py

from google.adk.agents.sequential_agent import SequentialAgent
from get_sql_info_agent import build_sql_info_agent
from get_dml_info_agent import build_dml_planner_agent
from utils.config import  DEFAULT_LLM_MODEL

def build_adk_agents() -> SequentialAgent:
    sql_agent = build_sql_info_agent(
        model_name=DEFAULT_LLM_MODEL,
        output_key="sql_probe",
    )

    
    dml_agent = build_dml_planner_agent(
        model_name=DEFAULT_LLM_MODEL,
        output_key="plan",
    )

    return SequentialAgent(
        name="dml_pipeline",
        description="Sequential Agent : SQL info + DML planning",
        sub_agents=[sql_agent, dml_agent],
    )
