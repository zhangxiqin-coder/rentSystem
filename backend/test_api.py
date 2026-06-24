import requests
from datetime import date

# 先登录获取token
login_response = requests.post(
    'http://localhost:8000/api/v1/auth/login',
    json={'username': 'xiqin2026', 'password': 'xiqin2026'}
)

if login_response.status_code != 200:
    print(f"❌ 登录失败: {login_response.status_code}")
    print(login_response.text)
    exit(1)

token = login_response.json()['access_token']
headers = {'Authorization': f'Bearer {token}'}

print("=" * 80)
print(f"✅ 登录成功,用户: xiqin2026")
print("=" * 80)

# 调用逾期房间API
response = requests.get(
    'http://localhost:8000/api/v1/reminders/overdue-rooms',
    headers=headers,
    params={'advance_rent_days': 0}
)

if response.status_code != 200:
    print(f"❌ API调用失败: {response.status_code}")
    print(response.text)
    exit(1)

data = response.json()

print(f"\n📊 逾期房间统计:")
print(f"  - 已逾期: {data['overdue_count']} 个")
print(f"  - 即将到期: {data['expiring_count']} 个")

print(f"\n💰 已逾期房间 ({len(data['overdue'])}个):")
for room in data['overdue']:
    print(f"  - {room['room_number']}: 逾期{room.get('overdue_days', '?')}天, 欠费¥{room['total_amount']:.2f}")

print(f"\n📅 即将到期房间 ({len(data['expiring'])}个):")
for room in data['expiring']:
    days = room.get('days_until_due', room['days_to_due'])
    paid_status = "✅已支付" if room['days_to_due'] >= 0 else "❌未支付"
    print(f"  - {room['room_number']}: {days}天后到期, ¥{room['total_amount']:.2f}, {paid_status}")

# 检查102A-4是否在列表中
expiring_numbers = [r['room_number'] for r in data['expiring']]
if '102A-4' in expiring_numbers:
    print(f"\n✅ 102A-4 在即将到期列表中!")
    room_102a4 = next(r for r in data['expiring'] if r['room_number'] == '102A-4')
    print(f"   - {room_102a4['days_to_due']}天后到期")
    print(f"   - 金额: ¥{room_102a4['total_amount']:.2f}")
else:
    print(f"\n❌ 102A-4 不在即将到期列表中")
    print(f"   即将到期的房间: {expiring_numbers}")
