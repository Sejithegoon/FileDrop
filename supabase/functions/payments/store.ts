// PaymentStore on Supabase REST, plus the small piece of the Paddle API we need (the buyer's email).
import { SupabaseLicenceStore } from "../licence/store.ts";
import type { LicenceRow } from "../licence/logic.ts";
import type { Paddle, PaymentStore } from "./logic.ts";

export class SupabasePaymentStore extends SupabaseLicenceStore implements PaymentStore {
  constructor(private base: string, private serviceKey: string, private f: typeof fetch = fetch) {
    super(base, serviceKey, f);
  }

  private async call(path: string, init: RequestInit = {}): Promise<Response> {
    const r = await this.f(`${this.base}/rest/v1/${path}`, {
      ...init,
      headers: { apikey: this.serviceKey, Authorization: `Bearer ${this.serviceKey}`, "Content-Type": "application/json",
        ...(init.headers as Record<string, string> || {}) },
    });
    if (!r.ok) throw new Error(`REST ${path}: ${r.status} ${await r.text()}`);
    return r;
  }

  async seenEvent(id: string): Promise<boolean> {
    return (await (await this.call(`payment_events?id=eq.${encodeURIComponent(id)}&select=id`)).json()).length > 0;
  }

  async recordEvent(id: string, type: string, result: string): Promise<void> {
    await this.call("payment_events?on_conflict=id", {
      method: "POST", headers: { Prefer: "resolution=ignore-duplicates,return=minimal" },
      body: JSON.stringify({ id, type, result: result.slice(0, 500) }),
    });
  }

  async licenceByOrder(orderId: string): Promise<LicenceRow | null> {
    return (await (await this.call(`licences?order_id=eq.${encodeURIComponent(orderId)}&select=*`)).json())[0] ?? null;
  }

  async setRevoked(orderId: string, revokedAt: string | null, reason: string): Promise<number> {
    const rows = await (await this.call(`licences?order_id=eq.${encodeURIComponent(orderId)}&select=id`, {
      method: "PATCH", headers: { Prefer: "return=representation" },
      body: JSON.stringify({ revoked_at: revokedAt, revoke_reason: reason }),
    })).json();
    return rows.length;
  }
}

export class PaddleApi implements Paddle {
  constructor(private apiKey: string, private sandbox: boolean, private f: typeof fetch = fetch) {}

  async customerEmail(customerId: string): Promise<string> {
    const host = this.sandbox ? "https://sandbox-api.paddle.com" : "https://api.paddle.com";
    const r = await this.f(`${host}/customers/${encodeURIComponent(customerId)}`, {
      headers: { Authorization: `Bearer ${this.apiKey}` },
    });
    if (!r.ok) throw new Error(`Paddle customers: ${r.status} ${await r.text()}`);
    return (await r.json())?.data?.email ?? "";
  }
}
