-- money on reviewed evidence is final too. the worker has a plain INSERT on budgets and
-- the trail shows every figure on accepted evidence, so without this a buggy re-run could
-- slip unreviewed money onto the record. evidence_service skips reviewed sources already,
-- this is the db saying the same thing
create or replace function protect_reviewed_worker_budgets() returns trigger
language plpgsql as $$
begin
  if current_user <> 'paper_trail_worker' then
    return new;
  end if;
  -- same key decide_link locks, so any insert (store or raw sql) waits for a click in
  -- flight, and the check below then sees it (read committed, fresh snapshot per statement)
  perform pg_advisory_xact_lock(hashtextextended('budget:' || new.evidence_id, 0));
  if exists
    (select 1 from links where evidence_id=new.evidence_id and review_status <> 'unreviewed') then
    -- own sqlstate so the store can tell this apart and skip the figure
    raise exception 'workers cannot add money to reviewed evidence' using errcode = 'PTR01';
  end if;
  return new;
end $$;
drop trigger if exists protect_reviewed_worker_budgets on budgets;
create trigger protect_reviewed_worker_budgets before insert on budgets
for each row execute function protect_reviewed_worker_budgets();
