"""仪表盘插件模块

提供统一的数据模型和接口，用于智能盯盘系统的仪表盘功能。
"""

from .models import DashboardTask, TaskStatus, HealthStatus

__all__ = [
    "DashboardTask",
    "TaskStatus",
    "HealthStatus"
]