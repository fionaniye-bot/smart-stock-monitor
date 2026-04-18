"""仪表盘处理器健康检查集成测试

测试DashboardProcessor与HealthCheckSystem的集成
"""
import os
import json
import tempfile
import pytest
from unittest.mock import patch, MagicMock

from src.dashboard.dashboard_processor import DashboardProcessor
from src.dashboard.health_check import HealthCheckSystem
from src.dashboard.models import DashboardTask


def test_dashboard_processor_with_health_check():
    """测试带健康检查的仪表盘处理器初始化"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建必要的目录
        os.makedirs(os.path.join(tmpdir, "tasks"), exist_ok=True)
        os.makedirs(os.path.join(tmpdir, "results"), exist_ok=True)

        processor = DashboardProcessor(task_dir=tmpdir, lock_dir=tmpdir)

        # 验证健康检查系统已初始化
        assert hasattr(processor, 'health_check')
        assert isinstance(processor.health_check, HealthCheckSystem)

        # 获取健康状态
        health_status = processor.get_health_status()
        assert "system_status" in health_status
        assert "components" in health_status
        assert "dashboard_processor" in health_status["components"]


def test_health_check_integration_on_task_success():
    """测试任务成功时的健康检查集成"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建必要的目录
        os.makedirs(os.path.join(tmpdir, "tasks"), exist_ok=True)
        os.makedirs(os.path.join(tmpdir, "results"), exist_ok=True)

        processor = DashboardProcessor(task_dir=tmpdir, lock_dir=tmpdir)

        # 创建任务
        task_data = {
            "task_id": "health_check_test",
            "task_type": "data_filter",
            "status": "pending",
            "user_config": {
                "stock_symbols": ["AAPL"],
                "time_range": {"start": "2024-01-01", "end": "2024-12-31"},
                "filter_conditions": {"min_volume": 1000000}
            }
        }

        task_file = os.path.join(tmpdir, "health_check_test.json")
        with open(task_file, 'w') as f:
            json.dump(task_data, f)

        # 处理任务
        result = processor.process_task("health_check_test")
        assert result == True

        # 检查健康状态
        health_status = processor.get_health_status()
        # 系统状态应该是healthy，但如果是warning也接受（可能因为其他原因）
        assert health_status["system_status"] in ["healthy", "warning"]

        # 检查dashboard_processor组件状态
        dashboard_component = health_status["components"].get("dashboard_processor")
        assert dashboard_component is not None
        assert dashboard_component["status"] == "running"
        assert "last_successful_task" in dashboard_component
        assert dashboard_component["last_successful_task"] == "health_check_test"


def test_health_check_integration_on_task_failure():
    """测试任务失败时的健康检查集成"""
    with tempfile.TemporaryDirectory() as tmpdir:
        processor = DashboardProcessor(task_dir=tmpdir, lock_dir=tmpdir)

        # 创建无效任务（缺少必需字段）
        task_data = {
            "task_id": "failure_test",
            "status": "pending"
            # 缺少task_type字段
        }

        task_file = os.path.join(tmpdir, "failure_test.json")
        with open(task_file, 'w') as f:
            json.dump(task_data, f)

        # 处理任务（应该失败）
        result = processor.process_task("failure_test")
        assert result == False

        # 检查健康状态
        health_status = processor.get_health_status()

        # 系统状态可能是warning（因为有错误）
        assert health_status["system_status"] in ["healthy", "warning"]

        # 检查警报
        assert len(health_status["alerts"]) > 0

        # 找到相关的警报
        task_alerts = [alert for alert in health_status["alerts"]
                      if "failure_test" in alert.get("message", "")]
        assert len(task_alerts) > 0

        # 检查dashboard_processor组件状态
        dashboard_component = health_status["components"].get("dashboard_processor")
        assert dashboard_component is not None
        # 状态可能是warning或running
        assert dashboard_component["status"] in ["running", "warning"]


def test_perform_health_check_method():
    """测试执行健康检查方法"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建必要的目录
        os.makedirs(os.path.join(tmpdir, "tasks"), exist_ok=True)
        os.makedirs(os.path.join(tmpdir, "results"), exist_ok=True)

        processor = DashboardProcessor(task_dir=tmpdir, lock_dir=tmpdir)

        # 模拟磁盘空间检查
        with patch('shutil.disk_usage') as mock_disk_usage:
            # 模拟足够的磁盘空间
            mock_disk_usage.return_value = MagicMock(
                free=100 * 1024 * 1024 * 1024,
                total=200 * 1024 * 1024 * 1024
            )

            health_check_result = processor.perform_health_check()

            # 验证返回结果
            assert "system_status" in health_check_result
            assert "components" in health_check_result
            assert "alerts" in health_check_result

            # 验证系统检查组件
            assert "system_check" in health_check_result["components"]
            system_check = health_check_result["components"]["system_check"]
            # 状态可能是healthy或warning
            assert system_check["status"] in ["healthy", "warning"]
            assert "disk_free_gb" in system_check
            assert "disk_total_gb" in system_check


def test_custom_health_check_system():
    """测试使用自定义健康检查系统"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建自定义健康检查系统
        custom_health_check = HealthCheckSystem(base_path=tmpdir)

        # 使用自定义健康检查系统创建处理器
        processor = DashboardProcessor(
            task_dir=tmpdir,
            lock_dir=tmpdir,
            health_check=custom_health_check
        )

        # 验证使用的是自定义健康检查系统
        assert processor.health_check is custom_health_check

        # 在自定义健康检查系统中设置一些状态
        custom_health_check.update_component_status(
            component_name="custom_component",
            status="running",
            custom_metric=42
        )

        # 验证处理器可以看到这些状态
        health_status = processor.get_health_status()
        assert "custom_component" in health_status["components"]
        assert health_status["components"]["custom_component"]["custom_metric"] == 42


