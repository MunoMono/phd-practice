-- Ensure postgres password matches environment variable
-- This should be the FIRST migration to run
-- Prevents password authentication failures after container recreations

DO $$
BEGIN
    -- Set password to match POSTGRES_PASSWORD from environment
    EXECUTE 'ALTER USER postgres WITH PASSWORD ''postgres''';
    RAISE NOTICE 'Postgres password set successfully';
END $$;
