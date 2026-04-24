#!/usr/bin/env python3
"""重置用户密码的脚本"""
import sys
from pathlib import Path

# Add the backend directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.database import SessionLocal
from app.models import User

def reset_password(username: str, new_password: str):
    """重置用户密码"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            print(f"❌ 用户 '{username}' 不存在")
            return False

        # Reset password
        user.set_password(new_password)
        db.commit()

        # Verify
        is_valid = user.verify_password(new_password)
        print(f"✅ 密码已重置")
        print(f"   用户名: {user.username}")
        print(f"   显示名: {user.full_name}")
        print(f"   角色: {user.role}")
        print(f"   验证测试: {'通过' if is_valid else '失败'}")
        return is_valid
    except Exception as e:
        print(f"❌ 错误: {e}")
        db.rollback()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("用法: python reset_password.py <用户名> <新密码>")
        sys.exit(1)

    username = sys.argv[1]
    new_password = sys.argv[2]

    success = reset_password(username, new_password)
    sys.exit(0 if success else 1)
