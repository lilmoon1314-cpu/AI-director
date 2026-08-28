// 负载验收 globalSetup：**空操作占位**（Playwright 顺序为 webServer 先起、
// globalSetup 后跑——此处不能杀进程/删库：杀会误伤本轮 8010 uvicorn，
// 删库会被本轮 uvicorn 占用而失败）。
// 残留进程清理在 load 配置 webServer command 的前置 taskkill 中完成（彼时
// 本轮 uvicorn 尚未启动，杀全部 uvicorn 安全）；旧库数据兜底由负载 spec 内
// resetWorld 经 API 逐删（幂等，不依赖库初始状态）。
export default async function globalSetup(): Promise<void> {}
