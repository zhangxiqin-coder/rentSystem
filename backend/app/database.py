from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
import logging

# SQLite 数据库配置
SQLALCHEMY_DATABASE_URL = "sqlite:///./rent_management.db"

# 创建数据库引擎
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)

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
        logging.error(f"数据库错误: {e}")
        raise
    finally:
        db.close()


def create_tables():
    """创建所有数据库表"""
    from app.models import User, Room, Payment, UtilityReading, UtilityRate
    Base.metadata.create_all(bind=engine)
    logging.info("数据库表创建成功")
