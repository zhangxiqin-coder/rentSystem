"""Turso 缓存损坏（malformed）自愈测试（2026-08-23）
覆盖：
1. connect 时缓存损坏 → 删缓存重建
2. 运行中探测（SELECT 1）报 malformed → 删缓存重建
3. sync 时 malformed → 删缓存重建后重试成功
4. 非损坏错误（如普通网络错误）不触发删缓存
5. 独立缓存路径 TURSO_CACHE_PATH 环境变量生效
"""
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app.database as database


class TestMalformedSelfHeal:
    def setup_method(self):
        """每个用例前重置模块状态"""
        database._libsql_conn = None

    def teardown_method(self):
        database._libsql_conn = None

    def _fake_libsql(self, fail_first=True):
        """构造 libsql mock：connect+sync 第一次抛 malformed，第二次成功"""
        calls = {"connect": 0, "sync": 0}
        good_conn = MagicMock()

        def connect(path, sync_url=None, auth_token=None):
            calls["connect"] += 1
            if fail_first and calls["connect"] == 1:
                raise ValueError("database disk image is malformed")
            return good_conn
        mod = MagicMock()
        mod.connect.side_effect = connect
        return mod, calls, good_conn

    def test_connect_malformed_rebuilds(self):
        """connect 时 malformed → 删缓存 → 重连成功"""
        libsql_mod, calls, good = self._fake_libsql()
        with patch.dict("sys.modules", {"libsql_experimental": libsql_mod}), \
             patch.object(database, "_delete_local_cache") as del_mock, \
             patch.object(database, "TURSO_URL", "libsql://x"), \
             patch.object(database, "TURSO_TOKEN", "t"), \
             patch.object(database, "USE_TURSO", True):
            conn = database._get_libsql_conn()
        assert conn is good
        assert calls["connect"] == 2, "应重试第二次连接"
        del_mock.assert_called_once()

    def test_runtime_malformed_rebuilds(self):
        """运行中 SELECT 1 报 malformed → 删缓存重建"""
        libsql_mod, calls, good = self._fake_libsql(fail_first=False)
        bad_conn = MagicMock()
        bad_conn.execute.side_effect = ValueError("database disk image is malformed")
        libsql_mod.connect.side_effect = lambda *a, **k: bad_conn

        with patch.dict("sys.modules", {"libsql_experimental": libsql_mod}), \
             patch.object(database, "_delete_local_cache") as del_mock, \
             patch.object(database, "TURSO_URL", "libsql://x"), \
             patch.object(database, "TURSO_TOKEN", "t"), \
             patch.object(database, "USE_TURSO", True):
            database._get_libsql_conn()  # 建立连接（用 bad_conn）
            assert database._libsql_conn is bad_conn
            del_mock.reset_mock()
            # 重建路径用 good 连接
            libsql_mod.connect.side_effect = lambda *a, **k: good
            database._ensure_conn_alive()  # 探测失败 → 重建
        assert database._libsql_conn is good
        del_mock.assert_called_once()

    def test_sync_malformed_rebuilds(self):
        """sync 时 malformed → 删缓存重建后 sync 成功"""
        libsql_mod, calls, good = self._fake_libsql(fail_first=False)
        bad_conn = MagicMock()
        bad_conn.sync.side_effect = ValueError("database disk image is malformed")
        # 第一次 connect 返回 bad_conn；重建后的 connect 返回 good_conn
        connect_results = [bad_conn, good]
        libsql_mod.connect.side_effect = lambda *a, **k: connect_results.pop(0) if connect_results else good

        with patch.dict("sys.modules", {"libsql_experimental": libsql_mod}), \
             patch.object(database, "_delete_local_cache") as del_mock, \
             patch.object(database, "TURSO_URL", "libsql://x"), \
             patch.object(database, "TURSO_TOKEN", "t"), \
             patch.object(database, "USE_TURSO", True):
            # 第一次连接：sync 失败在 _get_libsql_conn 内部触发重连
            # （首次 sync 抛 malformed → 删缓存 → 第二次 connect 返回 good）
            ok = database.sync_to_cloud()
        assert ok is True
        del_mock.assert_called_once()
        assert database._libsql_conn is good

    def test_non_malformed_no_cache_delete(self):
        """普通网络错误不触发删缓存"""
        libsql_mod = MagicMock()
        libsql_mod.connect.side_effect = ConnectionError("network unreachable")

        with patch.dict("sys.modules", {"libsql_experimental": libsql_mod}), \
             patch.object(database, "_delete_local_cache") as del_mock, \
             patch.object(database, "TURSO_URL", "libsql://x"), \
             patch.object(database, "TURSO_TOKEN", "t"), \
             patch.object(database, "USE_TURSO", True):
            try:
                database._get_libsql_conn()
                raised = False
            except ConnectionError:
                raised = True
        assert raised, "普通错误应原样抛出"
        del_mock.assert_not_called()

    def test_cache_path_env_override(self):
        """TURSO_CACHE_PATH 环境变量覆盖缓存路径"""
        libsql_mod = MagicMock()
        seen_paths = []
        libsql_mod.connect.side_effect = lambda path, **k: seen_paths.append(path) or MagicMock()

        with patch.dict("sys.modules", {"libsql_experimental": libsql_mod}), \
             patch.dict(os.environ, {"TURSO_CACHE_PATH": "/tmp/my_own_cache.db"}), \
             patch.object(database, "TURSO_URL", "libsql://x"), \
             patch.object(database, "TURSO_TOKEN", "t"), \
             patch.object(database, "USE_TURSO", True):
            database._get_libsql_conn()
        assert seen_paths == ["/tmp/my_own_cache.db"]
