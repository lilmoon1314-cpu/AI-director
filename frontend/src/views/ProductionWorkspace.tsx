import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Link, NavLink, useLocation, useParams } from "react-router-dom";

import { api } from "../api/client";
import { useProjectStore } from "../stores/projectStore";

const STAGES = [
  ["overview", "概览"], ["script", "剧本"], ["production", "表演与制作"],
  ["shots", "镜头"], ["timing", "粗配音与时长"], ["storyboard", "故事板"],
  ["director", "导演预演"], ["timeline", "时间轴"], ["generate", "生成"], ["review", "审查"],
] as const;
const DOCUMENT_NAMES: Record<string, string> = {
  screenplay: "剧本", production_breakdown: "制作拆解", performance_script: "表演脚本",
  shot_plan: "镜头计划", storyboard: "故事板", timeline: "时间轴文档",
};
const linkStyle = "rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-800 transition hover:border-teal-600 hover:bg-teal-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100";

/** URL-keyed shell: a late result from an old scope can never render in the new one. */
export function ProductionWorkspace() {
  const { pathname } = useLocation();
  return <WorkspacePage key={pathname} />;
}

function Resource<T>({ load, children }: { load: () => Promise<T>; children: (data: T) => ReactNode }) {
  const [state, setState] = useState<{ data?: T; error?: string }>({});
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    setState({});
    void load().then(
      (data) => { if (active) setState({ data }); },
      (error: unknown) => { if (active) setState({ error: error instanceof Error ? error.message : "读取失败" }); },
    );
    return () => { active = false; };
  }, [load, attempt]);
  if (state.error) return <div role="alert" className="rounded-xl bg-amber-50 p-5 text-slate-800">
    <p>无法读取当前范围：{state.error}</p>
    <p className="my-2 text-sm">检查项目、系列和剧集地址，或重试连接。</p>
    <button className="underline" onClick={() => setAttempt(attempt + 1)}>重试</button>
  </div>;
  if (state.data === undefined) return <p role="status" className="p-5 text-slate-500">正在读取工作区…</p>;
  return children(state.data);
}

function PageList<T>({ load, empty, children }: {
  load: (offset: number) => Promise<T[]>; empty: string; children: (items: T[]) => ReactNode;
}) {
  const [offset, setOffset] = useState(0);
  const fetchPage = useCallback(() => load(offset), [load, offset]);
  return <Resource key={offset} load={fetchPage}>{(items) => <>
    {items.length ? children(items) : <p className="rounded-xl border border-dashed border-slate-300 p-6 text-slate-500">{empty}</p>}
    {(offset > 0 || items.length === 20) && <div className="mt-4 flex items-center gap-4 text-sm">
      <button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 20))} className="disabled:opacity-40">上一页</button>
      <span>第 {offset / 20 + 1} 页</span>
      <button disabled={items.length < 20} onClick={() => setOffset(offset + 20)} className="disabled:opacity-40">下一页</button>
    </div>}
  </>}</Resource>;
}

