"""任务管理器

负责任务创建、管理和验证，集成安全防护。
"""

import os
import json
import uuid
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from .models import DashboardTask, TaskStatus, validate_task_type, validate_task_status
from .security import SecurityValidator, security_validator
from .shared_dirs import SharedDirectoryManager
from .file_lock import FileLock


class TaskManager:
    """任务管理器

    负责任务的创建、验证、存储和状态管理。
    集成安全验证，确保所有任务内容都经过安全检查。
    """

    def __init__(self, base_path: str = ".", lock_timeout: int = 30):
        """初始化任务管理器

        Args:
            base_path: 基础目录路径
            lock_timeout: 文件锁超时时间（秒）
        """
        self.base_path = os.path.abspath(base_path)
        self.lock_timeout = lock_timeout

        # 初始化组件
        self.security_validator = security_validator
        self.shared_dirs = SharedDirectoryManager(base_path=self.base_path, create_dirs=True)
        self.logger = logging.getLogger(__name__)

        # 确保目录存在
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """确保必要的目录存在"""
        try:
            # SharedDirectoryManager已经创建了目录，这里只是双重检查
            for dir_name in ["tasks", "results", "status", "cache", "locks"]:
                dir_path = self.shared_dirs.get_subdir_path(dir_name)
                if not os.path.exists(dir_path):
                    os.makedirs(dir_path, exist_ok=True)

        except Exception as e:
            self.logger.error(f"创建目录失败: {e}")
            raise

    def create_task(self, task_type: str, user_config: Dict[str, Any],
                   priority: str = "normal", task_id: Optional[str] = None) -> DashboardTask:
        """创建新任务

        Args:
            task_type: 任务类型（data_filter, strategy_backtest, indicator_adjust）
            user_config: 用户配置
            priority: 优先级（low, normal, high）
            task_id: 可选的任务ID，如果为None则自动生成

        Returns:
            DashboardTask: 创建的任务对象

        Raises:
            ValueError: 如果任务数据无效或不安全
        """
        # 验证任务类型
        if not validate_task_type(task_type):
            raise ValueError(f"无效的任务类型: {task_type}")

        # 验证优先级
        valid_priorities = {"low", "normal", "high"}
        if priority not in valid_priorities:
            raise ValueError(f"无效的优先级: {priority}")

        # 验证用户配置
        # 创建一个临时的任务数据用于验证
        test_task_data = {
            "task_id": "test_validation",
            "task_type": task_type,
            "status": "pending",
            "user_config": user_config
        }
        if not self.security_validator.validate_task_content(test_task_data):
            raise ValueError("用户配置不安全或无效")

        # 生成或验证任务ID
        if task_id is None:
            task_id = self._generate_task_id()
        else:
            if not isinstance(task_id, str) or not task_id.strip():
                raise ValueError("任务ID必须是非空字符串")
            # 清理任务ID而不是拒绝
            task_id = self.security_validator.sanitize_filename(task_id)
            if not task_id.strip():
                raise ValueError("任务ID清理后为空")

        # 创建任务对象
        task_data = {
            "task_id": task_id,
            "task_type": task_type,
            "status": "pending",
            "user_config": user_config,
            "priority": priority,
            "timestamp": datetime.now().isoformat(),
            "metadata": {
                "created_by": "task_manager",
                "created_at": datetime.now().isoformat()
            }
        }

        # 验证整个任务数据
        if not self.security_validator.validate_task_content(task_data):
            raise ValueError("任务数据不安全或无效")

        # 创建DashboardTask对象
        try:
            task = DashboardTask.from_dict(task_data)
        except Exception as e:
            raise ValueError(f"创建任务对象失败: {e}")

        # 保存任务文件
        self._save_task(task)

        # 创建初始状态文件
        self._update_status_file(task_id, "pending", 0, None, None)

        self.logger.info(f"创建任务成功: {task_id} ({task_type})")
        return task

    def _generate_task_id(self) -> str:
        """生成唯一的任务ID"""
        # 使用UUID生成唯一ID，并清理以确保安全
        raw_id = str(uuid.uuid4())
        safe_id = self.security_validator.sanitize_filename(raw_id)

        # 移除UUID中的连字符，使其更简洁
        safe_id = safe_id.replace("-", "")

        # 添加前缀以便识别
        return f"task_{safe_id[:16]}"

    def _save_task(self, task: DashboardTask) -> None:
        """保存任务到文件"""
        task_file = self.shared_dirs.get_task_path(task.task_id)

        # 使用文件锁确保并发安全
        lock = FileLock.create_task_lock(
            task_id=task.task_id,
            lock_dir=self.shared_dirs.get_subdir_path("locks"),
            timeout=self.lock_timeout
        )

        try:
            with lock:
                # 将任务转换为字典
                task_dict = task.to_dict()

                # 再次验证任务数据
                if not self.security_validator.validate_task_content(task_dict):
                    raise ValueError("任务数据在保存前验证失败")

                # 保存到文件
                with open(task_file, 'w', encoding='utf-8') as f:
                    json.dump(task_dict, f, ensure_ascii=False, indent=2)

        except TimeoutError:
            self.logger.error(f"保存任务时获取锁超时: {task.task_id}")
            raise
        except Exception as e:
            self.logger.error(f"保存任务失败 {task.task_id}: {e}")
            raise

    def get_task(self, task_id: str) -> Optional[DashboardTask]:
        """获取任务

        Args:
            task_id: 任务ID

        Returns:
            DashboardTask: 任务对象，如果不存在则返回None
        """
        task_file = self.shared_dirs.get_task_path(task_id)

        if not os.path.exists(task_file):
            self.logger.warning(f"任务文件不存在: {task_file}")
            return None

        # 使用文件锁保护读取
        lock = FileLock.create_task_lock(
            task_id=task_id,
            lock_dir=self.shared_dirs.get_subdir_path("locks"),
            timeout=self.lock_timeout
        )

        try:
            with lock:
                with open(task_file, 'r', encoding='utf-8') as f:
                    task_data = json.load(f)

                # 验证任务数据
                if not self.security_validator.validate_task_content(task_data):
                    self.logger.warning(f"任务数据不安全: {task_id}")
                    return None

                # 创建任务对象
                return DashboardTask.from_dict(task_data)

        except (TimeoutError, FileNotFoundError, json.JSONDecodeError) as e:
            self.logger.warning(f"读取任务失败 {task_id}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"获取任务时发生错误 {task_id}: {e}")
            return None

    def update_task_status(self, task_id: str, status: str,
                          progress_percent: Optional[int] = None,
                          error_message: Optional[str] = None,
                          result_path: Optional[str] = None) -> bool:
        """更新任务状态

        Args:
            task_id: 任务ID
            status: 新状态
            progress_percent: 进度百分比（0-100）
            error_message: 错误信息（如果状态为failed）
            result_path: 结果文件路径

        Returns:
            bool: 更新是否成功
        """
        # 验证状态
        if not validate_task_status(status):
            self.logger.error(f"无效的任务状态: {status}")
            return False

        # 验证进度百分比
        if progress_percent is not None:
            if not isinstance(progress_percent, int) or progress_percent < 0 or progress_percent > 100:
                self.logger.error(f"无效的进度百分比: {progress_percent}")
                return False

        # 获取任务
        task = self.get_task(task_id)
        if task is None:
            self.logger.error(f"任务不存在: {task_id}")
            return False

        # 更新任务状态
        task.status = status

        # 保存更新后的任务
        try:
            self._save_task(task)
        except Exception as e:
            self.logger.error(f"保存任务状态更新失败 {task_id}: {e}")
            return False

        # 创建或更新状态文件
        return self._update_status_file(task_id, status, progress_percent, error_message, result_path)

    def _update_status_file(self, task_id: str, status: str,
                           progress_percent: Optional[int],
                           error_message: Optional[str],
                           result_path: Optional[str]) -> bool:
        """更新状态文件"""
        status_file = self.shared_dirs.get_status_path(task_id)

        # 创建状态对象
        status_data = {
            "task_id": task_id,
            "current_status": status,
            "progress_percent": progress_percent or 0,
            "current_step": self._get_step_from_status(status),
            "last_update": datetime.now().isoformat()
        }

        if error_message:
            status_data["error_message"] = error_message
        if result_path:
            # 验证结果路径
            if self.security_validator.validate_file_path(result_path, self.base_path):
                status_data["result_path"] = result_path
            else:
                self.logger.warning(f"结果路径不安全: {result_path}")

        try:
            # 验证状态数据
            # 状态数据不需要完整的任务验证，只需要基本验证
            if not task_id or not isinstance(task_id, str):
                self.logger.warning(f"无效的任务ID: {task_id}")
                return False

            if not validate_task_status(status):
                self.logger.warning(f"无效的任务状态: {status}")
                return False

            # 检查是否有恶意内容
            if self.security_validator._contains_malicious_content(task_id):
                self.logger.warning(f"任务ID包含恶意内容: {task_id}")
                return False

            # 保存状态文件
            with open(status_file, 'w', encoding='utf-8') as f:
                json.dump(status_data, f, ensure_ascii=False, indent=2)

            return True

        except Exception as e:
            self.logger.error(f"更新状态文件失败 {task_id}: {e}")
            return False

    def _get_step_from_status(self, status: str) -> str:
        """根据状态获取当前步骤"""
        steps = {
            "pending": "等待处理",
            "processing": "处理中",
            "completed": "已完成",
            "failed": "处理失败",
            "cancelled": "已取消"
        }
        return steps.get(status, "未知状态")

    def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """获取任务状态

        Args:
            task_id: 任务ID

        Returns:
            TaskStatus: 状态对象，如果不存在则返回None
        """
        status_file = self.shared_dirs.get_status_path(task_id)

        if not os.path.exists(status_file):
            return None

        try:
            with open(status_file, 'r', encoding='utf-8') as f:
                status_data = json.load(f)

            # 验证状态数据
            # 状态数据只需要基本验证
            if "task_id" not in status_data or "current_status" not in status_data:
                self.logger.warning(f"状态数据缺少必需字段: {task_id}")
                return None

            # 检查任务ID
            task_id_from_data = status_data.get("task_id")
            if task_id_from_data != task_id:
                self.logger.warning(f"状态数据中的任务ID不匹配: {task_id_from_data} != {task_id}")
                return None

            # 检查恶意内容
            status_json = json.dumps(status_data)
            if self.security_validator._contains_malicious_content(status_json):
                self.logger.warning(f"状态数据包含恶意内容: {task_id}")
                return None

            return TaskStatus.from_dict(status_data)

        except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
            self.logger.warning(f"读取状态文件失败 {task_id}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"获取任务状态时发生错误 {task_id}: {e}")
            return None

    def list_tasks(self, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出任务

        Args:
            status_filter: 状态过滤器（如 "pending", "completed"）

        Returns:
            List[Dict[str, Any]]: 任务信息列表
        """
        tasks = []

        try:
            # 获取所有任务文件
            task_files = self.shared_dirs.list_files("tasks", "*.json")

            for task_file in task_files:
                try:
                    # 提取任务ID
                    filename = os.path.basename(task_file)
                    if filename.endswith("_status.json"):
                        continue  # 跳过状态文件

                    task_id = filename[:-5]  # 移除.json后缀

                    # 获取任务
                    task = self.get_task(task_id)
                    if task is None:
                        continue

                    # 应用状态过滤器
                    if status_filter and task.status != status_filter:
                        continue

                    # 获取状态
                    task_status = self.get_task_status(task_id)

                    # 构建任务信息
                    task_info = {
                        "task_id": task_id,
                        "task_type": task.task_type,
                        "status": task.status,
                        "priority": task.priority,
                        "created_at": task.timestamp.isoformat() if hasattr(task.timestamp, 'isoformat') else str(task.timestamp),
                        "progress": task_status.progress_percent if task_status else 0,
                        "current_step": task_status.current_step if task_status else "unknown"
                    }

                    tasks.append(task_info)

                except Exception as e:
                    self.logger.warning(f"处理任务文件失败 {task_file}: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"列出任务失败: {e}")

        return tasks

    def delete_task(self, task_id: str) -> bool:
        """删除任务

        Args:
            task_id: 任务ID

        Returns:
            bool: 删除是否成功
        """
        try:
            # 获取所有相关文件
            task_file = self.shared_dirs.get_task_path(task_id)
            status_file = self.shared_dirs.get_status_path(task_id)

            # 检查文件是否存在
            task_exists = os.path.exists(task_file)
            status_exists = os.path.exists(status_file)

            if not task_exists and not status_exists:
                self.logger.warning(f"任务文件不存在: {task_id}")
                return False

            # 使用文件锁保护删除操作
            lock = FileLock.create_task_lock(
                task_id=task_id,
                lock_dir=self.shared_dirs.get_subdir_path("locks"),
                timeout=self.lock_timeout
            )

            with lock:
                # 删除任务文件
                if task_exists:
                    os.remove(task_file)

                # 删除状态文件
                if status_exists:
                    os.remove(status_file)

                self.logger.info(f"删除任务成功: {task_id}")
                return True

        except TimeoutError:
            self.logger.error(f"删除任务时获取锁超时: {task_id}")
            return False
        except Exception as e:
            self.logger.error(f"删除任务失败 {task_id}: {e}")
            return False

    def cleanup_old_tasks(self, max_age_days: int = 30) -> int:
        """清理旧任务

        Args:
            max_age_days: 最大保留天数

        Returns:
            int: 清理的任务数量
        """
        cleaned_count = 0

        try:
            # 获取所有任务
            all_tasks = self.list_tasks()

            for task_info in all_tasks:
                task_id = task_info["task_id"]
                created_at_str = task_info["created_at"]

                try:
                    # 解析创建时间
                    created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                    age_days = (datetime.now() - created_at).days

                    # 检查是否超过最大年龄
                    if age_days > max_age_days:
                        # 只删除已完成或失败的任务
                        status = task_info["status"]
                        if status in ["completed", "failed", "cancelled"]:
                            if self.delete_task(task_id):
                                cleaned_count += 1

                except (ValueError, TypeError) as e:
                    self.logger.warning(f"解析任务时间失败 {task_id}: {e}")
                    continue

            self.logger.info(f"清理了 {cleaned_count} 个旧任务")
            return cleaned_count

        except Exception as e:
            self.logger.error(f"清理旧任务失败: {e}")
            return 0

    def validate_task_file(self, file_path: str) -> bool:
        """验证任务文件是否安全有效

        Args:
            file_path: 任务文件路径

        Returns:
            bool: 文件是否安全有效
        """
        try:
            # 验证文件路径
            if not self.security_validator.validate_file_path(file_path, self.base_path):
                return False

            # 读取文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                task_data = json.load(f)

            # 验证任务内容
            if not self.security_validator.validate_task_content(task_data):
                return False

            # 尝试创建任务对象
            DashboardTask.from_dict(task_data)

            return True

        except Exception as e:
            self.logger.warning(f"验证任务文件失败 {file_path}: {e}")
            return False


# 创建全局任务管理器实例
task_manager = TaskManager()