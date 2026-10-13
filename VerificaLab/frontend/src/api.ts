// Cliente da API — mesmo origem; CSRF via header em mutações.

export interface SessionInfo {
  csrf_token: string;
  csrf_header: string;
  version: string;
  limits: {
    load_max_rps: number;
    load_default_rps: number;
    load_max_concurrency: number;
    load_max_duration_s: number;
    load_max_attempts: number;
    load_allowed_methods: string[];
    max_upload_bytes: number;
    suite_allowed_commands: string[][];
    retention: string;
  };
  lab: { running: boolean; pid: number | null; endpoint: string; managed_by: string | null };
}

export interface Project {
  id: string;
  name: string;
  description: string;
  created_at: string;
  environments?: number;
  profiles?: number;
  runs?: number;
}

export interface Environment {
  id: string;
  project_id: string;
  name: string;
  scheme: string;
  host: string;
  port: number;
  kind: string;
  secret_header_name: string | null;
  has_secret: boolean;
  created_at: string;
}

export interface Tool {
  id: string;
  slug: string;
  name: string;
  upstream_path: string;
  language: string;
  license: string;
  status: string;
  capabilities: string[];
  import_formats: string[];
  notes: string;
}

export interface Profile {
  id: string;
  project_id: string;
  name: string;
  kind: "http" | "load" | "suite";
  config: Record<string, unknown>;
  created_at: string;
}

export interface Run {
  id: string;
  project_id: string;
  environment_id: string;
  profile_id: string;
  kind: string;
  state: string;
  queued_at: string;
  started_at: string | null;
  finished_at: string | null;
  exit_code: number | null;
  summary: string;
  progress: number;
  config: Record<string, unknown>;
}

export interface CheckResult {
  id: string;
  seq: number;
  name: string;
  category: string;
  status: string;
  expected: string | null;
  observed: string | null;
  message: string;
  evidence: Record<string, unknown>;
  duration_ms: number | null;
}

export interface Metric {
  id: string;
  name: string;
  value: number | null;
  unit: string | null;
  origin: string;
  samples: number | null;
  population: string | null;
  discarded: number;
  details: Record<string, unknown>;
}

export interface Finding {
  id: string;
  severity: string;
  title: string;
  description: string;
  hypothesis: number;
  evidence: Record<string, unknown>;
  created_at: string;
}

export interface Artifact {
  id: string;
  kind: string;
  filename: string;
  sha256: string;
  size: number;
  preview: string;
}

export interface RunDetail {
  run: Run;
  checks: CheckResult[];
  metrics: Metric[];
  findings: Finding[];
  artifacts: Artifact[];
  events: { id: number; ts: string; level: string; message: string }[];
  imports: { id: string; format: string; source_name: string; records: number }[];
}

let csrfToken = "";
export function setCsrf(token: string) {
  csrfToken = token;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (!headers.has("Content-Type") && options.body && !(options.body instanceof File)) {
    headers.set("Content-Type", "application/json");
  }
  if (csrfToken) headers.set("X-VerificaLab-CSRF", csrfToken);
  const res = await fetch(path, { ...options, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* corpo não-JSON */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  if (res.headers.get("content-type")?.includes("application/json")) {
    return res.json();
  }
  return res as unknown as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  del: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  upload: <T>(path: string, file: File) =>
    request<T>(path, { method: "POST", body: file }),
};

export const fmt = {
  date(iso: string | null): string {
    if (!iso) return "—";
    try {
      return new Date(iso).toLocaleString("pt-BR");
    } catch {
      return iso;
    }
  },
  num(v: number | null | undefined, digits = 2): string {
    if (v === null || v === undefined) return "desconhecido";
    return Number(v).toFixed(digits).replace(/\.?0+$/, "") || "0";
  },
};
