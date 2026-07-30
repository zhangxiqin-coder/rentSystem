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
    """
    global _libsql_conn
    if _libsql_conn is None:
        import libsql_experimental as libsql
        local_cache = os.path.join(os.path.dirname(__file__), "..", "turso_cache.db")
        _libsql_conn = libsql.connect(local_cache, sync_url=TURSO_URL, auth_token=TURSO_TOKEN)
        # 连接建立时先拉一次云端最新数据
        _libsql_conn.sync()
    return _libsql_conn


def sync_to_cloud() -> bool:
    """把本地缓存的写入推送到 Turso 云端（并拉取云端最新数据）。

    libsql embedded replica 模式下，session.commit() 只是把数据写到
    本地缓存文件 turso_cache.db，其他进程/服务通过新连接读到的还是云端旧数据。
    必须调用此函数（或底层 conn.sync()）才能完成云端同步。

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

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Turso 模式下：session.commit() 之后自动 sync 到云端
# 这样所有走 get_db() 的 API 写入都会自动同步，业务代码无需手动调用 sync_to_cloud()
if USE_TURSO:
    @event.listens_for(SessionLocal, "after_commit")
    def _auto_sync_after_commit(session):
        sync_to_cloud()


# 创建基类
Base = declarative_base()

# 依赖项：获取数据库会话
def get_db() -> Generator[Session, None, None]:
    """获取数据库会话的依赖项。

    Turso 模式下，通过 SQLAlchemy 的 after_commit 事件钩子自动同步到云端，
    业务代码（走标准 get_db 依赖的 API）无需手动调用 sync_to_cloud()。

    Yields:
        Session: SQLAlchemy 数据库会话对象

    Raises:
        Exception: 数据库连接错误时抛出异常
    """
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
