// LicenceStore backed by Supabase REST with the service role key (provided to Edge Functions automatically).
import { type LicenceRow, type LicenceStore, type Mailer, PermanentMailError } from "./logic.ts";

export class SupabaseLicenceStore implements LicenceStore {
  constructor(private url: string, private key: string, private fetcher: typeof fetch = fetch) {}

  private async rest(path: string, init: RequestInit = {}): Promise<Response> {
    const r = await this.fetcher(`${this.url}/rest/v1/${path}`, {
      ...init,
      headers: { apikey: this.key, Authorization: `Bearer ${this.key}`, "Content-Type": "application/json",
        ...(init.headers as Record<string, string> || {}) },
    });
    if (!r.ok) throw new Error(`REST ${path}: ${r.status} ${await r.text()}`);
    return r;
  }

  async countHits(key: string, sinceMs: number): Promise<number> {
    const r = await this.rest(`rate_hits?select=id&key=eq.${encodeURIComponent(key)}&at=gt.${encodeURIComponent(new Date(sinceMs).toISOString())}`,
      { method: "HEAD", headers: { Prefer: "count=exact" } });
    return Number((r.headers.get("content-range") || "*/0").split("/")[1] || 0);
  }

  async addHit(key: string): Promise<void> {
    await this.rest("rate_hits", { method: "POST", body: JSON.stringify({ key }), headers: { Prefer: "return=minimal" } });
  }

  async getLicence(id: string): Promise<LicenceRow | null> {
    const rows = await (await this.rest(`licences?id=eq.${encodeURIComponent(id)}&select=*`)).json();
    return rows[0] ?? null;
  }

  async licencesByEmail(email: string): Promise<LicenceRow[]> {
    return await (await this.rest(`licences?email=eq.${encodeURIComponent(email)}&select=*&order=issued_at`)).json();
  }

  async insertLicence(row: LicenceRow & { note: string; order_id: string | null }): Promise<void> {
    await this.rest("licences", { method: "POST", body: JSON.stringify(row), headers: { Prefer: "return=minimal" } });
  }

  async activations(licenceId: string): Promise<string[]> {
    const rows = await (await this.rest(`activations?licence_id=eq.${encodeURIComponent(licenceId)}&select=install_id`)).json();
    return rows.map((r: { install_id: string }) => r.install_id);
  }

  async addActivation(licenceId: string, installId: string, appVersion: string): Promise<void> {
    await this.rest("activations?on_conflict=licence_id,install_id", {
      method: "POST", headers: { Prefer: "resolution=ignore-duplicates,return=minimal" },
      body: JSON.stringify({ licence_id: licenceId, install_id: installId, app_version: appVersion }),
    });
  }

  async touchActivation(licenceId: string, installId: string, appVersion: string): Promise<void> {
    await this.rest(`activations?licence_id=eq.${encodeURIComponent(licenceId)}&install_id=eq.${encodeURIComponent(installId)}`, {
      method: "PATCH", headers: { Prefer: "return=minimal" },
      body: JSON.stringify({ last_seen_at: new Date().toISOString(), app_version: appVersion }),
    });
  }

  async removeActivation(licenceId: string, installId: string): Promise<void> {
    await this.rest(`activations?licence_id=eq.${encodeURIComponent(licenceId)}&install_id=eq.${encodeURIComponent(installId)}`,
      { method: "DELETE", headers: { Prefer: "return=minimal" } });
  }

  /** True if the bearer token belongs to a signed-in user listed in public.admins. */
  async isAdmin(authorization: string): Promise<boolean> {
    if (!authorization.startsWith("Bearer ")) return false;
    const r = await this.fetcher(`${this.url}/auth/v1/user`, { headers: { apikey: this.key, Authorization: authorization } });
    if (!r.ok) return false;
    const user = await r.json();
    if (!user?.id) return false;
    const rows = await (await this.rest(`admins?user_id=eq.${encodeURIComponent(user.id)}&select=user_id`)).json();
    return rows.length > 0;
  }
}

/** Sends email through Resend (https://resend.com) when RESEND_API_KEY is set. */
export class ResendMailer implements Mailer {
  constructor(private apiKey: string, private from: string, private fetcher: typeof fetch = fetch) {}

  async send(to: string, subject: string, text: string, html?: string): Promise<void> {
    const r = await this.fetcher("https://api.resend.com/emails", {
      method: "POST",
      headers: { Authorization: `Bearer ${this.apiKey}`, "Content-Type": "application/json" },
      body: JSON.stringify({ from: this.from, to: [to], subject, text, ...(html ? { html } : {}) }),
    });
    if (r.ok) return;
    const detail = `email: ${r.status} ${(await r.text()).slice(0, 300)}`;
    // 4xx (except rate limits) means the email itself was refused; 5xx and 429 are worth retrying.
    if (r.status >= 400 && r.status < 500 && r.status !== 429) throw new PermanentMailError(detail);
    throw new Error(detail);
  }
}
