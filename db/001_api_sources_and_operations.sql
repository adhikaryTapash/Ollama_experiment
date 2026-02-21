-- External API tool: api_sources and api_operations
-- Run this with a Postgres user that has CREATE TABLE (writer will need INSERT/UPDATE).
-- App uses read-only access (SELECT only).

CREATE TABLE IF NOT EXISTS api_sources (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(255) NOT NULL UNIQUE,
    base_url    VARCHAR(2048) NOT NULL,
    swagger_url VARCHAR(2048) NOT NULL,
    raw_swagger JSONB NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS api_operations (
    id                      SERIAL PRIMARY KEY,
    api_source_id           INTEGER NOT NULL REFERENCES api_sources(id) ON DELETE CASCADE,
    operation_id            VARCHAR(255) NOT NULL,
    method                  VARCHAR(10) NOT NULL,
    path_template           VARCHAR(2048) NOT NULL,
    summary                 TEXT,
    tag                     VARCHAR(255),
    parameters_schema       JSONB,
    request_body_schema_ref  VARCHAR(255),
    UNIQUE(api_source_id, operation_id)
);

CREATE INDEX IF NOT EXISTS idx_api_operations_api_source_id
    ON api_operations(api_source_id);

COMMENT ON TABLE api_sources IS 'One row per external API (tenant). Writer upserts; app reads.';
COMMENT ON TABLE api_operations IS 'One row per path+method. Writer upserts; app reads.';
