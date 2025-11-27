CREATE SCHEMA IF NOT EXISTS logs;

CREATE TABLE IF NOT EXISTS logs.agent_llm_logs (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL,
	app_name VARCHAR(255) NOT NULL,
	agent_name  VARCHAR(255) NOT NULL,  
        log_data JSONB NOT NULL,
	run_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS logs.db_pipeline_logs (
    id SERIAL PRIMARY KEY,
    request_id VARCHAR(255) NOT NULL,
    app_name VARCHAR(255) NOT NULL,
    pipeline_name VARCHAR(255) NOT NULL,
    stage VARCHAR(255) NOT NULL,
    log_data JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT now()
);