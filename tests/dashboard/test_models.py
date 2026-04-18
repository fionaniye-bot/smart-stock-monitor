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


def test_indicator_adjust_task_creation():
    """测试技术指标调整任务创建"""
    from src.dashboard.models import DashboardTask

    # 测试技术指标调整任务创建
    task = DashboardTask.create_indicator_adjust_task(
        task_id="test_indicator_001",
        stock_symbols=["AAPL", "GOOGL"],
        time_range={"start": "2026-01-01", "end": "2026-04-18"},
        indicator_params={
            "ma_periods": [5, 10, 20],
            "rsi_period": 14,
            "macd_fast": 12,
            "macd_slow": 26,
            "macd_signal": 9
        }
    )

    assert task.task_id == "test_indicator_001"
    assert task.task_type == "indicator_adjust"
    assert task.status == "pending"
    assert "stock_symbols" in task.user_config
    assert "indicator_params" in task.user_config
    assert task.user_config["indicator_params"]["ma_periods"] == [5, 10, 20]


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


def test_field_type_validation():
    """测试字段类型验证"""
    from src.dashboard.models import DashboardTask, TaskStatus, validate_task_type, validate_task_status

    # 测试任务类型验证
    assert validate_task_type("data_filter") == True
    assert validate_task_type("strategy_backtest") == True
    assert validate_task_type("indicator_adjust") == True
    assert validate_task_type("invalid_type") == False

    # 测试任务状态验证
    assert validate_task_status("pending") == True
    assert validate_task_status("processing") == True
    assert validate_task_status("completed") == True
    assert validate_task_status("failed") == True
    assert validate_task_status("cancelled") == True
    assert validate_task_status("invalid_status") == False

    # 测试DashboardTask字段类型
    task = DashboardTask(
        task_id="test_field_types",
        timestamp="2026-04-18T10:30:00",
        task_type="data_filter",
        status="pending",
        user_config={},
        priority="normal",
        estimated_compute_time=30,  # 应该是整数秒
        metadata={}
    )

    # 验证estimated_compute_time是整数
    assert isinstance(task.estimated_compute_time, int) or task.estimated_compute_time is None

    # 测试TaskStatus字段类型
    status = TaskStatus(
        task_id="test_field_types",
        current_status="processing",
        progress_percent=50,  # 应该是整数
        current_step="processing",
        estimated_remaining_time=60,  # 应该是整数秒
        start_time="2026-04-18T10:30:00",
        last_update="2026-04-18T10:30:30",
        error_message=None,
        result_path=None
    )

    # 验证progress_percent是整数
    assert isinstance(status.progress_percent, int)
    # 验证estimated_remaining_time是整数或None
    assert isinstance(status.estimated_remaining_time, int) or status.estimated_remaining_time is None


def test_from_dict_validation():
    """测试from_dict方法的验证功能"""
    from src.dashboard.models import DashboardTask, TaskStatus

    # 测试DashboardTask验证
    # 无效任务类型
    try:
        DashboardTask.from_dict({
            "task_id": "test_001",
            "task_type": "invalid_type",
            "status": "pending"
        })
        assert False, "应该抛出ValueError"
    except ValueError as e:
        assert "无效的任务类型" in str(e)

    # 无效任务状态
    try:
        DashboardTask.from_dict({
            "task_id": "test_002",
            "task_type": "data_filter",
            "status": "invalid_status"
        })
        assert False, "应该抛出ValueError"
    except ValueError as e:
        assert "无效的任务状态" in str(e)

    # 测试TaskStatus验证
    # 无效任务状态
    try:
        TaskStatus.from_dict({
            "task_id": "test_003",
            "current_status": "invalid_status",
            "progress_percent": 0
        })
        assert False, "应该抛出ValueError"
    except ValueError as e:
        assert "无效的任务状态" in str(e)

    # 无效进度百分比
    try:
        TaskStatus.from_dict({
            "task_id": "test_004",
            "current_status": "pending",
            "progress_percent": "not_a_number"
        })
        assert False, "应该抛出ValueError"
    except ValueError as e:
        assert "进度百分比必须是数字" in str(e)


def test_to_dict_conversion():
    """测试to_dict方法的转换功能"""
    from src.dashboard.models import DashboardTask, TaskStatus
    from datetime import datetime

    # 测试DashboardTask转换
    task = DashboardTask(
        task_id="test_conversion",
        timestamp=datetime.now(),
        task_type="data_filter",
        status="processing",
        user_config={"test": "data"},
        priority="high",
        estimated_compute_time=45,
        metadata={"source": "test"}
    )

    task_dict = task.to_dict()

    # 验证timestamp被转换为ISO字符串
    assert isinstance(task_dict["timestamp"], str)
    # 验证estimated_compute_time是整数
    assert isinstance(task_dict["estimated_compute_time"], int)
    assert task_dict["estimated_compute_time"] == 45

    # 测试TaskStatus转换
    status = TaskStatus(
        task_id="test_conversion",
        current_status="processing",
        progress_percent=75,
        current_step="calculating",
        estimated_remaining_time=120,
        start_time=datetime.now(),
        last_update=datetime.now()
    )

    status_dict = status.to_dict()

    # 验证时间字段被转换为ISO字符串
    assert isinstance(status_dict["start_time"], str)
    assert isinstance(status_dict["last_update"], str)
    # 验证progress_percent是整数
    assert isinstance(status_dict["progress_percent"], int)
    assert status_dict["progress_percent"] == 75
    # 验证estimated_remaining_time是整数
    assert isinstance(status_dict["estimated_remaining_time"], int)
    assert status_dict["estimated_remaining_time"] == 120