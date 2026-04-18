"""健康检查系统

实现完整的健康检查系统，包括健康状态管理、警报系统和系统检查。
与仪表盘处理器集成，提供增强的错误处理。
"""
import os
import json
import logging
import shutil
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import asdict

from .models import HealthStatus


class HealthCheckSystem:
    """健康检查系统

    管理系统的健康状态，包括组件状态、警报和系统检查。
    提供与仪表盘处理器的集成，增强错误处理能力。
    """

    def __init__(self, base_path: str):
        """
        初始化健康检查系统

        Args:
            base_path: 基础目录路径，健康文件将保存在 base_path/results/dashboard_health.json
        """
        self.base_path = base_path
        self.health_file = os.path.join(base_path, "results", "dashboard_health.json")
        self.logger = logging.getLogger(__name__)

        # 确保目录存在
        os.makedirs(os.path.dirname(self.health_file), exist_ok=True)

    def get_status(self) -> HealthStatus:
        """
        获取当前健康状态

        从文件加载健康状态，如果文件不存在或损坏，返回初始状态。

        Returns:
            HealthStatus: 当前健康状态
        """
        try:
            if os.path.exists(self.health_file):
                with open(self.health_file, 'r', encoding='utf-8') as f:
                    health_data = json.load(f)

                # 从字典创建HealthStatus对象
                status = HealthStatus(
                    system_status=health_data.get("system_status", "healthy"),
                    last_check=datetime.fromisoformat(health_data.get("last_check", datetime.now().isoformat())),
                    components=health_data.get("components", {}),
                    alerts=health_data.get("alerts", [])
                )

                # 更新最后检查时间
                status.last_check = datetime.now()
                self._save_status(status)

                return status

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            self.logger.warning(f"加载健康状态文件失败，使用初始状态: {e}")

        # 返回初始状态
        return self._create_initial_status()

    def update_component_status(self, component_name: str, status: str, **metrics) -> None:
        """
        更新组件状态

        Args:
            component_name: 组件名称
            status: 组件状态 (running, warning, critical, idle等)
            **metrics: 组件指标，如last_heartbeat、pending_tasks等
        """
        current_status = self.get_status()

        # 更新组件状态
        if component_name not in current_status.components:
            current_status.components[component_name] = {}

        current_status.components[component_name]["status"] = status
        current_status.components[component_name].update(metrics)

        # 重新计算系统状态
        self._recalculate_system_status(current_status)

        # 保存更新后的状态
        self._save_status(current_status)

        self.logger.info(f"更新组件状态: {component_name} -> {status}")

    def add_alert(self, level: str, component: str, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        """
        添加警报

        Args:
            level: 警报级别 (info, warning, error, critical)
            component: 触发警报的组件
            message: 警报消息
            details: 警报详细信息
        """
        current_status = self.get_status()

        # 创建警报对象
        alert = {
            "level": level,
            "component": component,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "details": details or {}
        }

        # 添加警报到列表开头（最新的在前面）
        current_status.alerts.insert(0, alert)

        # 限制警报数量（保留最近的50条）
        if len(current_status.alerts) > 50:
            current_status.alerts = current_status.alerts[:50]

        # 根据警报级别可能更新系统状态
        if level in ["error", "critical"]:
            # 如果组件存在，更新其状态
            if component in current_status.components:
                current_status.components[component]["status"] = level
            else:
                # 如果组件不存在，创建它
                current_status.components[component] = {"status": level}

            # 重新计算系统状态
            self._recalculate_system_status(current_status)

        # 保存更新后的状态
        self._save_status(current_status)

        self.logger.info(f"添加警报: {level} - {component} - {message}")

    def perform_system_check(self) -> HealthStatus:
        """
        执行系统健康检查

        检查磁盘空间、任务目录状态等系统级健康指标。

        Returns:
            HealthStatus: 包含系统检查结果的健康状态
        """
        current_status = self.get_status()

        # 添加系统检查组件
        system_check_metrics = {"status": "healthy"}

        try:
            # 检查磁盘空间
            disk_info = self._check_disk_space()
            system_check_metrics.update(disk_info)

            # 检查磁盘使用率
            if disk_info.get("disk_usage_percent", 0) > 95:
                system_check_metrics["status"] = "critical"
                self.add_alert(
                    level="critical",
                    component="system_check",
                    message=f"磁盘空间严重不足: {disk_info.get('disk_usage_percent', 0):.1f}% 已使用",
                    details=disk_info
                )
            elif disk_info.get("disk_usage_percent", 0) > 85:
                system_check_metrics["status"] = "warning"
                self.add_alert(
                    level="warning",
                    component="system_check",
                    message=f"磁盘空间不足: {disk_info.get('disk_usage_percent', 0):.1f}% 已使用",
                    details=disk_info
                )

            # 检查任务目录
            task_dir_status = self._check_task_directory()
            system_check_metrics.update(task_dir_status)

            if not task_dir_status.get("task_dir_exists", True):
                system_check_metrics["status"] = "warning"
                self.add_alert(
                    level="warning",
                    component="system_check",
                    message="任务目录不存在",
                    details=task_dir_status
                )

        except Exception as e:
            system_check_metrics["status"] = "critical"
            self.add_alert(
                level="critical",
                component="system_check",
                message=f"系统检查失败: {str(e)}",
                details={"exception": str(e)}
            )
            self.logger.error(f"系统检查失败: {e}")

        # 更新系统检查组件状态
        component_status = system_check_metrics.pop("status")  # 移除status，因为它已经是参数
        self.update_component_status("system_check", component_status, **system_check_metrics)

        return self.get_status()

    def _recalculate_system_status(self, status: HealthStatus) -> None:
        """
        重新计算系统状态

        基于组件状态计算整体系统状态：
        - 任何组件状态为"critical" → 系统状态为"critical"
        - 任何组件状态为"warning" → 系统状态为"warning"
        - 否则 → 系统状态为"healthy"

        Args:
            status: 要重新计算的健康状态
        """
        system_status = "healthy"

        for component_name, component_data in status.components.items():
            component_status = component_data.get("status", "").lower()

            if component_status == "critical":
                system_status = "critical"
                break  # critical优先级最高，无需继续检查
            elif component_status == "warning" and system_status != "critical":
                system_status = "warning"
            # 其他状态不影响系统状态

        status.system_status = system_status
        status.last_check = datetime.now()

    def _save_status(self, status: HealthStatus) -> None:
        """
        保存健康状态到文件

        Args:
            status: 要保存的健康状态
        """
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(self.health_file), exist_ok=True)

            # 转换为字典并保存
            health_dict = status.to_dict()
            with open(self.health_file, 'w', encoding='utf-8') as f:
                json.dump(health_dict, f, ensure_ascii=False, indent=2)

        except Exception as e:
            self.logger.error(f"保存健康状态失败: {e}")
            raise

    def _create_initial_status(self) -> HealthStatus:
        """
        创建初始健康状态

        Returns:
            HealthStatus: 初始健康状态
        """
        status = HealthStatus.create_initial_status()
        self._save_status(status)
        return status

    def _check_disk_space(self) -> Dict[str, Any]:
        """
        检查磁盘空间

        Returns:
            包含磁盘空间信息的字典
        """
        try:
            # 获取健康文件所在磁盘的信息
            disk_usage = shutil.disk_usage(os.path.dirname(self.health_file))

            total_gb = disk_usage.total / (1024 ** 3)
            free_gb = disk_usage.free / (1024 ** 3)
            used_gb = total_gb - free_gb
            usage_percent = (used_gb / total_gb) * 100 if total_gb > 0 else 0

            return {
                "disk_total_gb": round(total_gb, 2),
                "disk_free_gb": round(free_gb, 2),
                "disk_used_gb": round(used_gb, 2),
                "disk_usage_percent": round(usage_percent, 2),
                "check_time": datetime.now().isoformat()
            }

        except Exception as e:
            self.logger.warning(f"检查磁盘空间失败: {e}")
            return {
                "disk_check_error": str(e),
                "check_time": datetime.now().isoformat()
            }

    def _check_task_directory(self) -> Dict[str, Any]:
        """
        检查任务目录状态

        Returns:
            包含任务目录状态信息的字典
        """
        try:
            # 检查任务目录（假设在base_path/tasks）
            task_dir = os.path.join(self.base_path, "tasks")
            results_dir = os.path.join(self.base_path, "results")

            task_dir_exists = os.path.exists(task_dir)
            results_dir_exists = os.path.exists(results_dir)

            # 如果目录存在，统计文件数量
            task_files_count = 0
            if task_dir_exists:
                task_files = [f for f in os.listdir(task_dir) if f.endswith('.json')]
                task_files_count = len(task_files)

            result_files_count = 0
            if results_dir_exists:
                result_files = [f for f in os.listdir(results_dir) if f.endswith(('.json', '.csv', '.pdf'))]
                result_files_count = len(result_files)

            return {
                "task_dir_exists": task_dir_exists,
                "results_dir_exists": results_dir_exists,
                "task_files_count": task_files_count,
                "result_files_count": result_files_count,
                "check_time": datetime.now().isoformat()
            }

        except Exception as e:
            self.logger.warning(f"检查任务目录失败: {e}")
            return {
                "directory_check_error": str(e),
                "check_time": datetime.now().isoformat()
            }