-- Create langfuse database for Langfuse service
-- This script is executed during PostgreSQL container initialization

CREATE DATABASE langfuse;
GRANT ALL PRIVILEGES ON DATABASE langfuse TO sunnyagent;
