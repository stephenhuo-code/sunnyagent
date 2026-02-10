-- Migration: Create files table for user file management
-- Run this script against the PostgreSQL database

-- Create files table
CREATE TABLE IF NOT EXISTS files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_id VARCHAR(8) UNIQUE NOT NULL,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
    original_name VARCHAR(255) NOT NULL,
    content_type VARCHAR(100),
    size_bytes BIGINT NOT NULL,
    storage_path TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);

-- Create indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_files_user ON files(user_id);
CREATE INDEX IF NOT EXISTS idx_files_conversation ON files(conversation_id);
CREATE INDEX IF NOT EXISTS idx_files_file_id ON files(file_id);

-- Add comment for documentation
COMMENT ON TABLE files IS 'User-uploaded files with permission tracking';
COMMENT ON COLUMN files.file_id IS '8-character short ID for URL paths';
COMMENT ON COLUMN files.user_id IS 'Owner of the file - cascades on user deletion';
COMMENT ON COLUMN files.conversation_id IS 'Optional link to conversation - set NULL on conversation deletion';
COMMENT ON COLUMN files.storage_path IS 'Actual file path on disk (e.g., /tmp/sunnyagent_files/{file_id}/{filename})';
COMMENT ON COLUMN files.is_deleted IS 'Soft delete flag';
