-- Photools Database Initialization Script
-- Creates initial database structure for photo metadata cataloging

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create basic tables for initial setup
-- This is a minimal schema to get the database running

-- Photos table for basic photo metadata
CREATE TABLE IF NOT EXISTS photos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    filename VARCHAR(255) NOT NULL,
    file_path TEXT NOT NULL,
    file_size BIGINT,
    mime_type VARCHAR(100),
    width INTEGER,
    height INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Indexes for common queries
    CONSTRAINT photos_filename_unique UNIQUE (filename, file_path)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_photos_filename ON photos(filename);
CREATE INDEX IF NOT EXISTS idx_photos_created_at ON photos(created_at);
CREATE INDEX IF NOT EXISTS idx_photos_mime_type ON photos(mime_type);

-- Metadata table for EXIF and other metadata
CREATE TABLE IF NOT EXISTS photo_metadata (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    photo_id UUID NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
    key VARCHAR(255) NOT NULL,
    value TEXT,
    value_type VARCHAR(50) DEFAULT 'string',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT photo_metadata_unique UNIQUE (photo_id, key)
);

-- Create indexes for metadata queries
CREATE INDEX IF NOT EXISTS idx_photo_metadata_photo_id ON photo_metadata(photo_id);
CREATE INDEX IF NOT EXISTS idx_photo_metadata_key ON photo_metadata(key);
CREATE INDEX IF NOT EXISTS idx_photo_metadata_key_value ON photo_metadata(key, value);

-- System info table for tracking database version and configuration
CREATE TABLE IF NOT EXISTS system_info (
    key VARCHAR(255) PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Insert initial system information
INSERT INTO system_info (key, value) VALUES 
    ('db_version', '0.1.0'),
    ('initialized_at', CURRENT_TIMESTAMP::TEXT),
    ('schema_version', '1')
ON CONFLICT (key) DO UPDATE SET 
    value = EXCLUDED.value,
    updated_at = CURRENT_TIMESTAMP;

-- Create a trigger to automatically update updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply the trigger to relevant tables
CREATE TRIGGER update_photos_updated_at 
    BEFORE UPDATE ON photos 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions to the application user
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO photo_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO photo_user;
GRANT USAGE, CREATE ON SCHEMA public TO photo_user;

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'Photools database initialized successfully!';
    RAISE NOTICE 'Schema version: 1';
    RAISE NOTICE 'Database ready for photo metadata cataloging';
END $$;