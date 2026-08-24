from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from typing import Generator
import logging
import os

# 数据库配置：优先使用 Turso (libSQL)，回退到本地 SQLite
# Turso 环境变量：TURSO_DATABASE_URL 和 TURSO_AUTH_TOKEN
TURSO_URL = os.getenv("TURSO_DATABASE_URL")
TURSO_TOKEN = os.getenv("TURSO_AUTH_TOKEN")

# 是否使用 Turso 云数据库（全局标志，避免后面误调 sync）
USE_TURSO = bool(TURSO_URL and TURSO_TOKEN)

# Turso libSQL 原生连接（模块级单例）
# ⚠️ 重要：libsql embedded replica 模式下，commit 只写入本地缓存文件，
# 必须再调用 conn.sync() 才能把改动推送到云端（同时拉取云端最新数据）。
# 否则其他进程/连接读到的还是云端旧数据。
_libsql_conn = None


def _get_libsql_conn():
    """获取模块级缓存的 libsql 连接单例（embedded replica 模式）。

    首次调用时创建连接并从云端拉取最新数据，后续复用同一连接。
    缓存文件损坏（malformed）时自动删除缓存重建（云端是 source of truth）。
    """
    global _libsql_conn
    if _libsql_conn is None:
        import libsql_experimental as libsql
        # 缓存路径可用环境变量覆盖：并行进程（cron 脚本等）必须用独立缓存文件，
        # 多进程共享同一 embedded replica 缓存会导致文件损坏（malformed）。
        local_cache = os.environ.get(
            "TURSO_CACHE_PATH",
            os.path.join(os.path.dirname(__file__), "..", "turso_cache.db"),
        )
        try:
            _libsql_conn = libsql.connect(local_cache, sync_url=TURSO_URL, auth_token=TURSO_TOKEN)
            # 连接建立时先拉一次云端最新数据
            _libsql_conn.sync()
        except Exception as e:
            if "malformed" in str(e) or "corrupt" in str(e):
                # 缓存文件损坏：删除缓存三件套，从云端全量重建
                # （embedded replica 模式下云端是 source of truth，缓存随时可重建）
                logging.warning(f"turso 缓存损坏（{type(e).__name__}），删除缓存重建: {e}")
                _delete_local_cache()
                _libsql_conn = libsql.connect(local_cache, sync_url=TURSO_URL, auth_token=TURSO_TOKEN)
                _libsql_conn.sync()
            else:
                raise
    return _libsql_conn


def _delete_local_cache():
    """删除本地缓存文件（db/-wal/-shm/-info 四件套）。

    只删缓存文件不删云端数据；下次连接自动从云端全量拉取重建。
    删除失败（权限等）不抛错——重建路径会再次暴露问题。
    """
    base = os.environ.get(
        "TURSO_CACHE_PATH",
        os.path.join(os.path.dirname(__file__), "..", "turso_cache.db"),
    )
    for suffix in ["", "-wal", "-shm", "-info"]:
        p = base + suffix
        if os.path.exists(p):
            try:
                os.remove(p)
                logging.warning(f"已删除损坏缓存: {p}")
            except OSError as oe:
                logging.error(f"删除缓存失败 {p}: {oe}")


def _reset_libsql_conn(reason: str = ""):
    """重置 libsql 连接单例（连接失效时调用，下次访问会自动重建）。

    背景：Turso 的 Hrana 长连接闲置后会被云端掐掉，
    之后所有操作报 `ValueError: Hrana: stream not found`。
    模块级单例不会自愈，必须显式重建。

    同时 dispose SQLAlchemy engine，让 StaticPool 丢弃缓存的死连接，
    否则 engine 会继续复用已失效的连接对象。

    Args:
        reason: 触发重置的原因（用于日志排查）
    """
    global _libsql_conn
    if _libsql_conn is not None:
        try:
            _libsql_conn.close()
        except Exception:
            pass  # 死连接 close 失败无所谓，直接丢弃
        logging.warning(f"libsql 连接已重置{f'（{reason}）' if reason else ''}，下次访问将重建连接")
        _libsql_conn = None
    # dispose engine 缓存的连接（StaticPool 持有同一个死连接）
    eng = globals().get("engine")
    if eng is not None:
        try:
            eng.dispose()
        except Exception:
            pass


def _is_hrana_error(e: Exception) -> bool:
    """判断异常是否为 Hrana 连接失效（stream not found / Hrana api error）。

    这类错误的特征是连接对象已死但不会自愈，必须重建。
    """
    msg = str(e)
    return "stream not found" in msg or "Hrana" in msg


def _ensure_conn_alive():
    """请求前健康检查：Hrana 连接失效时自动重建（自愈）。

    背景：Turso Hrana 长连接闲置后被云端掐掉，之后所有 DB 操作
    （包括读）都会报 `Hrana: stream not found` 且不会自行恢复。
    每次请求前用一条轻量语句探测，失败则重置单例并立即重建。

    只在 Turso 模式且连接已初始化时生效；探测语句走本地缓存，
    正常情况下开销可忽略。非 Hrana 错误不处理，交给上层。
    """
    global _libsql_conn
    if not USE_TURSO or _libsql_conn is None:
        return
    try:
        _libsql_conn.execute("SELECT 1")
    except Exception as e:
        if _is_hrana_error(e):
            _reset_libsql_conn(f"健康检查探测失败: {type(e).__name__}")
            _get_libsql_conn()  # 立即重建；重建失败则抛错让上层感知
        elif "malformed" in str(e) or "corrupt" in str(e):
            # 缓存文件损坏（运行中损坏或外部进程写坏）：丢弃连接+删缓存+全量重建
            logging.warning(f"运行中检测到缓存损坏，删缓存重建: {type(e).__name__}: {e}")
            try:
                _libsql_conn.close()
            except Exception:
                pass
            _libsql_conn = None
            _delete_local_cache()
            _get_libsql_conn()


