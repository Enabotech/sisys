-- sisys - PostgreSQL Database Initialization Script
-- This script is executed when the PostgreSQL container is first started

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create schema for sisys
CREATE SCHEMA IF NOT EXISTS sisys;

-- Grant permissions
GRANT ALL PRIVILEGES ON SCHEMA sisys TO sisys_dev;
GRANT ALL PRIVILEGES ON DATABASE sisys TO sisys_dev;

-- Note: Tables will be created by Alembic migrations
-- This script just sets up the initial database structure
