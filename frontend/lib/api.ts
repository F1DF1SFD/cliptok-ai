import { assetPath } from "@/lib/base-path";
import { DEMO_MODE, DemoRestriction, demoApi } from "@/lib/demo";
import type {
  Health,
  Job,
  Project,
  PublicShare,
  RenderSettings,
  ShareInfo,
  Sticker,
} from "@/lib/types";

/**
 * Empty by default: the studio calls its own origin and Next proxies /api to the
 * backend, so one URL works from localhost, a LAN address or a tunnel.
 * Set NEXT_PUBLIC_API_URL to talk to the API directly (two-port development).
 */
export const API_BASE = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      cache: "no-store",
      headers: {
        ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
        ...(init?.headers ?? {}),
      },
    });
  } catch {
    throw new ApiError(
      `Can't reach the ClipTok API at ${API_BASE || "this server"}. Start the backend and try again.`,
      0,
    );
  }

  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const payload = await response.json();
      if (typeof payload?.detail === "string") detail = payload.detail;
      else if (Array.isArray(payload?.detail)) detail = payload.detail[0]?.msg ?? detail;
    } catch {
      /* keep default message */
    }
    throw new ApiError(detail, response.status);
  }

  if (response.status === 204) return undefined as T;
  const text = await response.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

export function mediaUrl(path: string | null | undefined): string | undefined {
  if (!path) return undefined;
  if (path.startsWith("http")) return path;
  // Demo builds serve the sample media as static files next to the app.
  if (DEMO_MODE) return assetPath(path);
  return `${API_BASE}${path}`;
}

/** Anything that needs the Python pipeline is unavailable in a static demo. */
function needsPipeline(): never {
  throw new DemoRestriction();
}

export const api = {
  health: () => (DEMO_MODE ? demoApi.health() : request<Health>("/api/health")),
  listProjects: () => (DEMO_MODE ? demoApi.listProjects() : request<Project[]>("/api/projects")),
  getProject: (id: string) =>
    DEMO_MODE ? demoApi.getProject(id) : request<Project>(`/api/projects/${id}`),
  updateProject: (id: string, payload: { name?: string; settings?: RenderSettings }) =>
    DEMO_MODE
      ? demoApi.updateProject(id, payload)
      : request<Project>(`/api/projects/${id}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        }),
  deleteProject: (id: string) =>
    DEMO_MODE ? needsPipeline() : request<void>(`/api/projects/${id}`, { method: "DELETE" }),
  importTwitch: (url: string) =>
    DEMO_MODE
      ? needsPipeline()
      : request<Project>("/api/projects/import", {
          method: "POST",
          body: JSON.stringify({ url }),
        }),
  upload: async (file: File, onProgress?: (percent: number) => void) => {
    if (DEMO_MODE) needsPipeline();
    // Use XHR so the import card can show real upload progress.
    return new Promise<Project>((resolve, reject) => {
      const form = new FormData();
      form.append("file", file);
      const xhr = new XMLHttpRequest();
      xhr.open("POST", `${API_BASE}/api/projects/upload`);
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable && onProgress) {
          onProgress(Math.round((event.loaded / event.total) * 100));
        }
      };
      xhr.onload = () => {
        try {
          const payload = JSON.parse(xhr.responseText || "{}");
          if (xhr.status >= 200 && xhr.status < 300) resolve(payload as Project);
          else reject(new ApiError(payload?.detail ?? "Upload failed", xhr.status));
        } catch {
          reject(new ApiError("Upload failed", xhr.status));
        }
      };
      xhr.onerror = () => reject(new ApiError("Upload failed — check your connection.", 0));
      xhr.send(form);
    });
  },
  uploadMusic: (id: string, file: File) => {
    if (DEMO_MODE) return needsPipeline();
    const form = new FormData();
    form.append("file", file);
    return request<Project>(`/api/projects/${id}/music`, { method: "POST", body: form });
  },
  removeMusic: (id: string) =>
    DEMO_MODE ? needsPipeline() : request<Project>(`/api/projects/${id}/music`, { method: "DELETE" }),
  transcribe: (id: string) =>
    DEMO_MODE ? needsPipeline() : request<Job>(`/api/projects/${id}/transcribe`, { method: "POST" }),
  analyze: (id: string) =>
    DEMO_MODE ? needsPipeline() : request<Job>(`/api/projects/${id}/analyze`, { method: "POST" }),
  render: (id: string, quality: "preview" | "final") =>
    DEMO_MODE
      ? needsPipeline()
      : request<Job>(`/api/projects/${id}/render`, {
          method: "POST",
          body: JSON.stringify({ quality }),
        }),
  getJob: (jobId: string) => request<Job>(`/api/jobs/${jobId}`),
  share: (id: string) =>
    DEMO_MODE
      ? demoApi.share()
      : request<{ share: ShareInfo }>(`/api/projects/${id}/share`, {
          method: "POST",
          body: JSON.stringify({ quality: "auto" }),
        }),
  unshare: (id: string) =>
    DEMO_MODE
      ? demoApi.unshare()
      : request<void>(`/api/projects/${id}/share`, { method: "DELETE" }),
  shareInfo: (slug: string) => request<PublicShare>(`/api/share/${slug}`),
  stickers: () => (DEMO_MODE ? demoApi.stickers() : request<{ stickers: Sticker[] }>("/api/stickers")),
};

export { DemoRestriction };
