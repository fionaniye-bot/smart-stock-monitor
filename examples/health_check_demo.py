"""健康检查系统演示

演示如何使用健康检查系统和仪表盘处理器的集成功能
"""
import os
import tempfile
import json
import time
from datetime import datetime

from src.dashboard.dashboard_processor import DashboardProcessor
from src.dashboard.health_check import HealthCheckSystem


def demo_health_check_basic():
    """演示健康检查系统基本功能"""
    print("=== 健康检查系统基本功能演示 ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建必要的目录
        os.makedirs(os.path.join(tmpdir, "tasks"), exist_ok=True)
        os.makedirs(os.path.join(tmpdir, "results"), exist_ok=True)

        # 1. 创建健康检查系统
        print("1. 创建健康检查系统...")
        health_check = HealthCheckSystem(base_path=tmpdir)

        # 2. 获取初始状态
        print("2. 获取初始健康状态...")
        initial_status = health_check.get_status()
        print(f"   系统状态: {initial_status.system_status}")
        print(f"   组件数量: {len(initial_status.components)}")
        print(f"   警报数量: {len(initial_status.alerts)}")

        # 3. 更新组件状态
        print("3. 更新组件状态...")
        health_check.update_component_status(
            component_name="demo_component",
            status="running",
            uptime_hours=24,
            version="1.0.0"
        )

        # 4. 添加警报
        print("4. 添加警报...")
        health_check.add_alert(
            level="info",
            component="demo",
            message="演示系统启动",
            details={"start_time": datetime.now().isoformat()}
        )

        health_check.add_alert(
            level="warning",
            component="demo",
            message="磁盘空间使用率较高",
            details={"usage_percent": 87.5}
        )

        # 5. 执行系统检查
        print("5. 执行系统检查...")
        system_check_status = health_check.perform_system_check()
        print(f"   系统检查后状态: {system_check_status.system_status}")

        # 6. 获取最终状态
        print("6. 获取最终健康状态...")
        final_status = health_check.get_status()
        print(f"   最终系统状态: {final_status.system_status}")
        print(f"   组件列表: {list(final_status.components.keys())}")
        print(f"   警报总数: {len(final_status.alerts)}")

        # 显示最近的警报
        print("   最近3条警报:")
        for i, alert in enumerate(final_status.alerts[:3], 1):
            print(f"     {i}. [{alert['level']}] {alert['component']}: {alert['message']}")

        print("\n演示完成！")


def demo_dashboard_processor_integration():
    """演示仪表盘处理器与健康检查的集成"""
    print("\n=== 仪表盘处理器与健康检查集成演示 ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建必要的目录
        os.makedirs(os.path.join(tmpdir, "tasks"), exist_ok=True)
        os.makedirs(os.path.join(tmpdir, "results"), exist_ok=True)

        # 1. 创建仪表盘处理器
        print("1. 创建仪表盘处理器...")
        processor = DashboardProcessor(task_dir=tmpdir, lock_dir=tmpdir)

        # 2. 获取初始健康状态
        print("2. 获取初始健康状态...")
        initial_health = processor.get_health_status()
        print(f"   初始系统状态: {initial_health['system_status']}")

        # 3. 创建并处理任务
        print("3. 创建并处理任务...")
        task_data = {
            "task_id": "demo_task_001",
            "task_type": "data_filter",
            "status": "pending",
            "user_config": {
                "stock_symbols": ["AAPL", "GOOGL"],
                "time_range": {"start": "2024-01-01", "end": "2024-12-31"},
                "filter_conditions": {"min_price": 100}
            }
        }

        task_file = os.path.join(tmpdir, "demo_task_001.json")
        with open(task_file, 'w', encoding='utf-8') as f:
            json.dump(task_data, f)

        # 处理任务
        print("   处理任务中...")
        result = processor.process_task("demo_task_001")
        print(f"   任务处理结果: {'成功' if result else '失败'}")

        # 4. 获取任务后的健康状态
        print("4. 获取任务后的健康状态...")
        post_task_health = processor.get_health_status()
        print(f"   任务后系统状态: {post_task_health['system_status']}")

        # 检查dashboard_processor组件
        dashboard_comp = post_task_health['components'].get('dashboard_processor', {})
        print(f"   仪表盘处理器状态: {dashboard_comp.get('status', 'unknown')}")
        if 'last_successful_task' in dashboard_comp:
            print(f"   最后成功任务: {dashboard_comp['last_successful_task']}")

        # 5. 执行健康检查
        print("5. 执行健康检查...")
        check_result = processor.perform_health_check()
        print(f"   健康检查结果状态: {check_result['system_status']}")

        # 显示系统检查信息
        system_check = check_result['components'].get('system_check', {})
        if 'disk_free_gb' in system_check:
            print(f"   磁盘空间: {system_check['disk_free_gb']:.1f} GB 可用 / "
                  f"{system_check['disk_total_gb']:.1f} GB 总计")

        print("\n演示完成！")


def demo_error_handling_and_alerts():
    """演示错误处理和警报系统"""
    print("\n=== 错误处理和警报系统演示 ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建必要的目录
        os.makedirs(os.path.join(tmpdir, "tasks"), exist_ok=True)
        os.makedirs(os.path.join(tmpdir, "results"), exist_ok=True)

        # 1. 创建健康检查系统
        print("1. 创建健康检查系统...")
        health_check = HealthCheckSystem(base_path=tmpdir)

        # 2. 模拟各种错误
        print("2. 模拟各种错误并添加警报...")

        # 模拟组件故障
        health_check.add_alert(
            level="critical",
            component="data_service",
            message="数据服务连接失败",
            details={
                "error": "Connection timeout",
                "retry_count": 3,
                "last_attempt": datetime.now().isoformat()
            }
        )

        # 模拟性能问题
        health_check.add_alert(
            level="warning",
            component="task_queue",
            message="任务队列积压",
            details={
                "pending_tasks": 150,
                "threshold": 100,
                "avg_processing_time": 45.2
            }
        )

        # 模拟配置问题
        health_check.add_alert(
            level="error",
            component="config_manager",
            message="配置文件验证失败",
            details={
                "config_file": "app_config.yaml",
                "validation_errors": ["missing required field: api_key"]
            }
        )

        # 3. 更新组件状态为错误
        print("3. 更新故障组件状态...")
        health_check.update_component_status(
            component_name="data_service",
            status="critical",
            last_error="Connection timeout",
            error_time=datetime.now().isoformat()
        )

        health_check.update_component_status(
            component_name="task_queue",
            status="warning",
            pending_tasks=150,
            avg_wait_time_seconds=120
        )

        # 4. 获取并显示健康状态
        print("4. 获取健康状态...")
        status = health_check.get_status()
        print(f"   系统状态: {status.system_status}")
        print(f"   组件状态概览:")

        for comp_name, comp_data in status.components.items():
            comp_status = comp_data.get('status', 'unknown')
            print(f"     - {comp_name}: {comp_status}")

        print(f"\n   警报总数: {len(status.alerts)}")
        print("   最近5条警报:")

        for i, alert in enumerate(status.alerts[:5], 1):
            timestamp = alert.get('timestamp', '')[:19]  # 取前19个字符（YYYY-MM-DDTHH:MM:SS）
            print(f"     {i}. [{timestamp}] [{alert['level'].upper():8}] "
                  f"{alert['component']}: {alert['message']}")

        print("\n演示完成！")


def demo_health_check_file_persistence():
    """演示健康状态文件的持久化"""
    print("\n=== 健康状态文件持久化演示 ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建必要的目录
        os.makedirs(os.path.join(tmpdir, "tasks"), exist_ok=True)
        os.makedirs(os.path.join(tmpdir, "results"), exist_ok=True)

        # 1. 第一个健康检查实例
        print("1. 创建第一个健康检查实例并设置状态...")
        health_check1 = HealthCheckSystem(base_path=tmpdir)

        # 设置一些状态
        health_check1.update_component_status(
            component_name="persistence_demo",
            status="running",
            demo_value=42,
            created_at=datetime.now().isoformat()
        )

        health_check1.add_alert(
            level="info",
            component="demo",
            message="第一个实例创建的警报"
        )

        # 获取状态
        status1 = health_check1.get_status()
        print(f"   第一个实例系统状态: {status1.system_status}")

        # 2. 第二个健康检查实例（模拟重启）
        print("2. 创建第二个健康检查实例（模拟重启）...")
        health_check2 = HealthCheckSystem(base_path=tmpdir)

        # 获取状态
        status2 = health_check2.get_status()
        print(f"   第二个实例系统状态: {status2.system_status}")

        # 验证状态持久化
        if "persistence_demo" in status2.components:
            print("   [OK] 组件状态已持久化")
            demo_comp = status2.components["persistence_demo"]
            print(f"     组件值: {demo_comp.get('demo_value')}")
        else:
            print("   [FAIL] 组件状态未持久化")

        # 验证警报持久化
        if len(status2.alerts) > 0:
            print(f"   [OK] 警报已持久化 ({len(status2.alerts)} 条)")
            first_alert = status2.alerts[0]
            if "第一个实例创建的警报" in first_alert.get("message", ""):
                print("   [OK] 警报内容正确")
        else:
            print("   [FAIL] 警报未持久化")

        # 3. 显示健康文件路径
        health_file = os.path.join(tmpdir, "results", "dashboard_health.json")
        print(f"3. 健康状态文件位置: {health_file}")

        if os.path.exists(health_file):
            file_size = os.path.getsize(health_file)
            print(f"   文件大小: {file_size} 字节")

            # 显示文件内容（前几行）
            with open(health_file, 'r', encoding='utf-8') as f:
                content = json.load(f)
                print(f"   系统状态: {content.get('system_status')}")
                print(f"   组件数量: {len(content.get('components', {}))}")
                print(f"   警报数量: {len(content.get('alerts', []))}")

        print("\n演示完成！")


def main():
    """主函数"""
    print("健康检查系统演示程序")
    print("=" * 50)

    try:
        demo_health_check_basic()
        demo_dashboard_processor_integration()
        demo_error_handling_and_alerts()
        demo_health_check_file_persistence()

        print("\n" + "=" * 50)
        print("所有演示完成！")
        print("\n总结:")
        print("- 健康检查系统提供了完整的系统健康监控")
        print("- 支持组件状态管理、警报系统和系统检查")
        print("- 与仪表盘处理器深度集成，增强错误处理")
        print("- 健康状态持久化到文件，支持系统重启")
        print("- 提供详细的错误信息和诊断数据")

    except Exception as e:
        print(f"\n演示过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()