#!/usr/bin/env python3
"""
导入旧数据到租赁管理系统
从 /home/agentuser/test 目录导入房间信息和交租记录
"""
import json
import sqlite3
from datetime import datetime
from pathlib import Path

# 数据库路径
DB_PATH = "/home/agentuser/rent-management-system/backend/rent_management.db"

# 旧数据路径
OLD_DATA_DIR = "/home/agentuser/test"
UTILITIES_FILE = f"{OLD_DATA_DIR}/rent_utilities.json"
PAID_FILE = f"{OLD_DATA_DIR}/rent_paid.json"

# 默认用户ID（testuser3）
DEFAULT_USER_ID = 3


def parse_room_number(room_str):
    """解析房间号，提取楼栋、楼层、房间号"""
    # 例如: "102-1" -> building: "1", floor: "0", room_number: "02-1"
    # 例如: "9-302-2" -> building: "9", floor: "3", room_number: "302-2"

    parts = room_str.split("-")
    if len(parts) == 2:
        # 格式: "102-1"
        return {
            "building": parts[0][0] if parts[0] else "1",
            "floor": parts[0][1] if len(parts[0]) > 1 else "0",
            "room_number": room_str,
            "full_number": room_str
        }
    elif len(parts) >= 3:
        # 格式: "9-302-2"
        return {
            "building": parts[0],
            "floor": parts[1][0] if parts[1] else "0",
            "room_number": room_str,
            "full_number": room_str
        }
    else:
        # 格式: "102"
        return {
            "building": room_str[0] if room_str else "1",
            "floor": room_str[1] if len(room_str) > 1 else "0",
            "room_number": room_str,
            "full_number": room_str
        }


def main():
    print("🚀 开始导入旧数据...")

    # 读取水电费数据
    print(f"\n📖 读取 {UTILITIES_FILE}...")
    with open(UTILITIES_FILE, "r", encoding="utf-8") as f:
        utilities_data = json.load(f)

    # 读取已交租数据
    print(f"📖 读取 {PAID_FILE}...")
    with open(PAID_FILE, "r", encoding="utf-8") as f:
        paid_data = json.load(f)

    # 创建已交租映射 (room_number -> paid_info)
    paid_map = {}
    for item in paid_data.get("paid_rooms", []):
        paid_map[item["room"]] = {
            "paid_date": item.get("paid_date"),
            "note": item.get("note", "")
        }

    # 连接数据库
    print(f"\n🔗 连接数据库: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 统计
    rooms_created = 0
    readings_created = 0
    payments_created = 0

    # 导入每个房间
    print(f"\n📦 开始导入 {len(utilities_data['rooms'])} 个房间...")

    for room_data in utilities_data["rooms"]:
        room_str = room_data["room"]
        room_info = parse_room_number(room_str)

        # 检查房间是否已存在
        cursor.execute(
            "SELECT id FROM rooms WHERE room_number = ?",
            (room_str,)
        )
        existing = cursor.fetchone()

        if existing:
            room_id = existing[0]
            print(f"  ⚠️  房间 {room_str} 已存在，跳过创建")
        else:
            # 创建房间
            lease_start = "2026-01-01"  # 默认租期开始
            lease_end = "2026-12-31"    # 默认租期结束
            payment_cycle = 1           # 默认按月付

            cursor.execute("""
                INSERT INTO rooms (
                    room_number, building, floor,
                    monthly_rent, lease_start, lease_end,
                    payment_cycle, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                room_str,
                room_info["building"],
                int(room_info["floor"]),
                room_data.get("rent", 0),
                lease_start,
                lease_end,
                payment_cycle,
                "occupied",  # 默认已出租
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ))
            room_id = cursor.lastrowid
            rooms_created += 1
            print(f"  ✅ 创建房间: {room_str} (房租 ¥{room_data.get('rent', 0)})")

        # 创建水电读数记录
        last_water = room_data.get("last_water", 0)
        last_electric = room_data.get("last_electric", 0)
        updated_date = room_data.get("updated", datetime.now().strftime("%Y-%m-%d"))

        if last_water > 0 or last_electric > 0:
            cursor.execute("""
                INSERT INTO utility_readings (
                    room_id, utility_type,
                    reading, reading_date, previous_reading, notes
                ) VALUES (?, 'water', ?, ?, ?, ?)
            """, (room_id, last_water, updated_date, 0,
                  "导入的历史数据"))

            cursor.execute("""
                INSERT INTO utility_readings (
                    room_id, utility_type,
                    reading, reading_date, previous_reading, notes
                ) VALUES (?, 'electricity', ?, ?, ?, ?)
            """, (room_id, last_electric, updated_date, 0,
                  "导入的历史数据"))

            readings_created += 2
            print(f"    💧 水电读数: 水 {last_water} 吨, 电 {last_electric} 度")

        # 创建交租记录（如果有）
        last_paid = room_data.get("last_paid", "")
        if last_paid:
            # 计算金额
            rent_amount = room_data.get("rent", 0)

            # 尝试从 paid_map 获取详细信息
            paid_info = paid_map.get(room_str, {})
            note = paid_info.get("note", "")

            # 解析水电费（如果备注中有）
            water_fee = 0
            electric_fee = 0
            if note:
                # 例如: "¥1,465（房租¥1,350 + 水电¥115）"
                import re
                match = re.search(r'水电¥(\d+)', note)
                if match:
                    utility_total = int(match.group(1))
                    # 简单按比例分配（水费较高）
                    water_fee = int(utility_total * 0.6)
                    electric_fee = utility_total - water_fee

            cursor.execute("""
                INSERT INTO payments (
                    room_id, amount, payment_date,
                    payment_type, payment_method, status, description
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                room_id,
                rent_amount + water_fee + electric_fee,
                last_paid,
                "rent",  # 默认房租类型
                "cash",  # 默认现金
                "completed",
                f"导入的历史交租记录. 房租¥{rent_amount}. {note}"
            ))
            payments_created += 1
            print(f"    💰 交租记录: {last_paid} (¥{rent_amount + water_fee + electric_fee})")

    # 提交事务
    conn.commit()
    conn.close()

    print(f"\n✅ 导入完成!")
    print(f"   📊 统计:")
    print(f"      - 创建房间: {rooms_created}")
    print(f"      - 创建水电读数: {readings_created}")
    print(f"      - 创建交租记录: {payments_created}")
    print(f"\n🎉 数据已成功导入到 {DB_PATH}")


if __name__ == "__main__":
    main()
