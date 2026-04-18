"""测试仪表盘数据模型"""

def test_task_model_creation():
    """测试任务模型创建"""
    from src.dashboard.models import DashboardTask

    # 测试数据筛选任务创建
    task = DashboardTask.create_data_filter_task(
        task_id="test_001",
        stock_symbols=["AAPL", "MSFT"],
        time_range={"start": "2026-01-01", "end": "2026-04-18"},
        filter_conditions={
            "markets": ["US"],
            "industries": ["Technology"],
            "market_cap_min": 100,
            "market_cap_max": 1000
        }
    )

    assert task.task_id == "test_001"
    assert task.task_type == "data_filter"
    assert task.status == "pending"
    assert task.priority == "normal"
    assert "stock_symbols" in task.user_config
    assert len(task.user_config["stock_symbols"]) == 2


def test_task_model_to_dict():
    """测试任务模型转字典"""
    from src.dashboard.models import DashboardTask

    task = DashboardTask.create_data_filter_task(
        task_id="test_002",
        stock_symbols=["GOOGL"],
        time_range={"start": "2026-01-01", "end": "2026-04-18"},
        filter_conditions={"markets": ["US"]}
    )

    task_dict = task.to_dict()
    assert task_dict["task_id"] == "test_002"
    assert task_dict["task_type"] == "data_filter"
    assert task_dict["status"] == "pending"
    assert "timestamp" in task_dict


def test_task_model_from_dict():
    """测试从字典创建任务模型"""
    from src.dashboard.models import DashboardTask

    task_dict = {
        "task_id": "test_003",
        "task_type": "strategy_backtest",
        "status": "completed",
        "user_config": {
            "strategy_name": "moving_average",
            "parameters": {"period": 20}
        },
        "priority": "high",
        "timestamp": "2026-04-18T10:30:00"
    }

    task = DashboardTask.from_dict(task_dict)
    assert task.task_id == "test_003"
    assert task.task_type == "strategy_backtest"
    assert task.status == "completed"
    assert task.user_config["strategy_name"] == "moving_average"


def test_task_status_model():
    """测试任务状态模型"""
    from src.dashboard.models import TaskStatus

    status = TaskStatus.create_pending_status("test_004")
    assert status.task_id == "test_004"
    assert status.current_status == "pending"
    assert status.progress_percent == 0
    assert status.current_step == "initialized"


def test_health_status_model():
    """测试健康状态模型"""
    from src.dashboard.models import HealthStatus

    health = HealthStatus.create_initial_status()
    assert health.system_status == "healthy"
    assert len(health.components) > 0
    assert "dashboard" in health.components