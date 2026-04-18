"""健康检查系统测试

测试HealthCheckSystem类的功能，包括健康状态管理、警报系统和系统检查
"""
import os
import json
import tempfile
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from src.dashboard.models import HealthStatus
from src.dashboard.health_check import HealthCheckSystem


def test_health_check_system_initialization():
    """测试健康检查系统初始化"""
    with tempfile.TemporaryDirectory() as tmpdir:
        health_check = HealthCheckSystem(base_path=tmpdir)

        # 检查健康文件路径
        expected_health_file = os.path.join(tmpdir, "results", "dashboard_health.json")
        assert health_check.health_file == expected_health_file

        # 检查目录是否创建
        results_dir = os.path.join(tmpdir, "results")
        assert os.path.exists(results_dir)


def test_get_status_initial():
    """测试获取初始健康状态"""
    with tempfile.TemporaryDirectory() as tmpdir:
        health_check = HealthCheckSystem(base_path=tmpdir)
        status = health_check.get_status()

        # 验证初始状态
        assert isinstance(status, HealthStatus)
        assert status.system_status == "healthy"
        assert len(status.components) == 3  # dashboard, data_service, task_queue
        assert len(status.alerts) == 0

        # 验证组件状态
        assert "dashboard" in status.components
        assert "data_service" in status.components
        assert "task_queue" in status.components

        # 验证健康文件已创建
        health_file = os.path.join(tmpdir, "results", "dashboard_health.json")
        assert os.path.exists(health_file)


def test_get_status_from_existing_file():
    """测试从现有文件获取健康状态"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 先创建一个健康状态文件
        health_file = os.path.join(tmpdir, "results", "dashboard_health.json")
        os.makedirs(os.path.dirname(health_file), exist_ok=True)

        existing_status = {
            "system_status": "warning",
            "last_check": "2024-01-01T10:00:00",
            "components": {
                "dashboard": {"status": "running", "last_heartbeat": "2024-01-01T10:00:00"},
                "data_service": {"status": "warning", "last_update": "2024-01-01T09:30:00"}
            },
            "alerts": [
                {"level": "warning", "component": "data_service", "message": "数据更新延迟"}
            ]
        }

        with open(health_file, 'w', encoding='utf-8') as f:
            json.dump(existing_status, f)

        # 创建健康检查系统并获取状态
        health_check = HealthCheckSystem(base_path=tmpdir)
        status = health_check.get_status()

        # 验证从文件加载的状态
        assert status.system_status == "warning"
        assert len(status.components) == 2  # 只有dashboard和data_service
        assert len(status.alerts) == 1
        assert status.alerts[0]["message"] == "数据更新延迟"


def test_get_status_corrupted_file():
    """测试处理损坏的健康状态文件"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建一个损坏的JSON文件
        health_file = os.path.join(tmpdir, "results", "dashboard_health.json")
        os.makedirs(os.path.dirname(health_file), exist_ok=True)

        with open(health_file, 'w', encoding='utf-8') as f:
            f.write("{invalid json")

        # 应该返回初始状态而不抛出异常
        health_check = HealthCheckSystem(base_path=tmpdir)
        status = health_check.get_status()

        # 应该返回初始健康状态
        assert status.system_status == "healthy"
        assert len(status.components) == 3
        assert len(status.alerts) == 0


def test_update_component_status():
    """测试更新组件状态"""
    with tempfile.TemporaryDirectory() as tmpdir:
        health_check = HealthCheckSystem(base_path=tmpdir)

        # 更新组件状态
        health_check.update_component_status(
            component_name="dashboard",
            status="running",
            last_heartbeat=datetime.now().isoformat(),
            uptime_days=30
        )

        # 获取状态并验证
        status = health_check.get_status()
        assert "dashboard" in status.components
        assert status.components["dashboard"]["status"] == "running"
        assert "last_heartbeat" in status.components["dashboard"]
        assert "uptime_days" in status.components["dashboard"]
        assert status.components["dashboard"]["uptime_days"] == 30


def test_update_component_status_affects_system_status():
    """测试组件状态更新如何影响系统状态"""
    with tempfile.TemporaryDirectory() as tmpdir:
        health_check = HealthCheckSystem(base_path=tmpdir)

        # 初始状态应该是healthy
        status1 = health_check.get_status()
        assert status1.system_status == "healthy"

        # 添加warning组件
        health_check.update_component_status("data_service", "warning", last_update=datetime.now().isoformat())
        status2 = health_check.get_status()
        assert status2.system_status == "warning"

        # 添加critical组件
        health_check.update_component_status("task_queue", "critical", pending_tasks=1000)
        status3 = health_check.get_status()
        assert status3.system_status == "critical"

        # 修复组件
        health_check.update_component_status("task_queue", "running", pending_tasks=10)
        status4 = health_check.get_status()
        assert status4.system_status == "warning"  # 仍然有warning组件


