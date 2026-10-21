-- =====================================================================
-- Crescopus: let accounts be deleted cleanly
-- Run after migration_plan_ledger.sql. Safe to re-run.
--
-- The "who did this" columns on plans and ledger entries pointed at
-- profiles with no delete rule, so deleting an account that had added
-- or confirmed a ledger entry was blocked. Now the record stays and the
-- name is simply cleared ("set null") when that account is deleted.
-- =====================================================================

alter table cresco_plans
  drop constraint if exists cresco_plans_updated_by_fkey,
  add  constraint cresco_plans_updated_by_fkey
       foreign key (updated_by) references profiles(id) on delete set null;

alter table plan_versions
  drop constraint if exists plan_versions_created_by_fkey,
  add  constraint plan_versions_created_by_fkey
       foreign key (created_by) references profiles(id) on delete set null;

alter table ledger_entries
  drop constraint if exists ledger_entries_added_by_fkey,
  add  constraint ledger_entries_added_by_fkey
       foreign key (added_by) references profiles(id) on delete set null;

alter table ledger_entries
  drop constraint if exists ledger_entries_confirmed_by_fkey,
  add  constraint ledger_entries_confirmed_by_fkey
       foreign key (confirmed_by) references profiles(id) on delete set null;
