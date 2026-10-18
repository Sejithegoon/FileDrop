-- WiFiDrop Pro licences and the PCs they are activated on.
-- The "licence" Edge Function issues and activates licences with the service role.
-- Admins (public.admins) can read them, revoke or restore them, and free up PCs from the inbox.
-- We keep only what licensing needs: no names, addresses or payment details.

create table if not exists public.licences (
    id              text primary key,                    -- e.g. WDP-7K3M-QX2D-9PRT-HV4C
    email           text not null,                       -- where the licence was sent
    order_id        text unique,                         -- merchant order (payments, Phase D)
    edition         text not null default 'pro' check (edition in ('pro')),
    issued_at       timestamptz not null default now(),
    updates_until   date not null,
    max_activations integer not null default 3 check (max_activations between 1 and 50),
    revoked_at      timestamptz,
    revoke_reason   text not null default '',
    note            text not null default '',
    licence_text    text not null
);
create index if not exists licences_email on public.licences (lower(email));

create table if not exists public.activations (
    id           bigint generated always as identity primary key,
    licence_id   text not null references public.licences (id) on delete cascade,
    install_id   text not null,                          -- random ID of one WiFiDrop install, nothing personal
    app_version  text not null default '',
    activated_at timestamptz not null default now(),
    last_seen_at timestamptz not null default now(),
    unique (licence_id, install_id)
);

alter table public.licences    enable row level security;
alter table public.activations enable row level security;
revoke all on public.licences, public.activations from anon;

drop policy if exists "admins read licences" on public.licences;
create policy "admins read licences" on public.licences for select to authenticated using (public.is_admin());
drop policy if exists "admins update licences" on public.licences;
create policy "admins update licences" on public.licences for update to authenticated
    using (public.is_admin()) with check (public.is_admin());

drop policy if exists "admins read activations" on public.activations;
create policy "admins read activations" on public.activations for select to authenticated using (public.is_admin());
drop policy if exists "admins remove activations" on public.activations;
create policy "admins remove activations" on public.activations for delete to authenticated using (public.is_admin());

-- Admins may change only these columns; licence text, email and dates are fixed once issued.
revoke update on public.licences from authenticated;
grant update (revoked_at, revoke_reason, note) on public.licences to authenticated;
