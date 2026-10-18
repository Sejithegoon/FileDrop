-- WiFiDrop website forms: feedback, contact, beta sign-ups, Pro waitlist.
-- Visitors never touch these tables directly: the "forms" Edge Function writes with the
-- service role. Row Level Security lets only accounts listed in public.admins read or change them.

create table if not exists public.admins (
    user_id uuid primary key references auth.users (id) on delete cascade,
    added_at timestamptz not null default now()
);

create table if not exists public.submissions (
    id          bigint generated always as identity primary key,
    kind        text not null check (kind in ('feedback', 'contact', 'beta')),
    category    text not null,
    name        text not null default '',
    email       text not null default '',
    subject     text not null default '',
    message     text not null default '',
    details     jsonb not null default '{}'::jsonb,
    status      text not null default 'new' check (status in ('new', 'in_progress', 'closed')),
    admin_note  text not null default '',
    ip_hash     text not null default '',
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now()
);
create index if not exists submissions_kind_status on public.submissions (kind, status, created_at desc);

create table if not exists public.attachments (
    id            bigint generated always as identity primary key,
    submission_id bigint not null references public.submissions (id) on delete cascade,
    filename      text not null,
    content_type  text not null,
    size_bytes    integer not null,
    storage_path  text not null unique
);
create index if not exists attachments_submission on public.attachments (submission_id);

create table if not exists public.waitlist (
    id                bigint generated always as identity primary key,
    email             text not null unique,
    consent_text      text not null,
    consent_at        timestamptz not null default now(),
    ip_hash           text not null default '',
    unsubscribe_token text not null unique,
    unsubscribed_at   timestamptz
);

-- Short-lived counters for per-IP rate limits (only the function uses this).
create table if not exists public.rate_hits (
    id   bigint generated always as identity primary key,
    key  text not null,
    at   timestamptz not null default now()
);
create index if not exists rate_hits_key_at on public.rate_hits (key, at);

-- ---------------------------------------------------------------- security
alter table public.admins      enable row level security;
alter table public.submissions enable row level security;
alter table public.attachments enable row level security;
alter table public.waitlist    enable row level security;
alter table public.rate_hits   enable row level security;

-- Nothing for anonymous visitors.
revoke all on public.admins, public.submissions, public.attachments, public.waitlist, public.rate_hits from anon;

create or replace function public.is_admin() returns boolean
language sql stable security definer set search_path = public as $$
    select exists (select 1 from public.admins where user_id = auth.uid());
$$;
revoke all on function public.is_admin() from anon;

drop policy if exists "admins see themselves" on public.admins;
create policy "admins see themselves" on public.admins for select to authenticated using (user_id = auth.uid());

drop policy if exists "admins read submissions" on public.submissions;
create policy "admins read submissions" on public.submissions for select to authenticated using (public.is_admin());
drop policy if exists "admins update submissions" on public.submissions;
create policy "admins update submissions" on public.submissions for update to authenticated using (public.is_admin()) with check (public.is_admin());
drop policy if exists "admins delete submissions" on public.submissions;
create policy "admins delete submissions" on public.submissions for delete to authenticated using (public.is_admin());

drop policy if exists "admins read attachments" on public.attachments;
create policy "admins read attachments" on public.attachments for select to authenticated using (public.is_admin());

drop policy if exists "admins read waitlist" on public.waitlist;
create policy "admins read waitlist" on public.waitlist for select to authenticated using (public.is_admin());
drop policy if exists "admins delete waitlist" on public.waitlist;
create policy "admins delete waitlist" on public.waitlist for delete to authenticated using (public.is_admin());

-- ---------------------------------------------------------------- attachments bucket (private)
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('attachments', 'attachments', false, 5242880,
        array['image/png', 'image/jpeg', 'image/webp', 'image/gif', 'text/plain'])
on conflict (id) do nothing;

drop policy if exists "admins read attachment files" on storage.objects;
create policy "admins read attachment files" on storage.objects for select to authenticated
    using (bucket_id = 'attachments' and public.is_admin());
drop policy if exists "admins delete attachment files" on storage.objects;
create policy "admins delete attachment files" on storage.objects for delete to authenticated
    using (bucket_id = 'attachments' and public.is_admin());
