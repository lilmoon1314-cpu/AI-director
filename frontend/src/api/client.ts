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
export type AssetCard = components["schemas"]["AssetCard"];
export type AssetRead = components["schemas"]["AssetRead"];
export type AssetImageRead = components["schemas"]["AssetImageRead"];
export type EntityAssetCard = components["schemas"]["EntityAssetCard"];
export type GeneralAssetCreate = components["schemas"]["GeneralAssetCreate"];
export type GeneralAssetUpdate = components["schemas"]["GeneralAssetUpdate"];
export type ProjectRead = components["schemas"]["ProjectRead"];
export type ProjectCreate = components["schemas"]["ProjectCreate"];
export type ProjectUpdate = components["schemas"]["ProjectUpdate"];
export type SessionRead = components["schemas"]["SessionRead"];
export type MessageRead = components["schemas"]["MessageRead"];
export type DraftItem = components["schemas"]["DraftItem"];
export type ProposeResponse = components["schemas"]["ProposeResponse"];
export type ConfirmResponse = components["schemas"]["ConfirmResponse"];
export type MemoryDocBrief = components["schemas"]["MemoryDocBrief"];
export type MemoryDocRead = components["schemas"]["MemoryDocRead"];
export type MemoryDocSectionRead = components["schemas"]["MemoryDocSectionRead"];

/** 拼接 base 与 path（两侧冗余斜杠归一，边界：base 尾斜杠不影响结果）。 */
export function joinUrl(base: string, path: string): string {
  return `${base.replace(/\/+$/, "")}/${path.replace(/^\/+/, "")}`;
}

export const API_BASE: string =
  (import.meta.env.VITE_API_BASE as string | undefined) ?? "/api";

/** 默认项目 id（后端 projects.service.DEFAULT_PROJECT_ID 的前端镜像——
 * lifespan 恒播种、不可删除；切换器/首屏/测试共用，禁止散落字面量）。 */