function WorkspacePage() {
  const { projectId = "", seriesId, episodeId } = useParams();
  const { pathname } = useLocation();
  const project = useProjectStore((state) => state.projects.find((item) => item.id === projectId));
  const base = `/projects/${encodeURIComponent(projectId)}`;
  const seriesBase = `${base}/series/${encodeURIComponent(seriesId ?? "")}`;
  const episodeBase = `${seriesBase}/episodes/${encodeURIComponent(episodeId ?? "")}`;
  const section = pathname.split("/").at(-1) ?? "overview";
  const loadScope = useCallback(async () => {
    if (!seriesId) return { series: null, episode: null };
    const series = await api.getSeries(projectId, seriesId);
    const episode = episodeId ? await api.getEpisode(projectId, seriesId, episodeId) : null;
    return { series, episode };
  }, [projectId, seriesId, episodeId]);
  const loadSeries = useCallback((offset: number) => api.listSeries(projectId, offset), [projectId]);
  const loadEpisodes = useCallback((offset: number) => api.listEpisodes(projectId, seriesId!, offset), [projectId, seriesId]);
  const loadDocuments = useCallback((offset: number) => api.listProductionDocuments(projectId, episodeId!, offset), [projectId, episodeId]);
  const creative = pathname.includes("/create");
  const creativeLabels: Record<string, string> = { create: "创作", visual: "视觉资产", sound: "声音设计", story: "故事规划" };

  return <main className="min-w-0 flex-1 overflow-auto rounded-2xl bg-white/80 p-6 text-slate-800 dark:bg-slate-900/80 dark:text-slate-100" data-testid="production-workspace">
    <Resource load={loadScope}>{({ series, episode }) => <>
      <nav aria-label="当前创作范围" className="mb-6 flex flex-wrap items-center gap-2 text-sm text-slate-500" data-testid="scope-bar">
        <Link to={`${base}/overview`}>{project?.name ?? "当前项目"}</Link>
        <span>/</span><Link to={`${base}/${creative ? "create" : "series"}`}>{creative ? "创作" : "系列与剧集"}</Link>
        {series && <><span>/</span><Link to={`${seriesBase}/overview`}>{series.title}</Link></>}
        {episode && <><span>/</span><Link to={`${episodeBase}/overview`}>{episode.title}</Link></>}
      </nav>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div><p className="mb-2 text-xs font-semibold uppercase tracking-widest text-teal-700">创作工作台</p>
          <h1 className="text-2xl font-semibold">{episode?.title ?? series?.title ?? (creative ? creativeLabels[section] ?? "创作" : section === "series" ? "系列与剧集" : "项目概览")}</h1>
        </div>
        <Link className="text-sm text-teal-700 underline" to={`${base}/agent`}>打开创作助手</Link>
      </div>

      {episode && <details className="mb-6 rounded-xl border border-slate-200 p-3 dark:border-slate-700">
        <summary className="cursor-pointer text-sm font-medium">制作流程 · {STAGES.find(([path]) => path === section)?.[1]}</summary>
        <nav aria-label="剧集制作流程" className="mt-3 flex flex-wrap gap-2" data-testid="production-rail">
        {STAGES.map(([path, label]) => <NavLink key={path} to={`${episodeBase}/${path}`} className={({ isActive }) => `rounded-lg px-3 py-2 text-sm ${isActive ? "bg-teal-800 text-white" : "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300"}`}>{label}</NavLink>)}
      </nav></details>}

      <div className="mb-6 grid gap-3 md:grid-cols-3">
        <Summary title="当前阶段">{episode ? `剧集规划 · ${episode.status === "draft" ? "草稿" : episode.status}` : "工作区准备"}<p className="mt-2 text-xs text-slate-500">生产阶段尚未判定，已有文档不代表已批准。</p></Summary>
        <Summary title="下一动作"><Link className="text-teal-700 underline" to={episode ? `${episodeBase}/script` : series ? `${seriesBase}/episodes` : `${base}/series`}>{episode ? "查看剧本文档记录" : series ? "选择一个剧集" : "查看系列与剧集"}</Link><p className="mt-2 text-xs text-slate-500">也可以继续整理世界观与参考资料。</p></Summary>
        <Summary title="阻断与待开放"><p>生产放行与审查尚未接入</p><p className="mt-2 text-xs text-slate-500">目前可浏览规划与文档记录；编辑、批准与生成入口待开放。</p></Summary>
      </div>

      {creative ? <>
        <div className="mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Link className={linkStyle} to={`${base}/create/world`}>世界与人物图谱 →</Link>
          <Link className={linkStyle} to={`${base}/create/visual`}>视觉资产 →</Link>
          <Link className={linkStyle} to={`${base}/create/sound`}>声音设计 →</Link>
          <Link className={linkStyle} to={`${base}/create/story`}>故事规划 →</Link>
        </div>
        <p className="text-sm text-slate-500">{section === "visual" ? "视觉资产工作区待开放：未来可在一个资产页面管理合同、提示词、图片与历史。当前可先整理参考图片。" : "世界与人物图谱已可使用；视觉、声音与故事专用工作区将逐步开放。"}</p>
        <Link className="mt-4 inline-block text-sm text-teal-700 underline" to={`${base}/assets`}>浏览参考资料</Link>
      </> : episode ? <>
        {section !== "overview" && <h2 className="mb-3 text-lg font-medium">{STAGES.find(([path]) => path === section)?.[1]} · 浏览入口</h2>}
        {episode.outline && section === "overview" && <div className="mb-6"><h2 className="mb-2 font-medium">剧集大纲</h2><p className="whitespace-pre-wrap text-sm">{episode.outline}</p></div>}
        <h2 className="mb-3 font-medium">已有生产文档记录</h2>
        <p className="mb-3 text-sm text-slate-500">下列记录来自当前剧集。制作编辑器尚未开放；时间轴文档不代表可播放时间轴。</p>
        <PageList load={loadDocuments} empty="当前剧集还没有生产文档记录。">{(items) => <ul className="grid gap-2">{items.map((item) => <li key={item.id} className={linkStyle}>
          <span>{DOCUMENT_NAMES[item.document_type] ?? item.document_type}</span><span className="ml-3 text-xs text-slate-500">已保存记录 · {new Date(item.created_at).toLocaleDateString()}</span>
        </li>)}</ul>}</PageList>
      </> : series ? <PageList load={loadEpisodes} empty="这个系列还没有剧集。剧集规划编辑入口待开放。">{(items) => <div className="grid gap-3 sm:grid-cols-2">{items.map((item) => <Link className={linkStyle} key={item.id} to={`${seriesBase}/episodes/${encodeURIComponent(item.id)}/overview`}>
        <span className="mb-2 block text-xs text-teal-700">剧集 {item.position + 1}</span><span className="font-medium">{item.title}</span><p className="mt-2 text-xs text-slate-500">{item.status === "draft" ? "规划草稿" : item.status}</p>
      </Link>)}</div>}</PageList> : <>
        <h2 className="mb-3 font-medium">系列与剧集</h2>
        <PageList load={loadSeries} empty="当前项目还没有系列。你可以先整理世界观、人物和参考资料；系列规划编辑入口待开放。">{(items) => <div className="grid gap-3 sm:grid-cols-2">{items.map((item) => <Link className={linkStyle} key={item.id} to={`${base}/series/${encodeURIComponent(item.id)}/overview`}>{item.title}<span className="float-right">查看剧集 →</span></Link>)}</div>}</PageList>
        <div className="mt-6 flex flex-wrap gap-3"><Link className={linkStyle} to={`${base}/create/world`}>整理世界与人物</Link><Link className={linkStyle} to={`${base}/assets`}>浏览参考资料</Link></div>
      </>}
    </>}</Resource>
  </main>;
}

function Summary({ title, children }: { title: string; children: ReactNode }) {
  return <section className="rounded-xl border border-slate-200 p-4 dark:border-slate-700"><h2 className="mb-3 text-xs font-medium text-slate-500">{title}</h2><div className="text-sm">{children}</div></section>;
}
