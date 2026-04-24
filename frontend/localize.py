#!/usr/bin/env python3
"""
批量汉化前端 Vue 文件
"""
import re
from pathlib import Path

# 定义翻译映射
TRANSLATIONS = {
    # 通用
    "Dashboard": "租赁管理系统",
    "Room Management": "房间管理",
    "Payment Management": "交租记录",
    "Utility Management": "水电管理",
    "Settings": "设置",
    "Logout": "退出登录",
    "Login": "登录",
    "Register": "注册",
    "Welcome": "欢迎",
    "Back": "返回",
    "Save": "保存",
    "Cancel": "取消",
    "Delete": "删除",
    "Edit": "编辑",
    "View": "查看",
    "Create": "创建",
    "Update": "更新",
    "Search": "搜索",
    "Filter": "筛选",
    "Actions": "操作",
    "Confirm": "确认",
    "Submit": "提交",
    "Close": "关闭",
    "Loading": "加载中...",
    "No Data": "暂无数据",
    "Error": "错误",
    "Success": "成功",
    
    # 房间相关
    "Add Room": "添加房间",
    "Edit Room": "编辑房间",
    "Delete Room": "删除房间",
    "Room Number": "房间号",
    "Building": "楼栋",
    "Floor": "楼层",
    "Area": "面积",
    "Monthly Rent": "月租金",
    "Deposit": "押金",
    "Status": "状态",
    "Tenant Name": "租客姓名",
    "Tenant Phone": "租客电话",
    "Lease Start": "租期开始",
    "Lease End": "租期结束",
    "Payment Cycle": "付款周期",
    "Description": "描述",
    "Available": "空置",
    "Occupied": "已出租",
    "Maintenance": "维修中",
    "Manage your rooms": "管理您的房间",
    "Manage your rental rooms and tenants": "管理您的租赁房间和租客",
    "Search by room number, building, or tenant": "按房间号、楼栋或租客搜索...",
    
    # 交租相关
    "Add Payment": "添加交租记录",
    "Payment Date": "交租日期",
    "Amount": "金额",
    "Payment Method": "支付方式",
    "Cash": "现金",
    "Bank Transfer": "银行转账",
    "WeChat Pay": "微信支付",
    "Alipay": "支付宝",
    "Completed": "已完成",
    "Pending": "待处理",
    "Failed": "失败",
    "View payment history": "查看交租历史",
    "Record a payment": "记录交租",
    "Payment Type": "付款类型",
    "Due Date": "到期日期",
    
    # 水电相关
    "Utility Readings": "水电读数",
    "Water": "水",
    "Electricity": "电",
    "Gas": "气",
    "Reading Date": "读表日期",
    "Current Reading": "当前读数",
    "Previous Reading": "上次读数",
    "Usage": "用量",
    "Rate Used": "费率",
    "Amount (CNY)": "金额（元）",
    "Record Reading": "记录读数",
    "Utility readings and rates": "水电读数和费率",
    
    # 确认消息
    "Are you sure you want to delete": "确定要删除吗",
    "This action cannot be undone": "此操作无法撤销",
    "Confirm Delete": "确认删除",
    "Room deleted successfully": "房间删除成功",
    "Room updated successfully": "房间更新成功",
    "Room created successfully": "房间创建成功",
    "Payment recorded successfully": "交租记录成功",
    "Reading recorded successfully": "读数记录成功",
    "Failed to load rooms": "加载房间失败",
    "Failed to save room": "保存房间失败",
    "Failed to delete room": "删除房间失败",
    "Failed to load payments": "加载交租记录失败",
    "Failed to record payment": "记录交租失败",
    
    # 表单验证
    "Please enter": "请输入",
    "is required": "是必填项",
    "Invalid": "无效的",
    "must be greater than": "必须大于",
    "must be less than": "必须小于",
    
    # 分页
    "Total": "共",
    "items": "条",
    "Go to": "前往",
    "Page": "页",
}

def localize_file(file_path: Path) -> int:
    """汉化单个文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # 按长度排序，先替换长的短语（避免部分替换）
        for en, zh in sorted(TRANSLATIONS.items(), key=lambda x: len(x[0]), reverse=True):
            # 只替换在引号或模板中的文本
            # 替换 HTML 属性中的文本
            content = re.sub(
                f'placeholder="({re.escape(en)})"',
                f'placeholder="{zh}"',
                content
            )
            # 替换 label 属性
            content = re.sub(
                f'label="({re.escape(en)})"',
                f'label="{zh}"',
                content
            )
            # 替换按钮文本
            content = re.sub(
                f'>\\s*{re.escape(en)}\\s*<',
                f'>{zh}<',
                content
            )
            # 替换变量赋值中的字符串
            content = re.sub(
                f"['\"]({re.escape(en)})['\"]",
                f"'{zh}'",
                content
            )
            # 替换模板中的纯文本（需要更谨慎）
            # 替换 <h1>, <h2>, <h3>, <p> 标签中的内容
            for tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'span', 'div']:
                content = re.sub(
                    f'<{tag}[^>]*>(\\s*){re.escape(en)}(\\s*)</{tag}>',
                    f'<{tag}\\1{zh}\\2</{tag}>',
                    content,
                    flags=re.IGNORECASE
                )
        
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return 1
        return 0
    except Exception as e:
        print(f"  ❌ 处理失败: {e}")
        return 0

def main():
    base_path = Path("/home/agentuser/rent-management-system/frontend/src")
    
    # 查找所有 Vue 文件
    vue_files = list(base_path.rglob("*.vue"))
    
    print(f"🚀 开始汉化，找到 {len(vue_files)} 个 Vue 文件...")
    
    count = 0
    for file_path in vue_files:
        print(f"  📝 处理: {file_path.relative_to(base_path)}")
        if localize_file(file_path):
            count += 1
            print(f"    ✅ 已更新")
        else:
            print(f"    ⏭️  无需更新")
    
    print(f"\n✅ 汉化完成！共更新 {count} 个文件")

if __name__ == "__main__":
    main()
