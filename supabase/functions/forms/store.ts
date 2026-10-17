// Store backed by Supabase's REST (PostgREST) and Storage APIs, using the service role key.
// The service role key is provided to Edge Functions automatically and never leaves Supabase.
import type { Store, Submission } from "./logic.ts";

export class SupabaseStore implements Store {
  constructor(private url: string, private key: string, private fetcher: typeof fetch = fetch) {}

  private headers(extra: Record<string, string> = {}): Record<string, string> {
    return { apikey: this.key, Authorization: `Bearer ${this.key}`, ...extra };
  }

  private async rest(path: string, init: RequestInit = {}): Promise<Response> {
    const r = await this.fetcher(`${this.url}/rest/v1/${path}`, {
      ...init,
      headers: this.headers({ "Content-Type": "application/json", ...(init.headers as Record<string, string> || {}) }),
    });
    if (!r.ok) throw new Error(`REST ${path}: ${r.status} ${await r.text()}`);
    return r;
  }

  async countHits(key: string, sinceMs: number): Promise<number> {
    const r = await this.rest(
      `rate_hits?select=id&key=eq.${encodeURIComponent(key)}&at=gt.${encodeURIComponent(new Date(sinceMs).toISOString())}`,
      { method: "HEAD", headers: { Prefer: "count=exact" } },
    );
    return Number((r.headers.get("content-range") || "*/0").split("/")[1] || 0);
  }

  async addHit(key: string): Promise<void> {
    await this.rest("rate_hits", { method: "POST", body: JSON.stringify({ key }), headers: { Prefer: "return=minimal" } });
  }

  async insertSubmission(s: Submission): Promise<number> {
    const r = await this.rest("submissions?select=id", {
      method: "POST", body: JSON.stringify(s), headers: { Prefer: "return=representation" },
    });
    return (await r.json())[0].id;
  }

  async saveAttachment(submissionId: number, filename: string, contentType: string, data: Uint8Array): Promise<void> {
    const path = `${submissionId}/${crypto.randomUUID()}`;
    const up = await this.fetcher(`${this.url}/storage/v1/object/attachments/${path}`, {
      method: "POST", body: new Blob([data.slice()], { type: contentType }),
      headers: this.headers({ "Content-Type": contentType, "x-upsert": "false" }),
    });
    if (!up.ok) throw new Error(`storage upload: ${up.status} ${await up.text()}`);
    await this.rest("attachments", {
      method: "POST", headers: { Prefer: "return=minimal" },
      body: JSON.stringify({ submission_id: submissionId, filename, content_type: contentType, size_bytes: data.length, storage_path: path }),
    });
  }

  async upsertWaitlist(email: string, consentText: string, ipHash: string, token: string): Promise<void> {
    await this.rest("waitlist?on_conflict=email", {
      method: "POST",
      headers: { Prefer: "resolution=merge-duplicates,return=minimal" },
      body: JSON.stringify({ email, consent_text: consentText, consent_at: new Date().toISOString(), ip_hash: ipHash,
        unsubscribe_token: token, unsubscribed_at: null }),
    });
  }

  async unsubscribe(token: string): Promise<boolean> {
    const r = await this.rest(`waitlist?unsubscribe_token=eq.${encodeURIComponent(token)}&unsubscribed_at=is.null&select=id`, {
      method: "PATCH", body: JSON.stringify({ unsubscribed_at: new Date().toISOString() }), headers: { Prefer: "return=representation" },
    });
    return (await r.json()).length > 0;
  }

  async purgeOlderThan(days: number): Promise<void> {
    const cutoff = new Date(Date.now() - days * 86400000).toISOString();
    const old = await (await this.rest(`submissions?created_at=lt.${encodeURIComponent(cutoff)}&select=id,attachments(storage_path)`)).json();
    const paths = old.flatMap((s: { attachments: { storage_path: string }[] }) => s.attachments.map((a) => a.storage_path));
    if (paths.length) {
      await this.fetcher(`${this.url}/storage/v1/object/attachments`, {
        method: "DELETE", body: JSON.stringify({ prefixes: paths }), headers: this.headers({ "Content-Type": "application/json" }),
      });
    }
    if (old.length) await this.rest(`submissions?created_at=lt.${encodeURIComponent(cutoff)}`, { method: "DELETE" });
    await this.rest(`rate_hits?at=lt.${encodeURIComponent(new Date(Date.now() - 86400000).toISOString())}`, { method: "DELETE" });
  }
}
