"""utility-bills 创建接口回归测试（2026-09-08 8月水费录入失败事故）

事故链：本地缓存副本落后于云端（embedded replica 读旧数据）→
服务层查重失效 → INSERT 在云端撞 UNIQUE(series,year,month,utility_type)
→ libsql 把约束错误包成 ValueError → 前端收到 500。

回归目标：即使查重被绕过（缓存落后等任何原因），数据库约束兜底时
必须返回 400 + 友好中文提示，不能裸抛 500。
"""
import pytest

from app.models import UtilityBill, User, Room, pwd_context


@pytest.fixture
def bill_owner(client, db):
    """建一个有房间系列的用户并登录，返回 (headers, series)"""
    user = User(
        username="bill_owner_u9",
        email="bill_owner_u9@test.com",
        password_hash=pwd_context.hash("Test12345"),
        role="landlord",
    )
    db.add(user)
    db.flush()
    room = Room(
        room_number="UB-101",
        series="UB102",
        monthly_rent=1000,
        owner_id=user.id,
    )
    db.add(room)
    db.commit()
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "bill_owner_u9", "password": "Test12345"},
    )
    token = resp.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}, "UB102"


def _make_bill_payload(series="UB102", utility_type="water", month=8, cost=100.5):
    return {
        "series": series,
        "year": 2026,
        "month": month,
        "utility_type": utility_type,
        "cost": cost,
        "notes": "",
    }


class TestCreateUtilityBill:
    def test_create_ok(self, client, db, bill_owner):
        """正常创建返回 200，字段回显"""
        headers, series = bill_owner
        resp = client.post(
            "/api/v1/utility-bills/", json=_make_bill_payload(), headers=headers
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["series"] == series
        assert float(data["cost"]) == 100.5
        assert db.query(UtilityBill).count() == 1

    def test_duplicate_returns_400_friendly_message(self, client, db, bill_owner):
        """同系列同年月同类型重复创建 → 400 + 中文提示（服务层查重）"""
        headers, series = bill_owner
        first = client.post(
            "/api/v1/utility-bills/", json=_make_bill_payload(), headers=headers
        )
        assert first.status_code == 200
        second = client.post(
            "/api/v1/utility-bills/", json=_make_bill_payload(), headers=headers
        )
        assert second.status_code == 400
        assert "已存在" in second.json()["detail"]

    def test_db_constraint_fallback_returns_400_not_500(
        self, client, db, bill_owner, monkeypatch
    ):
        """查重被绕过（模拟缓存落后）、DB 约束兜底时 → 400 而不是 500。

        事故复现（2026-09-08 8月水费）：本地副本落后，服务层 .first()
        查不到云端已有记录 → INSERT 撞 UNIQUE(series,year,month,type)。
        生产 libsql 把约束错误包成 ValueError，测试 SQLite 抛
        IntegrityError——端点必须两者都兜住转 400。
        """
        headers, series = bill_owner
        # 预置一条“云端已有”的记录
        db.add(
            UtilityBill(
                series="UB102",
                year=2026,
                month=8,
                utility_type="water",
                cost=179.8,
            )
        )
        db.commit()

        # 模拟缓存落后：只对 UtilityBill 的查重返回 None，其余查询走真实路径
        real_query = db.query

        class _StaleQuery:
            def filter(self, *a, **k):
                return self

            def first(self):
                return None

        def fake_query(*args, **kwargs):
            if args and args[0] is UtilityBill:
                return _StaleQuery()
            return real_query(*args, **kwargs)

        monkeypatch.setattr(db, "query", fake_query)

        resp = client.post(
            "/api/v1/utility-bills/", json=_make_bill_payload(), headers=headers
        )
        assert resp.status_code == 400, f"应返回400，实际{resp.status_code}: {resp.text}"
        assert "已存在" in resp.json()["detail"]

    def test_other_series_forbidden(self, client, db, bill_owner):
        """给不属于自己的系列录账单 → 403"""
        headers, series = bill_owner
        resp = client.post(
            "/api/v1/utility-bills/",
            json=_make_bill_payload(series="OTHER"),
            headers=headers,
        )
        assert resp.status_code == 403
        assert "无权" in resp.json()["detail"]

    def test_same_month_different_type_ok(self, client, db, bill_owner):
        """同月同系列不同类型（水+电）→ 都能创建，互不冲突"""
        headers, series = bill_owner
        r1 = client.post(
            "/api/v1/utility-bills/",
            json=_make_bill_payload(utility_type="water"),
            headers=headers,
        )
        r2 = client.post(
            "/api/v1/utility-bills/",
            json=_make_bill_payload(utility_type="electric"),
            headers=headers,
        )
        assert r1.status_code == r2.status_code == 200, (r1.text, r2.text)
        assert db.query(UtilityBill).count() == 2

    def test_update_existing_bill_cost(self, client, db, bill_owner):
        """改已有账单金额走 PUT 正常（用户改错的正确姿势）"""
        headers, series = bill_owner
        created = client.post(
            "/api/v1/utility-bills/", json=_make_bill_payload(), headers=headers
        )
        bill_id = created.json()["id"]
        resp = client.put(
            f"/api/v1/utility-bills/{bill_id}",
            json={
                "utility_type": "water",
                "cost": 200.0,
                "notes": "改金额",
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        assert float(resp.json()["cost"]) == 200.0
