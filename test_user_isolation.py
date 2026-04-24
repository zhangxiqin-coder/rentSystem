"""
测试用户隔离功能
"""
import requests

BASE_URL = "http://localhost:8000/api"

# 创建一个session来保持cookies
session = requests.Session()

# 1. 创建测试用户
print("=" * 60)
print("1️⃣ 创建测试用户 (newlandlord)")
print("=" * 60)

register_data = {
    "username": "newlandlord",
    "email": "newlandlord@example.com",
    "full_name": "新房东",
    "password": "password123",
    "role": "landlord"
}

# 尝试创建用户
try:
    response = session.post(f"{BASE_URL}/auth/register", json=register_data)
    print(f"注册结果: {response.status_code}")
    if response.status_code == 200:
        print("   ✅ 测试用户创建成功")
    else:
        print(f"   ⚠️ 注册失败: {response.text}")
except Exception as e:
    print(f"   ⚠️ 注册请求异常: {e}")

# 2. 用测试用户登录
print("\n" + "=" * 60)
print("2️⃣ 用新用户登录获取token")
print("=" * 60)

login_data = {
    "username": "newlandlord",
    "password": "password123"
}

response = session.post(f"{BASE_URL}/auth/login", data=login_data, headers=headers)
if response.status_code == 200:
    token = response.json()["access_token"]
    print("   ✅ 新用户登录成功")
    print(f"   Token: {token[:50]}...")
else:
    print(f"   ❌ 登录失败: {response.text}")
    exit(1)

headers_auth = {"Authorization": f"Bearer {token}", "X-CSRF-Token": csrf_token}

# 3. 新用户查看房间列表（应该是空的）
print("\n" + "=" * 60)
print("3️⃣ 新用户查看房间列表（预期：空）")
print("=" * 60)

response = session.get(f"{BASE_URL}/rooms", headers=headers_auth)
rooms = response.json()
if response.status_code == 200:
    print(f"   房间数量: {len(rooms['items'])}")
    if len(rooms['items']) == 0:
        print("   ✅ 用户隔离生效：新用户看不到任何房间")
    else:
        print(f"   ❌ 用户隔离失败：看到了 {len(rooms['items'])} 个房间")
        if rooms['items']:
            print(f"   第一个房间: {rooms['items'][0]['room_number']}")
else:
    print(f"   ❌ 请求失败: {response.text}")

# 4. 新用户查看支付记录（应该是空的）
print("\n" + "=" * 60)
print("4️⃣ 新用户查看支付记录（预期：空）")
print("=" * 60)

response = session.get(f"{BASE_URL}/payments", headers=headers_auth)
payments = response.json()
if response.status_code == 200:
    print(f"   支付记录数量: {len(payments['items'])}")
    if len(payments['items']) == 0:
        print("   ✅ 用户隔离生效：新用户看不到任何支付记录")
    else:
        print(f"   ❌ 用户隔离失败：看到了 {len(payments['items'])} 条支付记录")
else:
    print(f"   ❌ 请求失败: {response.text}")

# 5. 新用户查看水电记录（应该是空的）
print("\n" + "=" * 60)
print("5️⃣ 新用户查看水电记录（预期：空）")
print("=" * 60)

response = session.get(f"{BASE_URL}/utility/readings", headers=headers_auth)
readings = response.json()
if response.status_code == 200:
    print(f"   水电记录数量: {len(readings['items'])}")
    if len(readings['items']) == 0:
        print("   ✅ 用户隔离生效：新用户看不到任何水电记录")
    else:
        print(f"   ❌ 用户隔离失败：看到了 {len(readings['items'])} 条水电记录")
else:
    print(f"   ❌ 请求失败: {response.text}")

# 6. 新用户创建一个房间（应该成功）
print("\n" + "=" * 60)
print("6️⃣ 新用户创建房间")
print("=" * 60)

new_room = {
    "room_number": "TEST-001",
    "building": "测试楼",
    "floor": 1,
    "area": 50.00,
    "monthly_rent": 1000.00,
    "payment_cycle": 1,
    "tenant_name": "测试租户",
    "lease_start": "2025-01-01",
    "lease_end": "2026-12-31",
    "status": "occupied"
}

response = session.post(f"{BASE_URL}/rooms", json=new_room, headers=headers_auth)
if response.status_code == 201:
    room = response.json()
    print(f"   ✅ 新用户成功创建房间: {room['room_number']}")
    print(f"   房间ID: {room['id']}")
    new_room_id = room['id']
else:
    print(f"   ❌ 创建失败: {response.text}")
    exit(1)

# 7. 新用户再次查看房间列表（应该能看到自己创建的房间）
print("\n" + "=" * 60)
print("7️⃣ 新用户再次查看房间列表（预期：看到自己的1个房间）")
print("=" * 60)

response = session.get(f"{BASE_URL}/rooms", headers=headers_auth)
rooms = response.json()
if response.status_code == 200:
    print(f"   房间数量: {len(rooms['items'])}")
    if len(rooms['items']) == 1 and rooms['items'][0]['room_number'] == "TEST-001":
        print("   ✅ 用户隔离生效：新用户只能看到自己创建的房间")
        print(f"   房间号: {rooms['items'][0]['room_number']}")
    else:
        print(f"   ❌ 用户隔离失败：房间数量或房间号不正确")
        for r in rooms['items']:
            print(f"      - {r['room_number']}")
else:
    print(f"   ❌ 请求失败: {response.text}")

# 8. 用testuser3登录
print("\n" + "=" * 60)
print("8️⃣ 用房东姐姐账户登录")
print("=" * 60)

login_data = {
    "username": "testuser3",
    "password": "test123"
}

response = session.post(f"{BASE_URL}/auth/login", data=login_data, headers=headers)
if response.status_code == 200:
    token = response.json()["access_token"]
    print("   ✅ 房东姐姐登录成功")
else:
    print(f"   ❌ 登录失败: {response.text}")
    exit(1)

headers_auth = {"Authorization": f"Bearer {token}", "X-CSRF-Token": csrf_token}

# 9. 房东姐姐查看房间列表（应该能看到所有房间，包括新用户创建的）
print("\n" + "=" * 60)
print("9️⃣ 房东姐姐查看房间列表（预期：看到所有房间）")
print("=" * 60)

response = session.get(f"{BASE_URL}/rooms", headers=headers_auth)
rooms = response.json()
if response.status_code == 200:
    print(f"   房间数量: {len(rooms['items'])}")
    if len(rooms['items']) > 1:
        print("   ✅ 用户隔离生效：房东姐姐可以看到所有房间")
        print(f"   前3个房间: {[r['room_number'] for r in rooms['items'][:3]]}")

        # 检查是否包含新用户创建的房间
        room_numbers = [r['room_number'] for r in rooms['items']]
        if "TEST-001" in room_numbers:
            print("   ✅ 房东姐姐可以看到新用户创建的房间")
        else:
            print("   ⚠️ 房东姐姐看不到新用户创建的房间")
    else:
        print(f"   ❌ 房间数量不对，应该有多个房间")
else:
    print(f"   ❌ 请求失败: {response.text}")

print("\n" + "=" * 60)
print("✅ 用户隔离功能测试完成！")
print("=" * 60)
