"""
测试房间管理 API
"""
import pytest
from fastapi.testclient import TestClient
from datetime import date
from decimal import Decimal

from app.main import app
from app.models import Room
from app.database import SessionLocal


client = TestClient(app)




class TestRoomsAPI:
    """房间 API 测试类"""
    
    def test_create_room(self, auth_headers):
        """测试创建房间"""
        room_data = {
            "room_number": "101",
            "building": "1号楼",
            "floor": 1,
            "area": Decimal("50.5"),
            "monthly_rent": Decimal("1000.00"),
            "deposit_amount": Decimal("2000.00"),
            "payment_cycle": 1,
            "status": "available"
        }
        
        response = client.post("/api/v1/rooms", json=room_data, headers=auth_headers)
        assert response.status_code == 201
        data = response.json()
        assert data["room_number"] == "101"
        assert data["monthly_rent"] == "1000.00"
    
    def test_create_duplicate_room(self, auth_headers, db):
        """测试创建重复房间号"""
        # 创建第一个房间
        room = Room(
            room_number="102",
            monthly_rent=Decimal("1000.00"),
            payment_cycle=1
        )
        db.add(room)
        db.commit()
        
        # 尝试创建重复房间
        room_data = {
            "room_number": "102",
            "monthly_rent": Decimal("1500.00"),
            "payment_cycle": 1
        }
        
        response = client.post("/api/v1/rooms", json=room_data, headers=auth_headers)
        assert response.status_code == 400
    
    def test_list_rooms(self, auth_headers, db):
        """测试获取房间列表"""
        # 创建测试房间
        for i in range(3):
            room = Room(
                room_number=f"10{i}",
                monthly_rent=Decimal("1000.00"),
                payment_cycle=1
            )
            db.add(room)
        db.commit()
        
        response = client.get("/api/v1/rooms", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 3
    
    def test_get_room_detail(self, auth_headers, db):
        """测试获取房间详情"""
        room = Room(
            room_number="201",
            monthly_rent=Decimal("1200.00"),
            payment_cycle=3
        )
        db.add(room)
        db.commit()
        
        response = client.get(f"/api/v1/rooms/{room.id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["room_number"] == "201"
    
    def test_update_room(self, auth_headers, db):
        """测试更新房间"""
        room = Room(
            room_number="301",
            monthly_rent=Decimal("1000.00"),
            payment_cycle=1
        )
        db.add(room)
        db.commit()
        
        update_data = {
            "monthly_rent": Decimal("1200.00"),
            "deposit_amount": Decimal("2400.00")
        }
        
        response = client.put(f"/api/v1/rooms/{room.id}", json=update_data, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["monthly_rent"] == "1200.00"
    
    def test_delete_room(self, auth_headers, db):
        """测试删除房间"""
        room = Room(
            room_number="401",
            monthly_rent=Decimal("1000.00"),
            payment_cycle=1
        )
        db.add(room)
        db.commit()
        room_id = room.id
        
        response = client.delete(f"/api/v1/rooms/{room_id}", headers=auth_headers)
        assert response.status_code == 204
        
        # 验证删除
        deleted_room = db.query(Room).filter(Room.id == room_id).first()
        assert deleted_room is None
    
    def test_room_auto_status_occupied(self, auth_headers, db):
        """测试房间自动状态更新 - 已租出"""
        room = Room(
            room_number="501",
            monthly_rent=Decimal("1000.00"),
            payment_cycle=1
        )
        db.add(room)
        db.commit()
        
        update_data = {
            "tenant_name": "张三",
            "tenant_phone": "13800138000",
            "lease_start": date.today(),
            "lease_end": date(2025, 12, 31)
        }
        
        response = client.put(f"/api/v1/rooms/{room.id}", json=update_data, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "occupied"
    
    def test_room_auto_status_available(self, auth_headers, db):
        """测试房间自动状态更新 - 空置"""
        room = Room(
            room_number="601",
            monthly_rent=Decimal("1000.00"),
            payment_cycle=1,
            tenant_name="李四"
        )
        db.add(room)
        db.commit()
        
        update_data = {
            "tenant_name": None,
            "tenant_phone": None
        }
        
        response = client.put(f"/api/v1/rooms/{room.id}", json=update_data, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "available"
    
    def test_filter_rooms_by_status(self, auth_headers, db):
        """测试按状态筛选房间"""
        # 创建不同状态的房间
        room1 = Room(room_number="701", monthly_rent=Decimal("1000"), payment_cycle=1, status="available")
        room2 = Room(room_number="702", monthly_rent=Decimal("1000"), payment_cycle=1, status="occupied")
        db.add_all([room1, room2])
        db.commit()
        
        response = client.get("/api/v1/rooms?status=available", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert all(r["status"] == "available" for r in data["items"])
