"""仪表盘数据模型定义

统一的数据模型类，确保与规格文档一致。
规格文档使用 'task_type' 字段，而实施计划使用 'type' 字段。
统一使用规格文档格式。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import uuid


# 任务类型常量
VALID_TASK_TYPES = {"data_filter", "strategy_backtest", "indicator_adjust"}
VALID_TASK_STATUSES = {"pending", "processing", "completed", "failed", "cancelled"}


def validate_task_type(task_type: str) -> bool:
    """验证任务类型是否有效"""
    return task_type in VALID_TASK_TYPES


def validate_task_status(status: str) -> bool:
    """验证任务状态是否有效"""
    return status in VALID_TASK_STATUSES


@dataclass
class DashboardTask:
    """仪表盘任务数据模型

    统一使用 'task_type' 字段（与规格文档一致）
    """

    task_id: str
    timestamp: datetime = field(default_factory=datetime.now)
    task_type: str = "data_filter"  # 统一使用 task_type 而不是 type
    status: str = "pending"
    user_config: Dict[str, Any] = field(default_factory=dict)
    priority: str = "normal"
    estimated_compute_time: Optional[int] = None  # 秒，与规格文档一致
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create_data_filter_task(
        cls,
        task_id: str,
        stock_symbols: List[str],
        time_range: Dict[str, str],
        filter_conditions: Dict[str, Any],
        priority: str = "normal"
    ) -> "DashboardTask":
        """创建数据筛选任务

        Args:
            task_id: 任务ID
            stock_symbols: 股票代码列表
            time_range: 时间范围 {start: "YYYY-MM-DD", end: "YYYY-MM-DD"}
            filter_conditions: 筛选条件
            priority: 优先级 (low, normal, high)

        Returns:
            DashboardTask实例
        """
        user_config = {
            "stock_symbols": stock_symbols,
            "time_range": time_range,
            "filter_conditions": filter_conditions
        }

        return cls(
            task_id=task_id,
            task_type="data_filter",
            user_config=user_config,
            priority=priority,
            metadata={
                "created_by": "dashboard",
                "task_category": "data_processing"
            }
        )

    @classmethod
    def create_strategy_backtest_task(
        cls,
        task_id: str,
        strategy_name: str,
        parameters: Dict[str, Any],
        stock_symbols: List[str],
        time_range: Dict[str, str],
        priority: str = "normal"
    ) -> "DashboardTask":
        """创建策略回测任务

        Args:
            task_id: 任务ID
            strategy_name: 策略名称
            parameters: 策略参数
            stock_symbols: 股票代码列表
            time_range: 时间范围
            priority: 优先级

        Returns:
            DashboardTask实例
        """
        user_config = {
            "strategy_name": strategy_name,
            "parameters": parameters,
            "stock_symbols": stock_symbols,
            "time_range": time_range
        }

        return cls(
            task_id=task_id,
            task_type="strategy_backtest",
            user_config=user_config,
            priority=priority,
            metadata={
                "created_by": "dashboard",
                "task_category": "strategy_analysis"
            }
        )

    @classmethod
    def create_indicator_adjust_task(
        cls,
        task_id: str,
        stock_symbols: List[str],
        time_range: Dict[str, str],
        indicator_params: Dict[str, Any],
        priority: str = "normal"
    ) -> "DashboardTask":
        """创建技术指标调整任务

        Args:
            task_id: 任务ID
            stock_symbols: 股票代码列表
            time_range: 时间范围 {start: "YYYY-MM-DD", end: "YYYY-MM-DD"}
            indicator_params: 指标参数配置
            priority: 优先级 (low, normal, high)

        Returns:
            DashboardTask实例
        """
        user_config = {
            "stock_symbols": stock_symbols,
            "time_range": time_range,
            "indicator_params": indicator_params
        }

        return cls(
            task_id=task_id,
            task_type="indicator_adjust",
            user_config=user_config,
            priority=priority,
            metadata={
                "created_by": "dashboard",
                "task_category": "technical_analysis"
            }
        )

    def to_dict(self) -> Dict[str, Any]:
        """将任务转换为字典

        Returns:
            包含任务数据的字典
        """
        return {
            "task_id": self.task_id,
            "timestamp": self.timestamp.isoformat(),
            "task_type": self.task_type,
            "status": self.status,
            "user_config": self.user_config,
            "priority": self.priority,
            "estimated_compute_time": self.estimated_compute_time,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DashboardTask":
        """从字典创建任务

        Args:
            data: 包含任务数据的字典

        Returns:
            DashboardTask实例
        """
        # 验证必需字段
        if "task_id" not in data:
            raise ValueError("任务数据缺少必需的 'task_id' 字段")

        # 验证任务类型
        task_type = data.get("task_type", "data_filter")
        if not validate_task_type(task_type):
            raise ValueError(f"无效的任务类型: {task_type}")

        # 验证任务状态
        status = data.get("status", "pending")
        if not validate_task_status(status):
            raise ValueError(f"无效的任务状态: {status}")

        # 处理时间戳
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp)
            except ValueError:
                raise ValueError(f"无效的时间戳格式: {timestamp}")
        elif timestamp is None:
            timestamp = datetime.now()
        elif isinstance(timestamp, datetime):
            # 已经是datetime对象，直接使用
            pass
        else:
            raise ValueError(f"时间戳必须是字符串或datetime对象，实际类型: {type(timestamp)}")

        # 处理计算时间（规格要求为整数秒）
        compute_time = data.get("estimated_compute_time")
        if compute_time is not None:
            if isinstance(compute_time, (int, float)):
                compute_time = int(compute_time)
            elif isinstance(compute_time, str):
                try:
                    # 尝试解析字符串为整数
                    compute_time = int(compute_time)
                except ValueError:
                    # 如果是timedelta字符串，转换为秒数
                    try:
                        parts = compute_time.split(":")
                        if len(parts) == 3:
                            hours, minutes, seconds = map(int, parts)
                            compute_time = hours * 3600 + minutes * 60 + seconds
                        else:
                            compute_time = None
                    except (ValueError, AttributeError):
                        compute_time = None
            else:
                compute_time = None

        return cls(
            task_id=data["task_id"],
            timestamp=timestamp,
            task_type=task_type,
            status=status,
            user_config=data.get("user_config", {}),
            priority=data.get("priority", "normal"),
            estimated_compute_time=compute_time,
            metadata=data.get("metadata", {})
        )


@dataclass
class TaskStatus:
    """任务状态数据模型"""

    task_id: str
    current_status: str = "pending"
    progress_percent: int = 0  # 规格要求为整数
    current_step: str = "initialized"
    estimated_remaining_time: Optional[int] = None  # 秒，与规格文档一致
    start_time: datetime = field(default_factory=datetime.now)
    last_update: datetime = field(default_factory=datetime.now)
    error_message: Optional[str] = None
    result_path: Optional[str] = None

    @classmethod
    def create_pending_status(cls, task_id: str) -> "TaskStatus":
        """创建待处理状态

        Args:
            task_id: 任务ID

        Returns:
            TaskStatus实例
        """
        return cls(
            task_id=task_id,
            current_status="pending",
            progress_percent=0,
            current_step="initialized"
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskStatus":
        """从字典创建状态

        Args:
            data: 包含状态数据的字典

        Returns:
            TaskStatus实例
        """
        # 验证必需字段
        if "task_id" not in data:
            raise ValueError("状态数据缺少必需的 'task_id' 字段")

        # 验证任务状态
        current_status = data.get("current_status", "pending")
        if not validate_task_status(current_status):
            raise ValueError(f"无效的任务状态: {current_status}")

        # 处理进度百分比
        progress_percent = data.get("progress_percent", 0)
        if isinstance(progress_percent, (int, float)):
            progress_percent = int(progress_percent)
            # 确保在0-100范围内
            progress_percent = max(0, min(100, progress_percent))
        else:
            raise ValueError(f"进度百分比必须是数字，实际类型: {type(progress_percent)}")

        # 处理剩余时间
        estimated_remaining_time = data.get("estimated_remaining_time")
        if estimated_remaining_time is not None:
            if isinstance(estimated_remaining_time, (int, float)):
                estimated_remaining_time = int(estimated_remaining_time)
            elif isinstance(estimated_remaining_time, str):
                try:
                    estimated_remaining_time = int(estimated_remaining_time)
                except ValueError:
                    # 如果是timedelta字符串，转换为秒数
                    try:
                        parts = estimated_remaining_time.split(":")
                        if len(parts) == 3:
                            hours, minutes, seconds = map(int, parts)
                            estimated_remaining_time = hours * 3600 + minutes * 60 + seconds
                        else:
                            estimated_remaining_time = None
                    except (ValueError, AttributeError):
                        estimated_remaining_time = None
            else:
                estimated_remaining_time = None

        # 处理时间字段
        start_time = data.get("start_time")
        if isinstance(start_time, str):
            try:
                start_time = datetime.fromisoformat(start_time)
            except ValueError:
                raise ValueError(f"无效的开始时间格式: {start_time}")
        elif start_time is None:
            start_time = datetime.now()
        elif isinstance(start_time, datetime):
            # 已经是datetime对象，直接使用
            pass
        else:
            raise ValueError(f"开始时间必须是字符串或datetime对象，实际类型: {type(start_time)}")

        last_update = data.get("last_update")
        if isinstance(last_update, str):
            try:
                last_update = datetime.fromisoformat(last_update)
            except ValueError:
                raise ValueError(f"无效的最后更新时间格式: {last_update}")
        elif last_update is None:
            last_update = datetime.now()
        elif isinstance(last_update, datetime):
            # 已经是datetime对象，直接使用
            pass
        else:
            raise ValueError(f"最后更新时间必须是字符串或datetime对象，实际类型: {type(last_update)}")

        return cls(
            task_id=data["task_id"],
            current_status=current_status,
            progress_percent=progress_percent,
            current_step=data.get("current_step", "initialized"),
            estimated_remaining_time=estimated_remaining_time,
            start_time=start_time,
            last_update=last_update,
            error_message=data.get("error_message"),
            result_path=data.get("result_path")
        )

    def to_dict(self) -> Dict[str, Any]:
        """将状态转换为字典

        Returns:
            包含状态数据的字典
        """
        # 验证状态值
        if not validate_task_status(self.current_status):
            raise ValueError(f"无效的任务状态: {self.current_status}")

        # 确保进度百分比在0-100范围内
        progress = max(0, min(100, self.progress_percent))

        return {
            "task_id": self.task_id,
            "current_status": self.current_status,
            "progress_percent": progress,
            "current_step": self.current_step,
            "estimated_remaining_time": self.estimated_remaining_time,
            "start_time": self.start_time.isoformat(),
            "last_update": self.last_update.isoformat(),
            "error_message": self.error_message,
            "result_path": self.result_path
        }


@dataclass
class HealthStatus:
    """系统健康状态数据模型"""

    system_status: str = "healthy"
    last_check: datetime = field(default_factory=datetime.now)
    components: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    alerts: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def create_initial_status(cls) -> "HealthStatus":
        """创建初始健康状态

        Returns:
            HealthStatus实例
        """
        return cls(
            system_status="healthy",
            components={
                "dashboard": {
                    "status": "running",
                    "last_heartbeat": datetime.now().isoformat()
                },
                "data_service": {
                    "status": "running",
                    "last_update": datetime.now().isoformat()
                },
                "task_queue": {
                    "status": "idle",
                    "pending_tasks": 0
                }
            },
            alerts=[]
        )

    def to_dict(self) -> Dict[str, Any]:
        """将健康状态转换为字典

        Returns:
            包含健康状态数据的字典
        """
        return {
            "system_status": self.system_status,
            "last_check": self.last_check.isoformat(),
            "components": self.components,
            "alerts": self.alerts
        }