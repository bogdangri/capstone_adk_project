CREATE EXTENSION IF NOT EXISTS vector;

CREATE SCHEMA IF NOT EXISTS setup;

CREATE TABLE IF NOT EXISTS setup.catalog_tables (
  doc_id       bigserial PRIMARY KEY,
  schema_name  text NOT NULL DEFAULT 'public',
  table_name   text NOT NULL,
  title        text NOT NULL,             -- e.g., "setup.domain_values"
  content      text NOT NULL,             -- natural-language description incl. columns
  embedding    vector(1536) NOT NULL,     -- pgvector embedding
  UNIQUE (schema_name, table_name)
);

-- Fast ANN index (cosine)
CREATE INDEX IF NOT EXISTS idx_catalog_tables_embed
  ON setup.catalog_tables
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);

-- 2) Use-case catalog (procedural knowledge)
CREATE TABLE IF NOT EXISTS setup.catalog_use_cases (
  doc_id         bigserial PRIMARY KEY,
  locale         text NOT NULL DEFAULT 'mixed', -- 'RO', 'EN', 'mixed' etc.
  title          text NOT NULL,                 -- short name, e.g. "Create/Update COD_SIND"
  request_text   text NOT NULL,                 -- examples of user emails/requests (multi-lingual ok)
  solution_text  text NOT NULL,                 -- your descriptive procedure
  tables_hint    text[],                        -- optional: ['reference_codes'] etc.
  sql_info_text  text NOT NULL, 
  sql_instr_text text NOT NULL,
  embedding     vector(1536) NOT NULL
);

CREATE TABLE IF NOT EXISTS setup.catalog_use_cases (
    doc_id        SERIAL PRIMARY KEY,
    locale        TEXT NOT NULL,
    title         TEXT NOT NULL UNIQUE,
    request_text  TEXT NOT NULL,
    solution_text TEXT NOT NULL,
    tables_hint   TEXT[] DEFAULT '{}',
    sql_info_json JSONB NOT NULL,
    embedding VECTOR(768)
);


CREATE INDEX IF NOT EXISTS idx_catalog_use_cases_embed
  ON setup.catalog_use_cases
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 200);

 ALTER TABLE setup.catalog_use_cases
  ADD CONSTRAINT catalog_use_cases_2_title_key UNIQUE (title);