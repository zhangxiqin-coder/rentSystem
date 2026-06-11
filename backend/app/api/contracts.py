"""
房屋租赁合同生成API
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pathlib import Path
from typing import Optional
from datetime import date, datetime
import os

router = APIRouter()

# 项目路径配置
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent  # 到达项目根目录
TEMPLATE_PATH = BASE_DIR / "frontend" / "public" / "templates" / "lease-contract-template.html"


@router.get("/generate-contract/{lease_record_id}", response_class=HTMLResponse)
async def generate_lease_contract(
    lease_record_id: int,
    keys_count: Optional[int] = 2,
    electricity_initial_reading: Optional[float] = None,
    water_initial_reading: Optional[float] = None
):
    """
    生成房屋租赁合同 HTML

    参数：
    - lease_record_id: 租赁记录ID
    - keys_count: 交付钥匙数量（默认2把）
    - electricity_initial_reading: 电表起始读数（可选，默认使用租赁记录中的读数）
    - water_initial_reading: 水表起始读数（可选，默认使用租赁记录中的读数）

    返回：HTML格式的合同内容
    """
    from app.models import Room, UtilityReading, User, LeaseRecord, Tenant
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        # 查询租赁记录
        lease_record = db.query(LeaseRecord).filter(LeaseRecord.id == lease_record_id).first()
        if not lease_record:
            raise HTTPException(status_code=404, detail="租赁记录不存在")

        # 获取房间信息
        room = lease_record.room
        if not room:
            raise HTTPException(status_code=404, detail="房间不存在")

        # 获取租客信息
        tenant = lease_record.tenant
        if not tenant:
            raise HTTPException(status_code=404, detail="租客不存在")

        # 获取房东信息
        landlord = db.query(User).filter(User.id == lease_record.owner_id).first()
        
        # 如果房东没有设置姓名和电话，使用默认值
        landlord_name = landlord.landlord_name if landlord and landlord.landlord_name else "张锡琴"
        landlord_phone = landlord.landlord_phone if landlord and landlord.landlord_phone else "13806504936"

        # 获取初始水电读数：优先使用租赁记录中的读数
        if electricity_initial_reading is None:
            electricity_initial_reading = float(lease_record.initial_electricity_reading) if lease_record.initial_electricity_reading else 0

        if water_initial_reading is None:
            water_initial_reading = float(lease_record.initial_water_reading) if lease_record.initial_water_reading else 0

        # 如果读数为0，转换为空字符串用于显示
        electricity_display = "" if electricity_initial_reading == 0 else f"{electricity_initial_reading} 度"
        water_display = "" if water_initial_reading == 0 else f"{water_initial_reading} 吨"
        
        # 备注逻辑：读数为0时显示备注，否则为空
        electricity_note = "以实际入住时候为准" if electricity_initial_reading == 0 else ""
        water_note = "以实际入住时候为准" if water_initial_reading == 0 else ""

        # 获取宽带费：从房间信息中读取
        broadband_fee = float(room.broadband_fee) if room.broadband_fee else 0
        broadband_note = ""  # 宽带费为0时不显示备注

        # 读取HTML模板
        if not TEMPLATE_PATH.exists():
            raise HTTPException(status_code=500, detail="合同模板文件不存在")

        with open(TEMPLATE_PATH, 'r', encoding='utf-8') as f:
            template = f.read()

        # 解析房间号（使用楼栋+房间号）
        building = room.building or ""
        room_num = room.room_number

        # 计算租赁月数
        lease_months = 0
        if lease_record.lease_start and lease_record.lease_end:
            # 计算月数差异
            year_diff = lease_record.lease_end.year - lease_record.lease_start.year
            month_diff = lease_record.lease_end.month - lease_record.lease_start.month
            lease_months = year_diff * 12 + month_diff

        # 签订日期默认为今天
        today = date.today()
        sign_year = today.year
        sign_month = today.month
        sign_day = today.day

        # 填充模板数据
        contract_data = {
            # 房东信息（从数据库读取）
            "landlord_name": landlord_name,
            "landlord_phone": landlord_phone,

            # 租客信息（从租赁记录获取）
            "tenant_name": tenant.name or "",
            "tenant_id_card": tenant.id_card or "",
            "tenant_phone": tenant.phone or "",

            # 房屋信息
            "building": building,
            "room": room_num,

            # 租赁条款（从租赁记录获取）
            "lease_months": lease_months,
            "lease_start_year": lease_record.lease_start.year if lease_record.lease_start else "",
            "lease_start_month": lease_record.lease_start.month if lease_record.lease_start else "",
            "lease_start_day": lease_record.lease_start.day if lease_record.lease_start else "",
            "lease_end_year": lease_record.lease_end.year if lease_record.lease_end else "",
            "lease_end_month": lease_record.lease_end.month if lease_record.lease_end else "",
            "lease_end_day": lease_record.lease_end.day if lease_record.lease_end else "",

            # 租金和押金（从租赁记录获取）
            "monthly_rent": float(lease_record.monthly_rent) if lease_record.monthly_rent else 0,
            "payment_cycle": room.payment_cycle or 1,
            "deposit_amount": float(lease_record.deposit_amount) if lease_record.deposit_amount else 0,

            # 设施信息
            "keys_count": keys_count,

            # 水电信息（从租赁记录获取初始读数，从房间获取费率）
            "electricity_initial_reading": electricity_display,
            "electricity_rate": float(room.electricity_rate) if room.electricity_rate else 1.0,
            "electricity_note": electricity_note,
            "water_initial_reading": water_display,
            "water_rate": float(room.water_rate) if room.water_rate else 5.0,
            "water_note": water_note,
            "broadband_fee": broadband_fee,
            "broadband_note": "" if broadband_fee > 0 else "",

            # 签字日期
            "sign_year": sign_year,
            "sign_month": sign_month,
            "sign_day": sign_day,
        }

        # 替换模板占位符
        for key, value in contract_data.items():
            placeholder = f"{{{{ {key} }}}}"
            template = template.replace(placeholder, str(value))

        return template

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成合同失败: {str(e)}")
    finally:
        db.close()
