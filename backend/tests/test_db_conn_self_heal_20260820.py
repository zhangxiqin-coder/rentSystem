"""
Hrana 连接失效自愈机制测试

背景：2026-08-20 11:46，Turso Hrana 长连接闲置后被云端掐掉（stream not found），
模块级单例连接不自愈，导致 102A-3 水电录入连续失败（1次400+3次500），
且整站所有 DB 请求 500，直到人工重启后端。

本测试验证 database.py 的自愈逻辑：
- _is_hrana_error: 正确识别 Hrana 失效错误
- _reset_libsql_conn: 重置单例 + dispose engine
- _ensure_conn_alive: 探测失败时自动重建
- sync_to_cloud: Hrana 失败时重置重试一次
"""
import pytest
from unittest.mock import MagicMock, patch

from app import database as db_module


class FakeHranaError(ValueError):
    """模拟 libsql 的 Hrana stream not found 错误"""
    def __str__(self):
        return 'Hrana: `api error: `status=404 Not Found, body={"error":"stream not found: d851ada9:b11193"}`'


class TestIsHranaError:
    def test_stream_not_found_is_hrana(self):
        assert db_module._is_hrana_error(FakeHranaError()) is True

    def test_plain_hrana_keyword(self):
        assert db_module._is_hrana_error(ValueError("Hrana: some other error")) is True

    def test_normal_db_error_not_hrana(self):
        assert db_module._is_hrana_error(ValueError("no such table: rooms")) is False

    def test_operational_error_not_hrana(self):
        assert db_module._is_hrana_error(RuntimeError("database is locked")) is False


class TestResetLibsqlConn:
    def setup_method(self):
        # 保存/恢复全局状态，避免污染其他测试
        self._orig_conn = db_module._libsql_conn
        self._orig_engine = db_module.engine

    def teardown_method(self):
        db_module._libsql_conn = self._orig_conn
        db_module.engine = self._orig_engine

    def test_reset_clears_singleton(self):
        dead = MagicMock()
        db_module._libsql_conn = dead
        db_module._reset_libsql_conn("test")
        assert db_module._libsql_conn is None
        dead.close.assert_called_once()

    def test_reset_disposes_engine(self):
        dead_engine = MagicMock()
        db_module._libsql_conn = MagicMock()
        db_module.engine = dead_engine
        db_module._reset_libsql_conn("test")
        dead_engine.dispose.assert_called_once()

    def test_reset_with_dead_close(self):
        """close 抛异常也不影响重置"""
        dead = MagicMock()
        dead.close.side_effect = RuntimeError("already closed")
        db_module._libsql_conn = dead
        db_module._reset_libsql_conn("test")
        assert db_module._libsql_conn is None

    def test_reset_when_conn_is_none(self):
        """连接未初始化时调用不报错"""
        db_module._libsql_conn = None
        db_module._reset_libsql_conn("test")
        assert db_module._libsql_conn is None


class TestEnsureConnAlive:
    def setup_method(self):
        self._orig_conn = db_module._libsql_conn
        self._orig_use_turso = db_module.USE_TURSO

    def teardown_method(self):
        db_module._libsql_conn = self._orig_conn
        db_module.USE_TURSO = self._orig_use_turso

    def test_healthy_conn_untouched(self):
        healthy = MagicMock()
        healthy.execute.return_value = MagicMock()
        db_module._libsql_conn = healthy
        db_module.USE_TURSO = True
        db_module._ensure_conn_alive()
        healthy.execute.assert_called_once_with("SELECT 1")
        # 连接未被替换
        assert db_module._libsql_conn is healthy

    def test_dead_conn_rebuilt(self):
        dead = MagicMock()
        dead.execute.side_effect = FakeHranaError()
        fresh = MagicMock()
        db_module._libsql_conn = dead
        db_module.USE_TURSO = True

        rebuild_calls = []
        def fake_get_conn():
            rebuild_calls.append(1)
            db_module._libsql_conn = fresh
            return fresh

        with patch.object(db_module, "_get_libsql_conn", side_effect=fake_get_conn):
            db_module._ensure_conn_alive()

        dead.execute.assert_called_once()
        assert len(rebuild_calls) == 1, "死连接应触发一次重建"
        assert db_module._libsql_conn is fresh

    def test_noop_when_conn_not_initialized(self):
        db_module._libsql_conn = None
        db_module._ensure_conn_alive()  # 不应抛错

    def test_noop_when_not_turso(self):
        probe = MagicMock()
        db_module._libsql_conn = probe
        db_module.USE_TURSO = False
        db_module._ensure_conn_alive()
        probe.execute.assert_not_called()

    def test_non_hrana_error_not_swallowed_by_reset(self):
        """非 Hrana 错误（如表不存在）不应触发重建，但也不应抛出中断请求"""
        weird = MagicMock()
        weird.execute.side_effect = ValueError("no such table: rooms")
        db_module._libsql_conn = weird
        db_module.USE_TURSO = True
        db_module._ensure_conn_alive()  # 不抛错，静默通过
        assert db_module._libsql_conn is weird, "非 Hrana 错误不应重置连接"


class TestSyncToCloudRetry:
    def setup_method(self):
        self._orig_conn = db_module._libsql_conn
        self._orig_use_turso = db_module.USE_TURSO

    def teardown_method(self):
        db_module._libsql_conn = self._orig_conn
        db_module.USE_TURSO = self._orig_use_turso

    def test_sync_retries_after_hrana_failure(self):
        """第一次 sync 因 Hrana 失败 → 重置重试 → 成功"""
        dead = MagicMock()
        dead.sync.side_effect = FakeHranaError()
        fresh = MagicMock()
        db_module._libsql_conn = dead
        db_module.USE_TURSO = True

        def fake_get_conn():
            db_module._libsql_conn = fresh
            return fresh

        with patch.object(db_module, "_get_libsql_conn", side_effect=fake_get_conn):
            result = db_module.sync_to_cloud()

        assert result is True
        fresh.sync.assert_called_once()

    def test_sync_gives_up_after_retry_fails(self):
        """重试仍失败 → 返回 False（进入 sync_queue 重试队列）"""
        dead = MagicMock()
        dead.sync.side_effect = FakeHranaError()
        also_dead = MagicMock()
        also_dead.sync.side_effect = FakeHranaError()
        db_module._libsql_conn = dead
        db_module.USE_TURSO = True

        conn_sequence = [also_dead]
        def fake_get_conn():
            db_module._libsql_conn = conn_sequence[0]
            return conn_sequence[0]

        with patch.object(db_module, "_get_libsql_conn", side_effect=fake_get_conn):
            result = db_module.sync_to_cloud()

        assert result is False

    def test_sync_non_hrana_failure_no_retry(self):
        """非 Hrana 失败（如 Turso 502）走原有路径，直接 False"""
        conn = MagicMock()
        conn.sync.side_effect = ValueError("Hrana: `api error: `status=502 Bad Gateway`")  # 502 也是 Hrana 前缀，属于可重试
        # 换成真正的非 Hrana 错误
        conn.sync.side_effect = ConnectionError("network unreachable")
        db_module._libsql_conn = conn
        db_module.USE_TURSO = True
        result = db_module.sync_to_cloud()
        assert result is False
        conn.sync.assert_called_once()  # 没有重试
