"""
房屋租赁合同生成API
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, Response
from pathlib import Path
from typing import Optional
from datetime import date, datetime
import os
import io
import tempfile

from weasyprint import HTML

router = APIRouter()

# 项目路径配置
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent  # 到达项目根目录
TEMPLATE_PATH = BASE_DIR / "frontend" / "public" / "templates" / "lease-contract-template.html"
TEMPLATE_GOLING_PATH = BASE_DIR / "frontend" / "public" / "templates" / "lease-contract-template-goling.html"


def get_contract_template(series: str) -> Path:
    """根据房间系列返回对应的合同模板"""
    series = str(series or "").strip()
    # 2-2501系列使用果岭合同模板
    if series.startswith("2-2501") or series == "2-2501":
        if TEMPLATE_GOLING_PATH.exists():
            return TEMPLATE_GOLING_PATH
        # fallback: 如果果岭模板不存在，使用默认模板
        return TEMPLATE_PATH
    # 其他系列使用默认模板
    return TEMPLATE_PATH


def inject_editable_features(html: str) -> str:
    """
    给已填充数据的合同HTML注入编辑功能：
    1. 整个合同区域设为contenteditable
    2. 添加浮动工具栏（打印按钮）
    3. 添加编辑提示
    4. 打印时隐藏工具栏和编辑边框
    """
    editable_css = """
    <style id="editable-mode">
        /* 编辑模式专用样式 */
        body {
            background: #f0f2f5 !important;
            padding: 20px 0 !important;
        }

        .contract-container {
            box-shadow: 0 2px 20px rgba(0,0,0,0.15) !important;
            outline: 2px dashed transparent;
            outline-offset: 4px;
            transition: outline-color 0.2s;
        }

        .contract-container:hover {
            outline-color: #409eff;
        }

        .contract-container:focus {
            outline: 2px solid #409eff !important;
            outline-offset: 4px;
        }

        /* 浮动工具栏 */
        .editable-toolbar {
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
            background: white;
            border-radius: 8px;
            box-shadow: 0 4px 16px rgba(0,0,0,0.2);
            padding: 12px;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .editable-toolbar button {
            padding: 8px 16px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
            font-weight: bold;
            white-space: nowrap;
        }

        .editable-toolbar .btn-print {
            background: #409eff;
            color: white;
        }

        .editable-toolbar .btn-print:hover {
            background: #66b1ff;
        }

        .editable-toolbar .btn-hint {
            background: #f4f4f5;
            color: #909399;
            font-size: 12px;
            font-weight: normal;
            cursor: default;
            text-align: center;
            line-height: 1.4;
        }

        /* 编辑提示横幅 */
        .editable-banner {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            background: linear-gradient(90deg, #409eff, #66b1ff);
            color: white;
            text-align: center;
            padding: 6px;
            font-size: 13px;
            z-index: 9998;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }

        /* 打印时隐藏工具元素 */
        @media print {
            .editable-toolbar,
            .editable-banner {
                display: none !important;
            }

            body {
                background: #fff !important;
                padding: 0 !important;
            }

            .contract-container {
                box-shadow: none !important;
                outline: none !important;
            }
        }
    </style>
    """

    editable_html = """
    <!-- 编辑模式横幅 -->
    <div class="editable-banner">
        ✏️ 编辑模式 — 直接点击合同内容即可修改，完成后点击右上角「打印 / 保存PDF」
    </div>

    <!-- 编辑模式工具栏 -->
    <div class="editable-toolbar">
        <button class="btn-hint">📝 可直接编辑<br>合同任意内容</button>
        <button class="btn-print" onclick="window.print()">🖨️ 打印 / 保存PDF</button>
    </div>
    """

    # 1. 注入CSS到 </head> 之前
    html = html.replace("</head>", editable_css + "\n</head>")

    # 2. 在 <body> 后面注入横幅和工具栏
    # 处理 <body> 和 <body class="..."> 两种情况
    import re
    body_match = re.search(r'<body[^>]*>', html)
    if body_match:
        body_tag = body_match.group()
        html = html.replace(body_tag, body_tag + "\n" + editable_html)

    # 3. 让合同容器可编辑
    # 找到 contract-container 的div，添加 contenteditable
    html = html.replace(
        '<div class="contract-container">',
        '<div class="contract-container" contenteditable="true" spellcheck="false">',
    )
    # 处理可能的其他格式
    if 'contenteditable="true"' not in html:
        html = re.sub(
            r'<div class="contract-container"[^>]*>',
            lambda m: m.group().replace('>', ' contenteditable="true" spellcheck="false">'),
            html,
        )

    return html


@router.get("/generate-contract/{lease_record_id}", response_class=HTMLResponse)
async def generate_lease_contract(
    lease_record_id: int,
    keys_count: Optional[int] = 2,
    electricity_initial_reading: Optional[float] = None,
    water_initial_reading: Optional[float] = None,
    editable: Optional[bool] = False
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

        # 根据房间系列选择模板
        series = room.series or ""
        template_path = get_contract_template(series)
        if not template_path.exists():
            raise HTTPException(status_code=500, detail=f"合同模板文件不存在: {template_path}")

        with open(template_path, 'r', encoding='utf-8') as f:
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

        # 签订日期：如果租期开始日期早于今天，用租期开始日期，否则用今天
        today = date.today()
        if lease_record.lease_start and lease_record.lease_start < today:
            sign_date = lease_record.lease_start
        else:
            sign_date = today
        sign_year = sign_date.year
        sign_month = sign_date.month
        sign_day = sign_date.day

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

        # 如果是编辑模式，注入编辑功能
        if editable:
            template = inject_editable_features(template)

        return template

    except Exception as e:
        import traceback
        error_detail = f"生成合同失败: {str(e)}\n{traceback.format_exc()}"
        print(error_detail)
        raise HTTPException(status_code=500, detail=error_detail)
    finally:
        db.close()


@router.get("/generate-contract-pdf/{lease_record_id}")
async def generate_lease_contract_pdf(
    lease_record_id: int,
    keys_count: Optional[int] = 2
):
    """
    生成房屋租赁合同 PDF 文件下载

    - 先生成 HTML 合同
    - 再用 weasyprint 转为 PDF
    - 返回 PDF 文件下载
    """
    # 先生成 HTML 合同
    html_content = await generate_lease_contract(lease_record_id, keys_count)

    if isinstance(html_content, HTMLResponse):
        html_str = html_content.body.decode('utf-8')
    else:
        html_str = str(html_content)

    try:
        # 将 HTML 转为 PDF
        html_bytes = html_str.encode('utf-8')
        pdf_file = io.BytesIO()
        HTML(string=html_str, base_url=str(BASE_DIR), encoding='utf-8').write_pdf(pdf_file)
        pdf_file.seek(0)

        # 获取租客姓名用于文件名
        from app.models import LeaseRecord
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            lease_record = db.query(LeaseRecord).filter(LeaseRecord.id == lease_record_id).first()
            tenant_name = lease_record.tenant.name if lease_record and lease_record.tenant else "租客"
            room_num = lease_record.room.room_number if lease_record and lease_record.room else "房间"
        finally:
            db.close()

        from urllib.parse import quote
        filename = f"房屋租赁合同_{room_num}_{tenant_name}.pdf"
        encoded_filename = quote(filename)

        return Response(
            content=pdf_file.getvalue(),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
            }
        )
    except Exception as e:
        import traceback
        error_detail = f"生成PDF失败: {str(e)}\n{traceback.format_exc()}"
        print(error_detail)
        raise HTTPException(status_code=500, detail=error_detail)
