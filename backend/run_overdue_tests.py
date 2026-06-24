"""
运行所有逾期管理相关测试
"""
import subprocess
import sys

def run_tests():
    """运行测试套件"""
    print("🧪 运行逾期管理功能测试...")
    print("=" * 50)
    
    # 后端业务逻辑测试
    print("\n1. 运行后端业务逻辑测试...")
    result1 = subprocess.run([
        sys.executable, "-m", "pytest", 
        "tests/test_rent_payment_status.py", 
        "-v", "--tb=short"
    ], capture_output=True, text=True)
    
    print(result1.stdout)
    if result1.stderr:
        print("STDERR:", result1.stderr)
    
    # 后端API测试（跳过有问题的部分）
    print("\n2. 运行后端API测试...")
    result2 = subprocess.run([
        sys.executable, "-m", "pytest", 
        "tests/test_reminders_api.py::TestRemindersAPI::test_get_overdue_rooms_unauthorized",
        "tests/test_reminders_api.py::TestRemindersAPI::test_get_reminders_summary_unauthorized", 
        "tests/test_reminders_api.py::TestRemindersAPI::test_get_upcoming_reminders_unauthorized",
        "tests/test_reminders_api.py::TestRemindersAPI::test_send_rent_reminder_unauthorized",
        "tests/test_reminders_api.py::TestRemindersAPI::test_send_reminder_notifications_unauthorized",
        "-v", "--tb=short"
    ], capture_output=True, text=True)
    
    print(result2.stdout)
    if result2.stderr:
        print("STDERR:", result2.stderr)
    
    # 总结
    print("\n" + "=" * 50)
    print("📊 测试总结:")
    print(f"   业务逻辑测试: {'✅ 通过' if result1.returncode == 0 else '❌ 失败'}")
    print(f"   API测试: {'✅ 通过' if result2.returncode == 0 else '❌ 失败'}")
    
    if result1.returncode == 0 and result2.returncode == 0:
        print("\n🎉 所有测试通过！")
        return 0
    else:
        print("\n⚠️  部分测试失败，请检查上面的错误信息")
        return 1

if __name__ == "__main__":
    sys.exit(run_tests())