export const DEFAULT_PROJECT_ID = "project-default";

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
  const isFormData = init?.body instanceof FormData;
  let resp: Response;
  try {
    resp = await fetch(joinUrl(API_BASE, path), {
      headers: { "Content-Type": "application/json" },
      ...init,
      // multipart 由浏览器自动生成含 boundary 的 Content-Type，禁止手动覆盖
      ...(isFormData ? { headers: undefined } : {}),
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
  // ---- 项目（F11 多项目底座；DESIGN.md §8.4 查询参数渐进迁移）----
  /** 项目列表（按最近活跃倒序；项目首屏与顶栏切换器数据源）。 */
  listProjects: () => apiFetch<ProjectRead[]>("/projects"),
  createProject: (body: ProjectCreate) =>
    apiFetch<ProjectRead>("/projects", { method: "POST", body: JSON.stringify(body) }),
  updateProject: (id: string, body: ProjectUpdate) =>
    apiFetch<ProjectRead>(`/projects/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteProject: (id: string) => apiFetch<void>(`/projects/${id}`, { method: "DELETE" }),
  /** 三视角图查询（perspective 枚举与后端契约一致；character 视角必须携带角色 id；
   *  project_id 缺省=默认项目——工作台内恒传当前项目）。 */
  getGraph: (
    perspective: "author" | "character" | "audience",
    characterId?: string,
    projectId?: string,
  ) => {
    const params = new URLSearchParams({ perspective });
    if (characterId) params.set("character_id", characterId);
    if (projectId) params.set("project_id", projectId);
    return apiFetch<GraphData>(`/graph?${params.toString()}`);
  },
  getEntity: (id: string) => apiFetch<EntityRead>(`/entities/${id}`),
  /** 实体摘要检索（@ 选择器/角色下拉数据源；project_id 过滤项目归属，缺省=全库）。 */
  listEntities: (params?: { q?: string; type?: string; project_id?: string }) => {
    const search = new URLSearchParams();
    if (params?.q) search.set("q", params.q);
    if (params?.type) search.set("type", params.type);
    if (params?.project_id) search.set("project_id", params.project_id);
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
  // ---- 资产管理（F08；路由总表见 backend/app/assets/ARCHITECTURE.md）----
  /** 图片上传（multipart；scope='general'|'entity'，owner_id 为资产 id 或实体 id）。 */
  uploadImage: (scope: "general" | "entity", ownerId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    form.append("scope", scope);
    form.append("owner_id", ownerId);
    return apiFetch<AssetImageRead>("/assets/images", { method: "POST", body: form });
  },
  /** 图片明细列表（实体详情面板图片区/通用资产编辑表单数据源）。 */
  listImages: (scope: "general" | "entity", ownerId: string) => {
    const params = new URLSearchParams({ scope, owner_id: ownerId });
    return apiFetch<AssetImageRead[]>(`/assets/images?${params.toString()}`);
  },
  deleteImage: (imageId: string) =>
    apiFetch<void>(`/assets/images/${imageId}`, { method: "DELETE" }),
  listGeneralAssets: (category?: string) => {
    const search = new URLSearchParams();
    if (category) search.set("category", category);
    const qs = search.toString();
    return apiFetch<AssetCard[]>(`/assets/general${qs ? `?${qs}` : ""}`);
  },
  createGeneralAsset: (body: GeneralAssetCreate) =>
    apiFetch<AssetRead>("/assets/general", { method: "POST", body: JSON.stringify(body) }),
  /** 通用资产详情（含图片明细；编辑表单数据源）。 */
  getGeneralAsset: (id: string) => apiFetch<AssetRead>(`/assets/general/${id}`),
  updateGeneralAsset: (id: string, body: GeneralAssetUpdate) =>
    apiFetch<AssetRead>(`/assets/general/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteGeneralAsset: (id: string) =>
    apiFetch<void>(`/assets/general/${id}`, { method: "DELETE" }),
  setAssetCover: (id: string, imageId: string) =>
    apiFetch<AssetRead>(`/assets/general/${id}/cover`, {
      method: "PUT",
      body: JSON.stringify({ image_id: imageId }),
    }),
  /** 项目资产卡片（主库实体按类型分组，封面对照资产库；随项目隔离）。 */
  listEntityCards: (projectId?: string) => {
    const search = new URLSearchParams();
    if (projectId) search.set("project_id", projectId);
    const qs = search.toString();
    return apiFetch<EntityAssetCard[]>(`/assets/entities${qs ? `?${qs}` : ""}`);
  },
  /** 资产 HTML 页地址（iframe src 用，不 fetch——后端返回 text/html）。 */
  assetPageUrl: (kind: "general" | "entity", id: string) =>
    kind === "general" ? joinUrl(API_BASE, `/assets/general/${id}/page`) : joinUrl(API_BASE, `/assets/entity/${id}/page`),
  // ---- Agent（F10；DESIGN.md §5.4/§8.3，project_id 查询参数渐进迁移约定）----
  /** 创建会话（project_id 空=默认项目——工作台内恒显式携带）。 */
  createSession: (projectId: string) =>
    apiFetch<SessionRead>(
      `/agent/sessions?${new URLSearchParams({ project_id: projectId }).toString()}`,
      { method: "POST", body: JSON.stringify({}) },
    ),
  listSessions: (projectId: string) =>
    apiFetch<SessionRead[]>(
      `/agent/sessions?${new URLSearchParams({ project_id: projectId }).toString()}`,
    ),
  listMessages: (conversationId: string) =>
    apiFetch<MessageRead[]>(`/agent/sessions/${conversationId}/messages`),
  propose: (body: { session_id: string; message: string; perspective: string; character_id?: string }) =>
    apiFetch<ProposeResponse>("/agent/propose", { method: "POST", body: JSON.stringify(body) }),
  confirmDrafts: (body: {
    session_id: string;
    items: { draft_id: string; kind: "entity" | "relation"; payload: Record<string, unknown>; confirmed: boolean }[];
  }) => apiFetch<ConfirmResponse>("/agent/confirm", { method: "POST", body: JSON.stringify(body) }),
  createMemoryDoc: (kind: string, projectId: string) =>
    apiFetch<MemoryDocRead>(
      `/agent/memory-docs?${new URLSearchParams({ kind, project_id: projectId }).toString()}`,
      { method: "POST" },
    ),
  listMemoryDocs: (projectId: string) =>
    apiFetch<MemoryDocBrief[]>(
      `/agent/memory-docs?${new URLSearchParams({ project_id: projectId }).toString()}`,
    ),
  getMemoryDoc: (id: string) => apiFetch<MemoryDocRead>(`/agent/memory-docs/${id}`),
  deleteMemoryDoc: (id: string) =>
    apiFetch<void>(`/agent/memory-docs/${id}`, { method: "DELETE" }),
  updateMemoryDocSection: (
    docId: string,
    sectionId: string,
    body: { content: string; expected_version: number },
    updatedBy: "user" | "agent" = "user",
  ) =>
    apiFetch<MemoryDocSectionRead>(
      `/agent/memory-docs/${docId}/sections/${sectionId}?${new URLSearchParams({ updated_by: updatedBy }).toString()}`,
      { method: "PATCH", body: JSON.stringify(body) },
    ),
  /** 记忆文档 HTML 页地址（iframe 预览用，不 fetch——后端返回 text/html）。 */
  memoryDocPageUrl: (id: string) => joinUrl(API_BASE, `/agent/memory-docs/${id}/page`),
};

/** Agent 对话 SSE 端点路径（fetch 流式读取用；POST + body 不适用 EventSource）。 */
export function agentChatPath(): string {
  return joinUrl(API_BASE, "/agent/chat");
}