def test_add_alert():
    """测试添加警报"""
    with tempfile.TemporaryDirectory() as tmpdir:
        health_check = HealthCheckSystem(base_path=tmpdir)

        # 添加几个警报
        health_check.add_alert(
            level="warning",
            component="data_service",
            message="数据更新延迟超过30分钟",
            details={"delay_minutes": 35}
        )

        health_check.add_alert(
            level="critical",
            component="task_queue",
            message="任务队列积压超过1000个任务",
            details={"pending_tasks": 1200}
        )

        # 获取状态并验证警报
        status = health_check.get_status()
        assert len(status.alerts) == 2

        # 验证警报（最新的在前面）
        # 第一个警报应该是最后添加的critical警报
        alert1 = status.alerts[0]
        assert alert1["level"] == "critical"
        assert alert1["component"] == "task_queue"
        assert alert1["message"] == "任务队列积压超过1000个任务"
        assert alert1["details"]["pending_tasks"] == 1200
        assert "timestamp" in alert1

        # 第二个警报应该是之前添加的warning警报
        alert2 = status.alerts[1]
        assert alert2["level"] == "warning"
        assert alert2["component"] == "data_service"
        assert alert2["message"] == "数据更新延迟超过30分钟"
        assert alert2["details"]["delay_minutes"] == 35


def test_alert_limit():
    """测试警报数量限制（最多50条）"""
    with tempfile.TemporaryDirectory() as tmpdir:
        health_check = HealthCheckSystem(base_path=tmpdir)

        # 添加超过限制的警报
        for i in range(60):
            health_check.add_alert(
                level="info",
                component="test",
                message=f"测试警报 {i}"
            )

        # 获取状态并验证警报数量
        status = health_check.get_status()
        assert len(status.alerts) == 50  # 应该只保留最近的50条

        # 验证最早的警报被移除（最新的在前面）
        # 第一个警报应该是最后添加的（59）
        first_alert = status.alerts[0]
        assert "测试警报 59" in first_alert["message"]

        # 最后一个警报应该是第10个添加的（因为只保留50条，前10条被移除）
        last_alert = status.alerts[-1]
        assert "测试警报 10" in last_alert["message"]


