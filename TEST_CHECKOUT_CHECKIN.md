# 退租和入住功能测试指南

## 功能说明

1. **退租功能**：房间从"已出租"变为"空置"，创建退租退款记录
2. **入住功能**：房间从"空置"变为"已出租"，填写租客信息
3. **支付记录**：退租记录以负数金额显示，与房租记录在同一页面展示

## 测试账号
- 访问: http://43.134.40.91:5173
- 账号: testuser / Test12345

## 测试步骤

### 退租流程
1. 进入"房间管理"页面
2. 找到一个"已出租"的房间（如房间101）
3. 点击"退租"按钮
4. 填写退款金额、日期、原因和方式
5. 确认后房间变空置，租客信息清空
6. 检查"支付记录"页面，应该有一条负数金额的退租记录（红色显示）

### 入住流程
1. 在"房间管理"页面找一个"空置"的房间
2. 点击"入住"按钮
3. 填写租客姓名、电话、租约日期等信息
4. 确认后房间变已出租，显示租客信息

## 数据库验证

查看房间101的状态：
```bash
cd backend
./venv/bin/python3 << 'EOF'
from app.database import SessionLocal
from app.models import Room

db = SessionLocal()
room = db.query(Room).filter(Room.id == 45).first()
if room:
    print(f"房间号: {room.room_number}")
    print(f"状态: {room.status}")
    print(f"租客: {room.tenant_name or '无'}")
    print(f"租约期: {room.lease_start} 至 {room.lease_end}")
db.close()
EOF
```

查看支付记录：
```bash
./venv/bin/python3 << 'EOF'
from app.database import SessionLocal
from app.models import Payment

db = SessionLocal()
payments = db.query(Payment).filter(Payment.room_id == 45).all()
for p in payments:
    print(f"{p.payment_date} - {p.payment_type} - ¥{p.amount} - {p.description}")
db.close()
EOF
```

## 完成状态
✅ 后端API开发完成（checkout和checkin端点）
✅ 前端UI实现完成（退租和入住按钮及表单）
✅ 数据库逻辑验证通过（房间状态切换、支付记录创建）
✅ 支付记录展示验证通过（负数金额红色显示）
✅ 水电记录优化完成（已收记录禁用标记按钮）
