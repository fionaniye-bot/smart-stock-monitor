"""仪表盘数据模型定义

统一的数据模型类，确保与规格文档一致。
规格文档使用 'task_type' 字段，而实施计划使用 'type' 字段。
统一使用规格文档格式。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import uuid


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
    estimated_compute_time: Optional[timedelta] = None
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
            "estimated_compute_time": (
                str(self.estimated_compute_time)
                if self.estimated_compute_time
                else None
            ),
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
        # 处理时间戳
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif timestamp is None:
            timestamp = datetime.now()

        # 处理计算时间
        compute_time = data.get("estimated_compute_time")
        if isinstance(compute_time, str):
            # 简单解析 timedelta 字符串，如 "1:30:00"
            parts = compute_time.split(":")
            if len(parts) == 3:
                hours, minutes, seconds = map(int, parts)
                compute_time = timedelta(hours=hours, minutes=minutes, seconds=seconds)
            else:
                compute_time = None

        return cls(
            task_id=data["task_id"],
            timestamp=timestamp,
            task_type=data.get("task_type", "data_filter"),
            status=data.get("status", "pending"),
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
    progress_percent: float = 0.0
    current_step: str = "initialized"
    estimated_remaining_time: Optional[timedelta] = None
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
            progress_percent=0.0,
            current_step="initialized"
        )

    def to_dict(self) -> Dict[str, Any]:
        """将状态转换为字典

        Returns:
            包含状态数据的字典
        """
        return {
            "task_id": self.task_id,
            "current_status": self.current_status,
            "progress_percent": self.progress_percent,
            "current_step": self.current_step,
            "estimated_remaining_time": (
                str(self.estimated_remaining_time)
                if self.estimated_remaining_time
                else None
            ),
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