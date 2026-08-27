-- Run this alongside deleting the 2 test users in the Supabase Auth dashboard,
-- to clear out test data created under the old schema too.
-- Order matters (children before parents, due to foreign keys).

delete from messages;
delete from revenue_reports;
delete from engagement_reports;
delete from partnerships;
delete from connection_requests;
delete from proposals;      -- old table, safe no-op if it's empty or already dropped
delete from revenue_streams;
delete from listings;
