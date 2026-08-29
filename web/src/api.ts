import type { Storm, SystemStatus, UploadResult } from "./types";

export interface StormListItem {
  storm_id: string;
  sid: string;
  name: string;
  basin: string;
  mode: string;
  status: string;
  first_valid_time: string;
  last_valid_time: string;
  peak: {
    vmax_kt: number;
    valid_time: string;
    category: {
      name: string;
      code: string;
      tone: string;
    };
  };
  observation_count: number;
  satellites: string[];
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) message = body.detail;
    } catch {
      // Keep the status-based fallback.
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export async function getStatus(signal?: AbortSignal): Promise<SystemStatus> {
  return parseResponse(
    await fetch("/api/v1/status", { signal, headers: { Accept: "application/json" } }),
  );
}

export async function getStorms(signal?: AbortSignal): Promise<{ items: StormListItem[]; count: number }> {
  return parseResponse(
    await fetch("/api/v1/storms", { signal, headers: { Accept: "application/json" } }),
  );
}

export async function getStorm(stormId: string, signal?: AbortSignal): Promise<Storm> {
  return parseResponse(
    await fetch(`/api/v1/storms/${encodeURIComponent(stormId)}`, {
      signal,
      headers: { Accept: "application/json" },
    }),
  );
}

export async function uploadAnalysis(file: File): Promise<UploadResult> {
  const form = new FormData();
  form.append("file", file);
  return parseResponse(
    await fetch("/api/v1/analysis/upload", { method: "POST", body: form }),
  );
}

export async function transitionAlert(
  alertId: string,
  action: "acknowledge" | "escalate" | "dismiss" | "resolve",
  reason?: string,
): Promise<{ status: string }> {
  return parseResponse(
    await fetch(`/api/v1/alerts/${encodeURIComponent(alertId)}/transition`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, reason, reviewer: "Demo analyst" }),
    }),
  );
}

