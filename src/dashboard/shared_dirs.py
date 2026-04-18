"""共享目录管理器

管理仪表盘插件的共享目录结构，集成安全验证。
"""

import os
from typing import Optional, Dict, Any
from pathlib import Path

from .security import SecurityValidator, security_validator


class SharedDirectoryManager:
    """共享目录管理器

    管理仪表盘插件的目录结构：
    - base_path/tasks/ - 任务文件
    - base_path/results/ - 结果文件
    - base_path/status/ - 状态文件
    - base_path/cache/ - 缓存文件

    所有路径生成都经过安全验证。
    """

    def __init__(self, base_path: str = ".", create_dirs: bool = True):
        """初始化共享目录管理器

        Args:
            base_path: 基础目录路径
            create_dirs: 是否自动创建目录结构
        """
        self.base_path = os.path.abspath(base_path)
        self.security_validator = security_validator

        # 验证基础目录路径
        if not self.security_validator.validate_directory_path(self.base_path, self.base_path):
            raise ValueError(f"基础目录路径不安全: {self.base_path}")

        # 定义子目录
        self.subdirs = {
            "tasks": "tasks",
            "results": "results",
            "status": "status",
            "cache": "cache",
            "locks": "locks"
        }

        # 创建目录结构
        if create_dirs:
            self._create_directory_structure()

    def _create_directory_structure(self) -> None:
        """创建目录结构"""
        try:
            # 创建基础目录
            os.makedirs(self.base_path, exist_ok=True)

            # 创建所有子目录
            for dir_name in self.subdirs.values():
                dir_path = self.get_subdir_path(dir_name)
                os.makedirs(dir_path, exist_ok=True)

        except Exception as e:
            raise RuntimeError(f"创建目录结构失败: {e}")

    def get_subdir_path(self, subdir_name: str) -> str:
        """获取子目录路径

        Args:
            subdir_name: 子目录名称

        Returns:
            str: 子目录的完整路径

        Raises:
            ValueError: 如果子目录名称无效或不安全
        """
        if subdir_name not in self.subdirs.values():
            raise ValueError(f"无效的子目录名称: {subdir_name}")

        dir_path = os.path.join(self.base_path, subdir_name)

        # 验证目录路径
        if not self.security_validator.validate_directory_path(dir_path, self.base_path):
            raise ValueError(f"子目录路径不安全: {dir_path}")

        return dir_path

    def get_task_path(self, task_id: str, filename: Optional[str] = None) -> str:
        """获取任务文件路径

        Args:
            task_id: 任务ID
            filename: 可选的文件名，如果为None则使用task_id.json

        Returns:
            str: 任务文件的完整路径

        Raises:
            ValueError: 如果任务ID或文件名不安全
        """
        # 验证任务ID
        if not task_id or not isinstance(task_id, str):
            raise ValueError("任务ID必须是非空字符串")

        # 清理任务ID
        safe_task_id = self.security_validator.sanitize_filename(task_id)

        # 确定文件名
        if filename:
            safe_filename = self.security_validator.sanitize_filename(filename)
        else:
            safe_filename = f"{safe_task_id}.json"

        # 构建完整路径
        tasks_dir = self.get_subdir_path("tasks")
        file_path = os.path.join(tasks_dir, safe_filename)

        # 验证文件路径
        if not self.security_validator.validate_file_path(file_path, self.base_path):
            raise ValueError(f"任务文件路径不安全: {file_path}")

        return file_path

    def get_status_path(self, task_id: str) -> str:
        """获取状态文件路径

        Args:
            task_id: 任务ID

        Returns:
            str: 状态文件的完整路径
        """
        safe_task_id = self.security_validator.sanitize_filename(task_id)
        filename = f"{safe_task_id}_status.json"
        return self.get_task_path(task_id, filename)

    def get_result_path(self, task_id: str, result_type: str = "data") -> str:
        """获取结果文件路径

        Args:
            task_id: 任务ID
            result_type: 结果类型（data, report, config等）

        Returns:
            str: 结果文件的完整路径
        """
        # 验证结果类型
        valid_result_types = {"data", "report", "config", "log", "summary"}
        if result_type not in valid_result_types:
            raise ValueError(f"无效的结果类型: {result_type}")

        safe_task_id = self.security_validator.sanitize_filename(task_id)

        # 根据结果类型确定扩展名
        extensions = {
            "data": ".csv",
            "report": ".pdf",
            "config": ".json",
            "log": ".log",
            "summary": ".txt"
        }

        ext = extensions.get(result_type, ".json")
        filename = f"{safe_task_id}_{result_type}{ext}"

        # 获取结果目录
        results_dir = self.get_subdir_path("results")
        file_path = os.path.join(results_dir, filename)

        # 验证文件路径
        if not self.security_validator.validate_file_path(file_path, self.base_path):
            raise ValueError(f"结果文件路径不安全: {file_path}")

        return file_path

    def get_cache_path(self, cache_key: str, extension: str = ".cache") -> str:
        """获取缓存文件路径

        Args:
            cache_key: 缓存键
            extension: 文件扩展名

        Returns:
            str: 缓存文件的完整路径
        """
        # 验证扩展名
        if not extension.startswith("."):
            extension = f".{extension}"

        # 清理缓存键
        safe_cache_key = self.security_validator.sanitize_filename(cache_key)
        filename = f"{safe_cache_key}{extension}"

        # 获取缓存目录
        cache_dir = self.get_subdir_path("cache")
        file_path = os.path.join(cache_dir, filename)

        # 验证文件路径
        if not self.security_validator.validate_file_path(file_path, self.base_path):
            raise ValueError(f"缓存文件路径不安全: {file_path}")

        return file_path

    def get_lock_path(self, lock_name: str) -> str:
        """获取锁文件路径

        Args:
            lock_name: 锁名称

        Returns:
            str: 锁文件的完整路径
        """
        # 清理锁名称
        safe_lock_name = self.security_validator.sanitize_filename(lock_name)
        filename = f".lock_{safe_lock_name}"

        # 获取锁目录
        locks_dir = self.get_subdir_path("locks")
        file_path = os.path.join(locks_dir, filename)

        # 验证文件路径
        if not self.security_validator.validate_file_path(file_path, self.base_path):
            raise ValueError(f"锁文件路径不安全: {file_path}")

        return file_path

    def validate_and_resolve_path(self, relative_path: str) -> str:
        """验证并解析相对路径

        Args:
            relative_path: 相对路径

        Returns:
            str: 解析后的绝对路径

        Raises:
            ValueError: 如果路径不安全
        """
        # 解析路径
        abs_path = os.path.join(self.base_path, relative_path)
        abs_path = os.path.abspath(abs_path)

        # 验证路径
        if not self.security_validator.validate_file_path(abs_path, self.base_path):
            raise ValueError(f"路径不安全: {relative_path}")

        return abs_path

    def list_files(self, subdir: str, pattern: str = "*") -> list:
        """列出目录中的文件

        Args:
            subdir: 子目录名称
            pattern: 文件模式（如 "*.json"）

        Returns:
            list: 文件路径列表
        """
        dir_path = self.get_subdir_path(subdir)

        try:
            files = []
            for filename in os.listdir(dir_path):
                file_path = os.path.join(dir_path, filename)

                # 验证文件路径
                if not self.security_validator.validate_file_path(file_path, self.base_path):
                    continue

                # 检查模式匹配
                if pattern == "*" or filename.endswith(pattern.lstrip("*")):
                    files.append(file_path)

            return files

        except Exception as e:
            raise RuntimeError(f"列出文件失败: {e}")

    def cleanup_old_files(self, subdir: str, max_age_days: int = 7) -> int:
        """清理旧文件

        Args:
            subdir: 子目录名称
            max_age_days: 最大保留天数

        Returns:
            int: 清理的文件数量
        """
        import time
        from datetime import datetime, timedelta

        dir_path = self.get_subdir_path(subdir)
        cutoff_time = time.time() - (max_age_days * 24 * 3600)

        cleaned_count = 0

        try:
            for filename in os.listdir(dir_path):
                file_path = os.path.join(dir_path, filename)

                # 验证文件路径
                if not self.security_validator.validate_file_path(file_path, self.base_path):
                    continue

                try:
                    file_stat = os.stat(file_path)
                    if file_stat.st_mtime < cutoff_time:
                        os.remove(file_path)
                        cleaned_count += 1
                except OSError:
                    # 忽略无法删除的文件
                    continue

            return cleaned_count

        except Exception as e:
            raise RuntimeError(f"清理旧文件失败: {e}")

    def get_directory_info(self) -> Dict[str, Any]:
        """获取目录信息

        Returns:
            Dict[str, Any]: 包含目录信息的字典
        """
        info = {
            "base_path": self.base_path,
            "subdirectories": {},
            "total_size": 0
        }

        try:
            for dir_name in self.subdirs.values():
                dir_path = self.get_subdir_path(dir_name)

                # 计算目录大小
                dir_size = 0
                file_count = 0

                for root, dirs, files in os.walk(dir_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        if self.security_validator.validate_file_path(file_path, self.base_path):
                            try:
                                dir_size += os.path.getsize(file_path)
                                file_count += 1
                            except OSError:
                                pass

                info["subdirectories"][dir_name] = {
                    "path": dir_path,
                    "size_bytes": dir_size,
                    "file_count": file_count
                }
                info["total_size"] += dir_size

        except Exception:
            # 如果获取信息失败，返回基本结构
            pass

        return info


# 创建全局目录管理器实例（使用当前目录）
shared_dirs = SharedDirectoryManager()