def sync_to_cloud() -> bool:
    """把本地缓存的写入推送到 Turso 云端（并拉取云端最新数据）。

    libsql embedded replica 模式下，session.commit() 只是把数据写到
    本地缓存文件 turso_cache.db，其他进程/服务通过新连接读到的还是云端旧数据。
    必须调用此函数（或底层 conn.sync()）才能完成云端同步。

    Hrana 连接失效时自动重置并重试一次。

    典型使用场景：
    - 后端 API 通过 get_db() 自动调用（已在文件末尾注入 after_commit 钩子）
    - 一次性脚本/工具直接用 ORM 操作数据库后，需要手动调用：
        db.commit()
        from app.database import sync_to_cloud
        sync_to_cloud()

    Returns:
        bool: True 表示成功同步（或非 Turso 模式下无需同步）；False 表示同步失败
    """
    if not USE_TURSO:
        return True
    try:
        _get_libsql_conn().sync()
        return True
    except Exception as e:
        if "malformed" in str(e) or "corrupt" in str(e):
            # 缓存损坏：删缓存全量重建后再试一次
            logging.warning(f"sync 遇到缓存损坏，删缓存重建后重试: {e}")
            global _libsql_conn
            if _libsql_conn is not None:
                try:
                    _libsql_conn.close()
                except Exception:
                    pass
            _libsql_conn = None
            _delete_local_cache()
            try:
                _get_libsql_conn().sync()
                logging.warning("缓存重建后 sync 重试成功")
                return True
            except Exception as e2:
                logging.error(f"缓存重建后 sync 仍失败: {type(e2).__name__}: {e2}", exc_info=True)
                return False
        if _is_hrana_error(e):
            logging.warning(f"sync 遇到 Hrana 连接失效，重置连接后重试: {e}")
            _reset_libsql_conn(f"sync 失败: {type(e).__name__}")
            try:
                _get_libsql_conn().sync()
                logging.warning("Hrana 重连后 sync 重试成功")
                return True
            except Exception as e2:
                logging.error(f"Hrana 重连后 sync 仍失败: {type(e2).__name__}: {e2}", exc_info=True)
                return False
        logging.error(f"Turso 云端同步失败: {type(e).__name__}: {e}", exc_info=True)
        return False


if USE_TURSO:
    engine = create_engine(
        "sqlite+libsql://",
        creator=_get_libsql_conn,
        poolclass=StaticPool,
    )
    logging.info(f"使用 Turso 云数据库: {TURSO_URL}")
else:
    # 本地 SQLite 回退
    SQLALCHEMY_DATABASE_URL = "sqlite:///./rent_management.db"
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
    logging.info("使用本地 SQLite 数据库")

# 生产库保护：拦截直接操作生产库的 ORM 调用
from app.prod_guard import _check_direct_orm_usage


class _GuardedSessionLocal(sessionmaker):
    """带生产库保护的 SessionLocal 工厂。

    生产环境下直接创建 Session 会触发保护机制报错。
    例外情况（自动放行）：
    - TESTING=1（测试模式）
    - ALLOW_PROD_DB=1（明确授权的脚本）
    - 调用栈来自 conftest.py / test_*.py
    """
    def __call__(self, *args, **kwargs):
        _check_direct_orm_usage()
        return super().__call__(*args, **kwargs)


# 创建会话工厂
SessionLocal = _GuardedSessionLocal(autocommit=False, autoflush=False, bind=engine)


# Turso 模式下：session.commit() 之后自动 sync 到云端
# sync 失败时记录到重试队列，后台 cron job 会自动重试
if USE_TURSO:
    @event.listens_for(SessionLocal, "after_commit")
    def _auto_sync_after_commit(session):
        success = sync_to_cloud()
        if not success:
            from app.sync_queue import record_failed_sync
            # 提取操作上下文（帮助排查是哪次写入失败了）
            info = session.info or {}
            context = info.get("sync_context", "unknown_commit")
            record_failed_sync(context)


# 创建基类
Base = declarative_base()

# 依赖项：获取数据库会话
def get_db() -> Generator[Session, None, None]:
    """获取数据库会话的依赖项。

    Turso 模式下，通过 SQLAlchemy 的 after_commit 事件钩子自动同步到云端，
    业务代码（走标准 get_db 依赖的 API）无需手动调用 sync_to_cloud()。

    请求开始前做连接健康检查，Hrana 连接失效时自动重建（自愈），
    避免连接闲置死亡导致整站 500 直到人工重启。

    Yields:
        Session: SQLAlchemy 数据库会话对象

    Raises:
        Exception: 数据库连接错误时抛出异常
    """
    _ensure_conn_alive()
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logging.error(f"数据库错误: {type(e).__name__}: {str(e)}", exc_info=True)
        raise
    finally:
        db.close()


def create_tables():
    """创建所有数据库表"""
    from app.models import User, Room, Payment, UtilityReading, UtilityRate, UtilityBill, \
        Tenant, LeaseRecord, RoomOccupant, \
        AssetPlatform, AssetRecord, AssetItem
    Base.metadata.create_all(bind=engine)
    # 建表也要同步到云端
    if USE_TURSO:
        sync_to_cloud()
    logging.info("数据库表创建成功")
