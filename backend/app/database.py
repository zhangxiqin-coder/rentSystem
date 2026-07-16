from sqlalchemy import create_engine
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

if TURSO_URL and TURSO_TOKEN:
    # Turso libSQL 连接（embedded replica 模式）
    # 第一个参数是本地缓存文件路径，sync_url 指向 Turso 云端
    # 必须调用 sync() 才能从云端拉取最新数据
    import libsql_experimental as libsql

    _LOCAL_CACHE = os.path.join(os.path.dirname(__file__), "..", "turso_cache.db")

    def _get_libsql_connection():
        conn = libsql.connect(_LOCAL_CACHE, sync_url=TURSO_URL, auth_token=TURSO_TOKEN)
        conn.sync()
        return conn

    engine = create_engine(
        "sqlite+libsql://",
        creator=_get_libsql_connection,
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

# 创建基类
Base = declarative_base()

# 依赖项：获取数据库会话
def get_db() -> Generator[Session, None, None]:
    """获取数据库会话的依赖项。
    
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
        Tenant, LeaseRecord, \
        AssetPlatform, AssetRecord, AssetItem
    Base.metadata.create_all(bind=engine)
    logging.info("数据库表创建成功")