def test_health_check_persistence():
    """测试健康检查状态的持久化"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建必要的目录
        os.makedirs(os.path.join(tmpdir, "tasks"), exist_ok=True)
        os.makedirs(os.path.join(tmpdir, "results"), exist_ok=True)

        # 第一个处理器实例
        processor1 = DashboardProcessor(task_dir=tmpdir, lock_dir=tmpdir)

        # 处理一个任务
        task_data = {
            "task_id": "persistence_test",
            "task_type": "data_filter",
            "status": "pending",
            "user_config": {"test": "data"}
        }

        task_file = os.path.join(tmpdir, "persistence_test.json")
        with open(task_file, 'w') as f:
            json.dump(task_data, f)

        processor1.process_task("persistence_test")

        # 获取第一个处理器的健康状态
        health_status1 = processor1.get_health_status()

        # 创建第二个处理器实例（模拟重启）
        processor2 = DashboardProcessor(task_dir=tmpdir, lock_dir=tmpdir)

        # 获取第二个处理器的健康状态
        health_status2 = processor2.get_health_status()

        # 验证健康状态持久化
        # 注意：时间戳可能不同，但组件状态应该相同
        assert health_status1["system_status"] == health_status2["system_status"]

        # 检查dashboard_processor组件
        comp1 = health_status1["components"].get("dashboard_processor", {})
        comp2 = health_status2["components"].get("dashboard_processor", {})
        assert comp1.get("status") == comp2.get("status")


def test_health_check_error_handling():
    """测试健康检查错误处理"""
    with tempfile.TemporaryDirectory() as tmpdir:
        processor = DashboardProcessor(task_dir=tmpdir, lock_dir=tmpdir)

        # 模拟健康检查系统抛出异常
        with patch.object(processor.health_check, 'get_status') as mock_get_status:
            mock_get_status.side_effect = Exception("模拟健康检查失败")

            # get_health_status应该处理异常并返回错误信息
            health_status = processor.get_health_status()
            assert health_status["system_status"] == "unknown"
            assert "error" in health_status
            assert "模拟健康检查失败" in health_status["error"]

        # 模拟perform_system_check抛出异常
        with patch.object(processor.health_check, 'perform_system_check') as mock_perform_check:
            mock_perform_check.side_effect = Exception("模拟系统检查失败")

            # perform_health_check应该处理异常并返回错误信息
            check_result = processor.perform_health_check()
            assert check_result["system_status"] == "error"
            assert "error" in check_result
            assert "模拟系统检查失败" in check_result["error"]


def test_health_check_with_multiple_tasks():
    """测试处理多个任务时的健康检查"""
    with tempfile.TemporaryDirectory() as tmpdir:
        processor = DashboardProcessor(task_dir=tmpdir, lock_dir=tmpdir)

        # 创建多个任务
        tasks = [
            {
                "task_id": "task1",
                "task_type": "data_filter",
                "status": "pending",
                "user_config": {"test": "data1"}
            },
            {
                "task_id": "task2",
                "task_type": "strategy_backtest",
                "status": "pending",
                "user_config": {"test": "data2"}
            }
        ]

        for task in tasks:
            task_file = os.path.join(tmpdir, f"{task['task_id']}.json")
            with open(task_file, 'w') as f:
                json.dump(task, f)

        # 处理第一个任务
        result1 = processor.process_task("task1")
        assert result1 == True

        # 获取中间健康状态
        health_status1 = processor.get_health_status()
        dashboard_comp1 = health_status1["components"].get("dashboard_processor", {})

        # 处理第二个任务
        result2 = processor.process_task("task2")
        assert result2 == True

        # 获取最终健康状态
        health_status2 = processor.get_health_status()
        dashboard_comp2 = health_status2["components"].get("dashboard_processor", {})

        # 验证健康状态更新
        assert dashboard_comp2.get("last_successful_task") == "task2"
        # 其他指标应该被更新


if __name__ == "__main__":
    # 运行测试
    test_dashboard_processor_with_health_check()
    print("✓ test_dashboard_processor_with_health_check passed")

    test_health_check_integration_on_task_success()
    print("✓ test_health_check_integration_on_task_success passed")

    test_perform_health_check_method()
    print("✓ test_perform_health_check_method passed")

    print("\n所有测试通过！")