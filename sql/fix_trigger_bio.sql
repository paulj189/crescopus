CREATE OR REPLACE FUNCTION public.handle_new_user()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
begin
  insert into public.profiles (id, full_name, is_developer, is_grower, country, bio)
  values (
    new.id,
    coalesce(new.raw_user_meta_data->>'full_name', ''),
    coalesce((new.raw_user_meta_data->>'is_developer')::boolean, false),
    coalesce((new.raw_user_meta_data->>'is_grower')::boolean, false),
    new.raw_user_meta_data->>'country',
    new.raw_user_meta_data->>'bio'
  );
  return new;
end;
$function$
