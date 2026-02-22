-- Add columns for tool selection (resource + action + has_path_params).
-- Run after 001_api_sources_and_operations.sql. Safe to run if columns already exist (will error on duplicate; run once).

ALTER TABLE api_operations ADD COLUMN IF NOT EXISTS has_path_params BOOLEAN NOT NULL DEFAULT true;
ALTER TABLE api_operations ADD COLUMN IF NOT EXISTS resource VARCHAR(64);
ALTER TABLE api_operations ADD COLUMN IF NOT EXISTS action VARCHAR(32);

COMMENT ON COLUMN api_operations.has_path_params IS 'True if path_template contains {param}; used to prefer list endpoints for "list of X"';
COMMENT ON COLUMN api_operations.resource IS 'Entity name for matching: airports, hotels, passengers, pricelists, etc.';
COMMENT ON COLUMN api_operations.action IS 'list | get_by_id | create | update | delete | other';
