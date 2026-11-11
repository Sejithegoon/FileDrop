-- Website stats: daily counts of page views, download clicks and Buy clicks, nothing else.
-- No cookies, no IP addresses, no visitor IDs: each row is just "this many of this event on this page that day".
-- The website calls public.track() with the publishable key; only admins (public.admins) can read the totals.

create table if not exists public.site_stats (
    day    date    not null default current_date,
    event  text    not null check (event in ('view', 'download', 'buy_click', 'buy_done')),
    page   text    not null default '',              -- e.g. index.html, pricing.html
    source text    not null default '',              -- referring site's host for visits from other sites, e.g. youtube.com
    n      bigint  not null default 0,
    primary key (day, event, page, source)
);

alter table public.site_stats enable row level security;
revoke all on public.site_stats from anon, authenticated;
grant select on public.site_stats to authenticated;
drop policy if exists "admins read site stats" on public.site_stats;
create policy "admins read site stats" on public.site_stats for select to authenticated using (public.is_admin());

-- Adds one to today's count. Anything that doesn't look like one of our pages or a plain host name is
-- stored as 'other', so the table can't be used to store arbitrary text.
create or replace function public.track(p_event text, p_page text default '', p_source text default '')
returns void language plpgsql security definer set search_path = public as $$
declare
    pg  text := lower(coalesce(p_page, ''));
    src text := lower(coalesce(p_source, ''));
begin
    if p_event not in ('view', 'download', 'buy_click', 'buy_done') then return; end if;
    if pg !~ '^[a-z0-9-]{1,40}\.html$' then pg := 'other'; end if;
    src := regexp_replace(src, '^www\.', '');
    if src <> '' and src !~ '^[a-z0-9.-]{1,60}$' then src := 'other'; end if;
    insert into public.site_stats as s (day, event, page, source, n)
    values ((now() at time zone 'America/Winnipeg')::date, p_event, pg, src, 1)
    on conflict (day, event, page, source) do update set n = s.n + 1;
end $$;

revoke all on function public.track(text, text, text) from public;
grant execute on function public.track(text, text, text) to anon, authenticated;
