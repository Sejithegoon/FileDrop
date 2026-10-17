-- Paddle webhooks: each event is recorded once, so a repeated delivery never issues a second licence.
create table if not exists public.payment_events (
    id          text primary key,                 -- Paddle event_id
    type        text not null,
    received_at timestamptz not null default now(),
    result      text not null default ''
);

alter table public.payment_events enable row level security;
revoke all on public.payment_events from anon;
drop policy if exists "admins read payment events" on public.payment_events;
create policy "admins read payment events" on public.payment_events for select to authenticated using (public.is_admin());
