-- Simple Photools Database Initialization
-- This script sets up basic database structure

\echo 'Initializing Photools database...'

-- Create necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create schema
CREATE SCHEMA IF NOT EXISTS photo_catalog;

-- Basic photos table
CREATE TABLE IF NOT EXISTS photo_catalog.photos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    filename VARCHAR(255) NOT NULL,
    file_path TEXT NOT NULL UNIQUE,
    file_size BIGINT,
    mime_type VARCHAR(100),
    width INTEGER,
    height INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Basic processing jobs table
CREATE TABLE IF NOT EXISTS photo_catalog.processing_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    photo_id UUID REFERENCES photo_catalog.photos(id) ON DELETE CASCADE,
    job_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_photos_filename ON photo_catalog.photos(filename);
CREATE INDEX IF NOT EXISTS idx_photos_created_at ON photo_catalog.photos(created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON photo_catalog.processing_jobs(status);

-- Grant permissions
GRANT ALL PRIVILEGES ON SCHEMA photo_catalog TO :"POSTGRES_USER";
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA photo_catalog TO :"POSTGRES_USER";
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA photo_catalog TO :"POSTGRES_USER";

\echo 'Photools database initialization completed!'