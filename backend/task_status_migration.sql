-- AI Action Planner: task_status table
-- Run this in your Supabase SQL Editor to create the table and enable RLS.

CREATE TABLE IF NOT EXISTS public.task_status (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    task_id       TEXT NOT NULL,          -- stable hash derived from cause (product + cause_type)
    status        TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'completed')),
    completed_at  TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, task_id)
);

-- Index for fast per-user lookups
CREATE INDEX IF NOT EXISTS task_status_user_id_idx ON public.task_status (user_id);

-- Enable Row Level Security
ALTER TABLE public.task_status ENABLE ROW LEVEL SECURITY;

-- Users can only see their own rows
CREATE POLICY "Users can view their own task status"
    ON public.task_status
    FOR SELECT
    USING (auth.uid() = user_id);

-- Users can insert their own rows
CREATE POLICY "Users can insert their own task status"
    ON public.task_status
    FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- Users can update their own rows
CREATE POLICY "Users can update their own task status"
    ON public.task_status
    FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- Users can delete their own rows (for reopening via delete+reinsert if needed)
CREATE POLICY "Users can delete their own task status"
    ON public.task_status
    FOR DELETE
    USING (auth.uid() = user_id);

-- Trigger to auto-update updated_at
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_task_status_updated_at ON public.task_status;
CREATE TRIGGER set_task_status_updated_at
    BEFORE UPDATE ON public.task_status
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
