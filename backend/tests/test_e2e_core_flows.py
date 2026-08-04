"""
核心业务流程端到端集成测试

覆盖三大核心功能（从前端API层走起）：
1. 增加房间
2. 增加租客（创建租客 + 创建租赁记录/入住）
3. 录入水电

每次提交代码前跑这个测试，确保核心流程不被改坏。
运行: cd backend && ./venv/bin/python -m pytest tests/test_e2e_core_flows.py -v
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal

from app.models import UtilityRate


@pytest.fixture(autouse=True)
def setup_utility_rates(db):
    """自动为每个测试创建水电费率（业务层查 UtilityRate 表，不是 Room 字段）"""
    today = date.today()
    for utype, rate_val in [("water", Decimal("5.00")), ("electricity", Decimal("1.00"))]:
        existing = db.query(UtilityRate).filter(
            UtilityRate.utility_type == utype,
            UtilityRate.is_active == True
        ).first()
        if not existing:
            db.add(UtilityRate(
                utility_type=utype,
                rate_per_unit=rate_val,
                effective_date=today - timedelta(days=365),
                is_active=True,
            ))
    db.commit()


class TestE2ECreateRoom:
    """E2E: 增加房间"""

    def test_create_room_minimal(self, client, auth_headers):
        """增加房间 - 最少必填字段"""
        room_data = {
            "room_number": "E2E-001",
            "building": "测试楼栋",
            "monthly_rent": "1500.00",
            "payment_cycle": 1,
        }
        resp = client.post("/api/v1/rooms", json=room_data, headers=auth_headers)
        assert resp.status_code == 201, f"创建房间失败: {resp.text}"
        data = resp.json()
        assert data["room_number"] == "E2E-001"
        assert float(data["monthly_rent"]) == 1500.0
        assert data["status"] == "available"

    def test_create_room_zero_rent_rejected(self, client, auth_headers):
        """增加房间 - 租金为0应被拒绝（gt=0）"""
        room_data = {
            "room_number": "E2E-ZERO",
            "building": "测试楼栋",
            "monthly_rent": "0",
            "payment_cycle": 1,
        }
        resp = client.post("/api/v1/rooms", json=room_data, headers=auth_headers)
        assert resp.status_code == 422, f"租金0应该返回422，实际{resp.status_code}: {resp.text}"

    def test_create_room_empty_lease_dates(self, client, auth_headers):
        """增加房间 - lease_start/lease_end 空字符串不应报422"""
        room_data = {
            "room_number": "E2E-002",
            "building": "测试楼栋",
            "monthly_rent": "2000.00",
            "payment_cycle": 1,
            "lease_start": None,
            "lease_end": None,
        }
        resp = client.post("/api/v1/rooms", json=room_data, headers=auth_headers)
        assert resp.status_code == 201, f"空日期应接受(null)，实际{resp.status_code}: {resp.text}"

    def test_create_room_with_tenant(self, client, auth_headers):
        """增加房间 - 带租客信息一起创建"""
        today = date.today()
        end = today.replace(year=today.year + 1) - timedelta(days=1)
        room_data = {
            "room_number": "E2E-003",
            "building": "测试楼栋",
            "monthly_rent": "1800.00",
            "payment_cycle": 1,
            "tenant_name": "张三",
            "tenant_phone": "13800000001",
            "lease_start": today.isoformat(),
            "lease_end": end.isoformat(),
        }
        resp = client.post("/api/v1/rooms", json=room_data, headers=auth_headers)
        assert resp.status_code == 201, f"创建带租客房间失败: {resp.text}"


class TestE2ECreateTenantAndLease:
    """E2E: 增加租客 + 创建租赁记录"""

    def _create_room(self, client, auth_headers, room_number="E2E-T01"):
        """辅助：先创建一个空房间"""
        resp = client.post("/api/v1/rooms", json={
            "room_number": room_number,
            "building": "测试楼栋",
            "monthly_rent": "1500.00",
            "payment_cycle": 1,
        }, headers=auth_headers)
        assert resp.status_code == 201
        return resp.json()

    def test_create_tenant(self, client, auth_headers):
        """增加租客 - 创建租客记录"""
        tenant_data = {
            "name": "李四",
            "phone": "13900000001",
            "status": "active",
        }
        resp = client.post("/api/v1/tenants", json=tenant_data, headers=auth_headers)
        assert resp.status_code in (200, 201), f"创建租客失败: {resp.text}"
        data = resp.json()
        assert data["name"] == "李四"

    def test_create_lease_record(self, client, auth_headers):
        """增加租客 - 创建租赁记录（入住）"""
        # 1. 先创建房间
        room = self._create_room(client, auth_headers, "E2E-L01")
        room_id = room["id"]

        # 2. 创建租客
        resp = client.post("/api/v1/tenants", json={
            "name": "王五",
            "phone": "13900000002",
            "status": "active",
        }, headers=auth_headers)
        assert resp.status_code in (200, 201)
        tenant_id = resp.json()["id"]

        # 3. 创建租赁记录
        today = date.today()
        end = today.replace(year=today.year + 1) - timedelta(days=1)
        lease_data = {
            "tenant_id": tenant_id,
            "room_id": room_id,
            "lease_start": today.isoformat(),
            "lease_end": end.isoformat(),
            "monthly_rent": "1500.00",
            "deposit_amount": "3000.00",
        }
        resp = client.post("/api/v1/lease-records", json=lease_data, headers=auth_headers)
        assert resp.status_code in (200, 201), f"创建租赁记录失败: {resp.text}"
        data = resp.json()
        assert data["tenant_id"] == tenant_id
        assert data["room_id"] == room_id

    def test_create_lease_invalid_dates_rejected(self, client, auth_headers):
        """增加租客 - 结束日期<=开始日期应返回400"""
        room = self._create_room(client, auth_headers, "E2E-L02")
        resp = client.post("/api/v1/tenants", json={
            "name": "赵六",
            "phone": "13900000003",
            "status": "active",
        }, headers=auth_headers)
        tenant_id = resp.json()["id"]

        today = date.today()
        lease_data = {
            "tenant_id": tenant_id,
            "room_id": room["id"],
            "lease_start": today.isoformat(),
            "lease_end": today.isoformat(),  # 同一天
            "monthly_rent": "1500.00",
        }
        resp = client.post("/api/v1/lease-records", json=lease_data, headers=auth_headers)
        assert resp.status_code == 400, f"结束日期<=开始日期应返回400，实际{resp.status_code}: {resp.text}"

    def test_room_checkin(self, client, auth_headers):
        """增加租客 - 通过房间checkin端点入住"""
        room = self._create_room(client, auth_headers, "E2E-C01")
        today = date.today()
        end = today.replace(year=today.year + 1) - timedelta(days=1)
        checkin_data = {
            "tenant_name": "钱七",
            "tenant_phone": "13900000004",
            "lease_start": today.isoformat(),
            "lease_end": end.isoformat(),
            "monthly_rent": 1500,
            "deposit_amount": 3000,
        }
        resp = client.post(f"/api/v1/rooms/{room['id']}/checkin", json=checkin_data, headers=auth_headers)
        assert resp.status_code == 200, f"入住失败: {resp.text}"


class TestE2EUtilityReading:
    """E2E: 录入水电"""

    def _create_occupied_room(self, client, auth_headers, room_number="E2E-U01"):
        """辅助：创建一个有租客的房间"""
        # 创建房间
        resp = client.post("/api/v1/rooms", json={
            "room_number": room_number,
            "building": "测试楼栋",
            "monthly_rent": "1500.00",
            "payment_cycle": 1,
            "water_rate": "5.00",
            "electricity_rate": "1.00",
            "tenant_name": "孙八",
            "tenant_phone": "13900000005",
            "lease_start": date.today().isoformat(),
            "lease_end": (date.today().replace(year=date.today().year + 1) - timedelta(days=1)).isoformat(),
        }, headers=auth_headers)
        assert resp.status_code == 201
        return resp.json()

    def test_create_water_reading(self, client, auth_headers):
        """录入水电 - 录入水费"""
        room = self._create_occupied_room(client, auth_headers, "E2E-W01")
        reading_data = {
            "room_id": room["id"],
            "utility_type": "water",
            "reading": "100.5",
            "reading_date": date.today().isoformat(),
        }
        resp = client.post("/api/v1/utility/readings", json=reading_data, headers=auth_headers)
        assert resp.status_code == 201, f"录入水费失败: {resp.text}"
        data = resp.json()
        assert float(data["reading"]) == 100.5

    def test_create_electricity_reading(self, client, auth_headers):
        """录入水电 - 录入电费"""
        room = self._create_occupied_room(client, auth_headers, "E2E-E01")
        reading_data = {
            "room_id": room["id"],
            "utility_type": "electricity",
            "reading": "200.0",
            "reading_date": date.today().isoformat(),
        }
        resp = client.post("/api/v1/utility/readings", json=reading_data, headers=auth_headers)
        assert resp.status_code == 201, f"录入电费失败: {resp.text}"

    def test_create_water_then_electricity(self, client, auth_headers):
        """录入水电 - 先水后电（完整流程）"""
        room = self._create_occupied_room(client, auth_headers, "E2E-WE01")
        today = date.today().isoformat()

        # 录入水
        resp = client.post("/api/v1/utility/readings", json={
            "room_id": room["id"],
            "utility_type": "water",
            "reading": "50.0",
            "reading_date": today,
        }, headers=auth_headers)
        assert resp.status_code == 201, f"录入水费失败: {resp.text}"

        # 录入电
        resp = client.post("/api/v1/utility/readings", json={
            "room_id": room["id"],
            "utility_type": "electricity",
            "reading": "150.0",
            "reading_date": today,
        }, headers=auth_headers)
        assert resp.status_code == 201, f"录入电费失败: {resp.text}"


class TestE2EFullWorkflow:
    """E2E: 完整业务流程（增房间→增租客→录入水电→清理）"""

    def test_full_workflow(self, client, auth_headers):
        """
        完整流程：
        1. 创建房间
        2. 创建租客
        3. 创建租赁记录（入住）
        4. 录入水费
        5. 录入电费
        6. 验证房间状态变为 occupied
        7. 清理删除
        """
        today = date.today()
        end = today.replace(year=today.year + 1) - timedelta(days=1)

        # Step 1: 创建房间
        resp = client.post("/api/v1/rooms", json={
            "room_number": "E2E-FULL-001",
            "building": "集成测试楼",
            "series": "测试系列",
            "monthly_rent": "2500.00",
            "payment_cycle": 1,
            "water_rate": "5.00",
            "electricity_rate": "1.00",
        }, headers=auth_headers)
        assert resp.status_code == 201, f"Step1 创建房间失败: {resp.text}"
        room = resp.json()
        room_id = room["id"]

        # Step 2: 创建租客
        resp = client.post("/api/v1/tenants", json={
            "name": "E2E测试租客",
            "phone": "13700000000",
            "status": "active",
        }, headers=auth_headers)
        assert resp.status_code in (200, 201), f"Step2 创建租客失败: {resp.text}"
        tenant_id = resp.json()["id"]

        # Step 3: 创建租赁记录（入住）
        resp = client.post("/api/v1/lease-records", json={
            "tenant_id": tenant_id,
            "room_id": room_id,
            "lease_start": today.isoformat(),
            "lease_end": end.isoformat(),
            "monthly_rent": "2500.00",
            "deposit_amount": "5000.00",
            "initial_electricity_reading": "100.0",
            "initial_water_reading": "50.0",
        }, headers=auth_headers)
        assert resp.status_code in (200, 201), f"Step3 创建租赁记录失败: {resp.text}"

        # Step 4: 验证房间状态
        resp = client.get(f"/api/v1/rooms/{room_id}", headers=auth_headers)
        assert resp.status_code == 200
        room_data = resp.json()
        assert room_data["status"] == "occupied", f"房间状态应为occupied，实际{room_data['status']}"
        assert room_data["tenant_name"] == "E2E测试租客"

        # Step 5: 录入水费
        resp = client.post("/api/v1/utility/readings", json={
            "room_id": room_id,
            "utility_type": "water",
            "reading": "65.0",
            "reading_date": today.isoformat(),
        }, headers=auth_headers)
        assert resp.status_code == 201, f"Step5 录入水费失败: {resp.text}"

        # Step 6: 录入电费
        resp = client.post("/api/v1/utility/readings", json={
            "room_id": room_id,
            "utility_type": "electricity",
            "reading": "130.0",
            "reading_date": today.isoformat(),
        }, headers=auth_headers)
        assert resp.status_code == 201, f"Step6 录入电费失败: {resp.text}"

        # Step 7: 清理 - 删除房间
        resp = client.delete(f"/api/v1/rooms/{room_id}", headers=auth_headers)
        assert resp.status_code in (200, 204), f"Step7 删除房间失败: {resp.text}"
