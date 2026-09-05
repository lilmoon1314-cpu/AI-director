"""assets 模块文件存储层：上传校验、uuid 重命名、流式写盘与路径安全。

硬约束（assets/CONSTRAINTS.md）:
    - 类型白名单 + 大小上限（阈值来自 config，禁止硬编码）。
    - 流式分块写盘，禁止整文件读入内存。
    - 存储名 = {uuid}.{ext}，禁止用户文件名参与路径拼接；解析存储名时
      必须校验解析结果落在 ASSET_DIR 内（防路径穿越）。
"""

import uuid
from pathlib import Path

from app.core.exceptions import NotFoundError, ValidationError

# 流式写入块大小（内存防线：任意时刻至多一个块在内存）
CHUNK_SIZE = 1024 * 1024


def _ext_of(filename: str) -> str:
    """提取文件扩展名（小写，不含点）。

    作用: 白名单校验的输入归一化。
    参数: filename — 用户提供的原始文件名。返回值: 扩展名（可为空串）。异常: 无。依赖: pathlib。
    """
    return Path(filename).suffix.lower().lstrip(".")


def validate_upload(
    *,
    filename: str,
    content_type: str,
    max_size_bytes: int,
    allowed_extensions: list[str],
) -> str:
    """校验上传文件（仅图片：MIME 前缀 + 扩展名白名单）。

    作用: 上传前置校验，返回归一化扩展名供重命名使用。
    参数:
        filename — 原始文件名；content_type — 客户端声明的 MIME；
        max_size_bytes — 大小上限；allowed_extensions — config 白名单（小写）。
    返回值: str — 小写扩展名。
    异常: ValidationError — MIME 非 image/*、扩展名不在白名单（三要素完整）。
    依赖: app.core.exceptions。
    """
    if not content_type.startswith("image/"):
        raise ValidationError(
            problem="上传文件类型不被接受",
            cause=f"仅接受图片（MIME 需以 image/ 开头），实际收到 '{content_type}'",
            fix=f"请上传图片文件，支持格式：{', '.join(allowed_extensions)}",
            detail={"content_type": content_type},
        )
    ext = _ext_of(filename)
    if ext not in allowed_extensions:
        raise ValidationError(
            problem="上传文件扩展名不在白名单",
            cause=f"扩展名 '{ext or '(缺失)'}' 不在允许列表 [{', '.join(allowed_extensions)}] 内",
            fix=f"请上传白名单内的图片格式：{', '.join(allowed_extensions)}",
            detail={"extension": ext, "allowed": allowed_extensions},
        )
    return ext


def build_stored_name(ext: str) -> str:
    """生成存储文件名（uuid 重命名，用户输入零参与）。

    作用: 满足「存储名 = {uuid}.{ext}」约束（防路径穿越与重名覆盖）。
    参数: ext — 已通过白名单校验的小写扩展名。
    返回值: str — 形如 "a1b2c3d4e5f6....png"。异常: 无。依赖: uuid。
    """
    return f"{uuid.uuid4().hex}.{ext}"


def resolve_stored_path(stored_name: str, asset_dir: str) -> Path:
    """把存储名解析为 ASSET_DIR 内的物理路径（路径穿越防线）。

    作用: 静态删除/校验场景的唯一取径入口——剥离任何目录成分，
        并断言解析结果落在 ASSET_DIR 内。
    参数: stored_name — 库内存储名；asset_dir — 资产目录（config）。
    返回值: Path — 物理路径。
    异常: ValidationError — 解析结果越出 ASSET_DIR（防穿越兜底）。
    依赖: pathlib。
    """
    root = Path(asset_dir).resolve()
    if Path(stored_name).name != stored_name or ".." in stored_name:
        # 存储名一律由 build_stored_name 生成（纯 uuid.ext）；出现目录成分即为脏数据，
        # 显式拒绝而非静默剥离（纵深防御，越界企图不应被无声吞掉）
        raise ValidationError(
            problem="资产存储名非法",
            cause=f"存储名 '{stored_name}' 含目录成分或相对路径片段",
            fix="存储名只能来自库内 asset_images.stored_name（uuid.ext），禁止拼接用户输入",
            detail={"stored_name": stored_name},
        )
    candidate = (root / stored_name).resolve()
    if not candidate.is_relative_to(root):
        raise ValidationError(
            problem="资产存储路径非法",
            cause=f"存储名 '{stored_name}' 解析后越出资产目录",
            fix="仅允许访问 ASSET_DIR 内的文件；请检查存储名来源",
            detail={"stored_name": stored_name},
        )
    return candidate


async def write_stream(upload: object, dest: Path, max_size_bytes: int) -> int:
    """分块流式写入上传体到目标路径（含大小上限强制）。

    作用:
        上传落盘的唯一入口：逐块读取（CHUNK_SIZE）写入，累计超限立即中止、
        删除半成品文件并抛错——满足「禁止整文件读入内存」硬约束。
    参数:
        upload — 提供 async read(n) 的上传对象（fastapi UploadFile 兼容）；
        dest — 目标物理路径；max_size_bytes — 大小上限。
    返回值: int — 实际写入字节数。
    异常: ValidationError — 写入累计超过上限（三要素完整）。
    依赖: 无（标准文件 IO）。
    """
    written = 0
    with dest.open("wb") as out:
        while True:
            chunk = await upload.read(CHUNK_SIZE)  # type: ignore[attr-defined]
            if not chunk:
                break
            written += len(chunk)
            if written > max_size_bytes:
                out.close()
                dest.unlink(missing_ok=True)
                raise ValidationError(
                    problem="上传文件超过大小上限",
                    cause=f"写入累计 {written} 字节，超过上限 {max_size_bytes} 字节",
                    fix=f"压缩或裁剪文件至 {max_size_bytes // (1024 * 1024)}MB 以内后重试",
                    detail={"written": written, "max_size_bytes": max_size_bytes},
                )
            out.write(chunk)
    return written


def delete_stored_file(stored_name: str, asset_dir: str) -> None:
    """删除资产目录内的物理文件（经路径穿越防线解析）。

    作用: 图片/资产删除与孤儿清扫的文件清理入口；文件不存在时静默跳过。
    参数: stored_name — 库内存储名；asset_dir — 资产目录（config）。
    返回值: 无。
    异常: ValidationError — 路径越界（resolve_stored_path 兜底）。
    依赖: resolve_stored_path。
    """
    path = resolve_stored_path(stored_name, asset_dir)
    path.unlink(missing_ok=True)


def stored_file_exists(stored_name: str, asset_dir: str) -> bool:
    """检查存储名对应的物理文件是否存在（经路径穿越防线解析）。

    作用: 静态访问兜底 404 的判断入口。
    参数: stored_name — 库内存储名；asset_dir — 资产目录（config）。
    返回值: bool。异常: ValidationError — 路径越界。依赖: resolve_stored_path。
    """
    return resolve_stored_path(stored_name, asset_dir).exists()


def not_found(stored_name: str) -> NotFoundError:
    """构造图片文件不存在的三要素异常。

    作用: 统一 404 消息质量。
    参数: stored_name — 存储名。返回值: NotFoundError。异常: 无。依赖: app.core.exceptions。
    """
    return NotFoundError(
        problem="图片文件不存在",
        cause=f"存储名 '{stored_name}' 对应的文件不在资产目录中",
        fix="确认文件未被手动删除，或重新上传图片",
        detail={"stored_name": stored_name},
    )
