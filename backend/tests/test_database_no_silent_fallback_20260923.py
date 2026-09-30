"""database.py 静默回退防护测试（2026-09-23 化石库误诊事故）

背景：脚本漏 load_dotenv 时 database.py 曾静默回退到本地 rent_management.db
（8月停更的化石库），产生"本地副本落后云端"的假象。
修复后行为：
  - 有 Turso 配置 → 正常云端模式
  - 无配置 + TESTING=1 → 回退到 test_rent_management.db（测试安全）
  - 无配置 + 非 TESTING → RuntimeError 显式报错（根治误诊）
"""
import importlib
import os
import sys
import subprocess

CODE = (
    "import sys; sys.path.insert(0, '.');\n"
    "try:\n"
    "    from app.database import USE_TURSO, engine\n"
    "    print('MODE', 'turso' if USE_TURSO else 'fallback', engine.url)\n"
    "except RuntimeError as e:\n"
    "    print('MODE runtime_error:', str(e)[:40])\n"
)


def _run(extra_env: dict) -> str:
    """子进程 import app.database，避免污染本进程的模块单例。"""
    env = {
        k: v for k, v in os.environ.items()
        if not k.startswith(("TURSO_", "TESTING", "ALLOW_PROD_DB"))
    }
    env.update(extra_env)
    # 剔除 heredoc 难搞的引号问题，用 -c 传代码
    r = subprocess.run(
        [sys.executable, "-c", CODE],
        capture_output=True, text=True, timeout=60, env=env,
    )
    return r.stdout.strip()


def test_missing_env_non_testing_raises_runtime_error():
    """无 Turso 配置且非测试模式：必须显式报错，不得静默回退。"""
    out = _run({})
    assert "MODE runtime_error" in out, f"应显式报错，实际输出: {out}"
    assert "拒绝回退" in out or "Turso 配置缺失" in out


def test_missing_env_with_testing_falls_back_to_test_db():
    """无 Turso 配置 + TESTING=1：回退到测试库（不是生产化石库）。"""
    out = _run({"TESTING": "1"})
    assert "MODE fallback" in out, f"应回退，实际输出: {out}"
    assert "test_rent_management.db" in out, f"必须指向测试库: {out}"
