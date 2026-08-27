-- Run this first to see your current trigger function's exact definition.
select pg_get_functiondef(oid)
from pg_proc
where proname = 'handle_new_user';

-- If that returns nothing, your trigger function has a different name.
-- Use this instead to find it:
select trigger_name, event_object_table, action_statement
from information_schema.triggers
where event_object_schema = 'auth' and event_object_table = 'users';
