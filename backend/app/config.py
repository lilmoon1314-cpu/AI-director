"""应用配置：唯一有权读取环境变量 / .env 的模块（禁止任何硬编码配置）。"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置模型。

    作用:
        集中承载全部可配置项；字段名与 .env 中的同名大写变量一一对应，
        未在 .env 中出现的项使用此处默认值。
    参数:
        无（由环境变量 / .env 文件注入，见 .env.example）。
    返回值:
        无（配置类定义）。
    异常:
        pydantic.ValidationError — 环境变量类型不合法（如数字位填了文字）时抛出。
    依赖:
        pydantic-settings。
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- 应用 ---
    app_name: str = "AI Director"

    # --- 数据库 ---
    database_url: str = "sqlite+aiosqlite:///data/app.db"
    # 独立资产库（assets 模块专用，DECISIONS 2026-09-05：启动 create_all 幂等引导）
    asset_db_url: str = "sqlite+aiosqlite:///data/assets.db"

    # --- 资产上传 ---
    asset_dir: str = "data/assets"
    asset_max_size_mb: int = 10
    asset_allowed_types: str = "png,jpg,jpeg,gif,webp"

    # --- LLM（OpenAI 兼容协议）---
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    # 轻量模型：摘要等辅助任务路由（成本分级，F10）
    llm_model_light: str = "gpt-4o-mini"
    llm_timeout_seconds: int = 60

    # --- Agent（F10 对话底座）---
    # 单轮对话上下文硬预算（近似 tokens；超限按裁剪顺序降级，见 agent/prompts.py）
    agent_context_max_tokens: int = 8000
    # 近期消息全量注入窗口（条）；超窗最旧消息压缩进会话摘要
    agent_history_window_messages: int = 20
    # 受控 ReAct：每条用户消息允许的工具调用配额
    agent_max_tool_calls_per_turn: int = 4
    # 单次工具输出注入上下文的截断上限（字符）
    agent_tool_output_max_chars: int = 2000
    # 内容合规 hook 开关（MVP 本地敏感词表实现，预留外部审核 API 位）
    agent_content_review_enabled: bool = False
    # 敏感词表（逗号分隔；仅在 agent_content_review_enabled=true 时生效）
    agent_content_review_words: str = ""

    # --- 跨域 ---
    cors_origins: str = "http://localhost:5173"

    # --- 日志与信号采集 ---
    log_dir: str = "logs"
    log_level: str = "INFO"
    log_rotate_max_mb: int = 10
    log_rotate_backup_count: int = 5
    metric_sample_interval_seconds: int = 30
    memory_guard_threshold_mb: int = 100

    @property
    def cors_origin_list(self) -> list[str]:
        """跨域来源列表。

        作用: 将逗号分隔的 CORS_ORIGINS 解析为列表，供中间件使用。
        参数: 无。返回值: list[str]。异常: 无。依赖: 无。
        """
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def asset_allowed_type_list(self) -> list[str]:
        """资产类型白名单列表。

        作用: 将逗号分隔的 ASSET_ALLOWED_TYPES 解析为小写列表，供上传校验使用。
        参数: 无。返回值: list[str]。异常: 无。依赖: 无。
        """
        return [t.strip().lower() for t in self.asset_allowed_types.split(",") if t.strip()]


@lru_cache
def get_settings() -> Settings:
    """获取进程唯一的配置实例。

    作用:
        以缓存保证全进程共享同一份配置；测试可通过清理缓存 + 环境变量注入实现隔离。
    参数: 无。
    返回值: Settings 实例。
    异常: 无（底层 ValidationError 由调用方处理）。
    依赖: functools.lru_cache。
    """
    return Settings()