def test_perform_system_check():
    """测试执行系统健康检查"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建必要的目录
        os.makedirs(os.path.join(tmpdir, "tasks"), exist_ok=True)
        os.makedirs(os.path.join(tmpdir, "results"), exist_ok=True)

        health_check = HealthCheckSystem(base_path=tmpdir)

        # 模拟磁盘空间检查
        with patch('shutil.disk_usage') as mock_disk_usage:
            # 模拟足够的磁盘空间
            mock_disk_usage.return_value = MagicMock(free=100 * 1024 * 1024 * 1024, total=200 * 1024 * 1024 * 1024)

            status = health_check.perform_system_check()

            # 验证系统状态
            assert status.system_status == "healthy"

            # 验证系统检查组件
            assert "system_check" in status.components
            assert status.components["system_check"]["status"] == "healthy"
            assert "disk_free_gb" in status.components["system_check"]
            assert "disk_total_gb" in status.components["system_check"]
            assert "disk_usage_percent" in status.components["system_check"]


def test_perform_system_check_low_disk_space():
    """测试磁盘空间不足的系统检查"""
    with tempfile.TemporaryDirectory() as tmpdir:
        health_check = HealthCheckSystem(base_path=tmpdir)

        # 模拟磁盘空间不足
        with patch('shutil.disk_usage') as mock_disk_usage:
            # 模拟磁盘空间不足（小于5%）
            mock_disk_usage.return_value = MagicMock(free=1 * 1024 * 1024 * 1024, total=100 * 1024 * 1024 * 1024)

            status = health_check.perform_system_check()

            # 验证系统状态
            assert status.system_status == "warning" or status.system_status == "critical"

            # 验证有警报
            assert len(status.alerts) > 0
            alert_messages = [alert["message"] for alert in status.alerts]
            assert any("磁盘空间" in msg for msg in alert_messages)


def test_perform_system_check_missing_task_dir():
    """测试任务目录不存在的系统检查"""
    with tempfile.TemporaryDirectory() as tmpdir:
        health_check = HealthCheckSystem(base_path=tmpdir)

        # 删除results目录以模拟缺失
        results_dir = os.path.join(tmpdir, "results")
        if os.path.exists(results_dir):
            import shutil
            shutil.rmtree(results_dir)

        status = health_check.perform_system_check()

        # 验证有关于目录的警报
        assert len(status.alerts) > 0
        alert_messages = [alert["message"] for alert in status.alerts]
        assert any("目录不存在" in msg for msg in alert_messages)


def test_recalculate_system_status_logic():
    """测试系统状态重新计算逻辑"""
    with tempfile.TemporaryDirectory() as tmpdir:
        health_check = HealthCheckSystem(base_path=tmpdir)

        # 测试1: 所有组件正常
        status1 = HealthStatus.create_initial_status()
        health_check._recalculate_system_status(status1)
        assert status1.system_status == "healthy"

        # 测试2: 有warning组件
        status2 = HealthStatus.create_initial_status()
        status2.components["data_service"]["status"] = "warning"
        health_check._recalculate_system_status(status2)
        assert status2.system_status == "warning"

        # 测试3: 有critical组件
        status3 = HealthStatus.create_initial_status()
        status3.components["task_queue"]["status"] = "critical"
        health_check._recalculate_system_status(status3)
        assert status3.system_status == "critical"

        # 测试4: 既有warning又有critical，应该取最严重的
        status4 = HealthStatus.create_initial_status()
        status4.components["data_service"]["status"] = "warning"
        status4.components["task_queue"]["status"] = "critical"
        health_check._recalculate_system_status(status4)
        assert status4.system_status == "critical"


def test_save_and_load_status():
    """测试保存和加载健康状态"""
    with tempfile.TemporaryDirectory() as tmpdir:
        health_check = HealthCheckSystem(base_path=tmpdir)

        # 创建自定义状态
        custom_status = HealthStatus(
            system_status="warning",
            last_check=datetime.now(),
            components={
                "test_component": {
                    "status": "running",
                    "custom_metric": 42
                }
            },
            alerts=[
                {
                    "level": "info",
                    "component": "test",
                    "message": "测试消息",
                    "timestamp": datetime.now().isoformat(),
                    "details": {"test": True}
                }
            ]
        )

        # 保存状态
        health_check._save_status(custom_status)

        # 验证文件存在
        health_file = os.path.join(tmpdir, "results", "dashboard_health.json")
        assert os.path.exists(health_file)

        # 重新加载并验证
        loaded_status = health_check.get_status()
        assert loaded_status.system_status == "warning"
        assert "test_component" in loaded_status.components
        assert loaded_status.components["test_component"]["custom_metric"] == 42
        assert len(loaded_status.alerts) == 1
        assert loaded_status.alerts[0]["message"] == "测试消息"


def test_health_check_integration_with_dashboard_processor():
    """测试健康检查与仪表盘处理器的集成"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建健康检查系统
        health_check = HealthCheckSystem(base_path=tmpdir)

        # 模拟任务处理失败
        try:
            raise ValueError("模拟任务处理失败")
        except Exception as e:
            health_check.add_alert(
                level="error",
                component="dashboard_processor",
                message=f"任务处理失败: {str(e)}",
                details={"exception_type": type(e).__name__}
            )

        # 验证警报已添加
        status = health_check.get_status()
        assert len(status.alerts) > 0
        assert any("任务处理失败" in alert["message"] for alert in status.alerts)


def test_component_metrics_persistence():
    """测试组件指标的持久化"""
    with tempfile.TemporaryDirectory() as tmpdir:
        health_check = HealthCheckSystem(base_path=tmpdir)

        # 更新组件状态并添加指标
        health_check.update_component_status(
            component_name="dashboard",
            status="running",
            uptime_hours=720,
            active_sessions=15,
            memory_usage_mb=256.5
        )

        # 保存并重新加载
        status1 = health_check.get_status()
        health_check._save_status(status1)

        # 创建新的健康检查实例（模拟重启）
        health_check2 = HealthCheckSystem(base_path=tmpdir)
        status2 = health_check2.get_status()

        # 验证指标持久化
        assert "dashboard" in status2.components
        dashboard_metrics = status2.components["dashboard"]
        assert dashboard_metrics["status"] == "running"
        assert dashboard_metrics["uptime_hours"] == 720
        assert dashboard_metrics["active_sessions"] == 15
        assert dashboard_metrics["memory_usage_mb"] == 256.5


if __name__ == "__main__":
    # 运行测试
    test_health_check_system_initialization()
    print("✓ test_health_check_system_initialization passed")

    test_get_status_initial()
    print("✓ test_get_status_initial passed")

    test_update_component_status()
    print("✓ test_update_component_status passed")

    test_add_alert()
    print("✓ test_add_alert passed")

    test_perform_system_check()
    print("✓ test_perform_system_check passed")

    print("\n所有测试通过！")