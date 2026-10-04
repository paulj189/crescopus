-- Adds read-tracking so unread messages can surface in the nav badge and
-- dashboard, instead of being invisible unless you open the CrescoPact.
-- Additive migration — safe to run without resetting the database.

create table message_reads (
  partnership_id uuid not null references partnerships(id) on delete cascade,
  profile_id uuid not null references profiles(id) on delete cascade,
  last_read_at timestamptz not null default now(),
  primary key (partnership_id, profile_id)
);

alter table message_reads enable row level security;

create policy "Users manage their own read state"
  on message_reads for all using (profile_id = auth.uid())
  with check (profile_id = auth.uid());
