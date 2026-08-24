/** 根组件：F01 阶段为占位工作台（毛玻璃卡片），F05 起替换为图谱工作台视图。 */
function App() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100">
      <div className="rounded-2xl border border-white/60 bg-white/60 px-12 py-10 text-center shadow-xl backdrop-blur-xl">
        <h1 className="text-3xl font-semibold tracking-tight text-slate-900">
          影视世界观工作台
        </h1>
        <p className="mt-3 text-sm text-slate-600">
          实体 · 关系 · 三视角图谱 —— 项目骨架已就绪（F01）
        </p>
      </div>
    </div>
  );
}

export default App;
