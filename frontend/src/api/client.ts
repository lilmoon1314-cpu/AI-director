/**
 * API 请求客户端：类型全部来自 openapi-typescript 生成的 schema（禁止手写重复类型，
 * frontend/CONSTRAINTS.md「API 契约」）；base URL 经 VITE_API_BASE 注入（禁硬编码）。
 */

import type { components } from "./schema";

export type EntityBrief = components["schemas"]["EntityBrief"];
export type EntityCreate = components["schemas"]["EntityCreate"];
export type EntityRead = components["schemas"]["EntityRead"];
export type EntityUpdate = components["schemas"]["EntityUpdate"];
export type RelationCreate = components["schemas"]["RelationCreate"];
export type RelationRead = components["schemas"]["RelationRead"];
export type RelationUpdate = components["schemas"]["RelationUpdate"];
export type GraphData = components["schemas"]["GraphData"];

/** 拼接 base 与 path（两侧冗余斜杠归一，边界：base 尾斜杠不影响结果）。 */
export function joinUrl(base: string, path: string): string {
  return `${base.replace(/\/+$/, "")}/${path.replace(/^\/+/, "")}`;
}

export const API_BASE: string =
  (import.meta.env.VITE_API_BASE as string | undefined) ?? "/api";

/** 后端 AppError 统一结构的客户端镜像（三要素：什么出了问题/为什么/怎么修）。 */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly problem: string;
  readonly cause: string;
  readonly fix: string;

  constructor(status: number, body: { code?: string; problem?: string; cause?: string; fix?: string }) {
    super(body.problem ?? `请求失败（HTTP ${status}）`);
    this.name = "ApiError";
    this.status = status;
    this.code = body.code ?? "UNKNOWN";
    this.problem = body.problem ?? `请求失败（HTTP ${status}）`;
    this.cause = body.cause ?? "服务端未返回原因说明";
    this.fix = body.fix ?? "检查请求参数与服务端日志";
  }
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  let resp: Response;
  try {
    resp = await fetch(joinUrl(API_BASE, path), {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch (cause) {
    throw new ApiError(0, {
      code: "NETWORK_ERROR",
      problem: "无法连接服务器",
      cause: String(cause),
      fix: "确认后端服务已启动（make dev-backend）后重试",
    });
  }
  if (!resp.ok) {
    let body: Record<string, unknown> = {};
    try {
      body = (await resp.json()) as Record<string, unknown>;
    } catch {
      // 非 JSON 错误体（如代理层错误页）→ 用占位三要素
    }
    throw new ApiError(resp.status, body);
  }
  if (resp.status === 204) {
    return undefined as T;
  }
  return (await resp.json()) as T;
}

/** 后端 REST 端点的类型化封装（路径总表见 backend/ARCHITECTURE.md §7）。 */
export const api = {
  /** 三视角图查询（perspective 枚举与后端契约一致；character 视角必须携带角色 id）。 */
  getGraph: (perspective: "author" | "character" | "audience", characterId?: string) => {
    const params = new URLSearchParams({ perspective });
    if (characterId) params.set("character_id", characterId);
    return apiFetch<GraphData>(`/graph?${params.toString()}`);
  },
  getEntity: (id: string) => apiFetch<EntityRead>(`/entities/${id}`),
  /** 实体摘要检索（@ 选择器/角色下拉数据源；后端 GET /api/entities?q=&type=）。 */
  listEntities: (params?: { q?: string; type?: string }) => {
    const search = new URLSearchParams();
    if (params?.q) search.set("q", params.q);
    if (params?.type) search.set("type", params.type);
    const qs = search.toString();
    return apiFetch<EntityBrief[]>(`/entities${qs ? `?${qs}` : ""}`);
  },
  createEntity: (body: EntityCreate) =>
    apiFetch<EntityRead>("/entities", { method: "POST", body: JSON.stringify(body) }),
  updateEntity: (id: string, body: EntityUpdate) =>
    apiFetch<EntityRead>(`/entities/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteEntity: (id: string) => apiFetch<void>(`/entities/${id}`, { method: "DELETE" }),
  listRelations: () => apiFetch<RelationRead[]>("/relations"),
  createRelation: (body: RelationCreate) =>
    apiFetch<RelationRead>("/relations", { method: "POST", body: JSON.stringify(body) }),
  updateRelation: (id: string, body: RelationUpdate) =>
    apiFetch<RelationRead>(`/relations/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteRelation: (id: string) => apiFetch<void>(`/relations/${id}`, { method: "DELETE" }),
};
