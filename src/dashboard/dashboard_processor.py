"""仪表盘任务处理器

处理仪表盘任务的调度和执行，包含文件锁机制防止竞态条件
"""
import os
import time
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from .models import DashboardTask, TaskStatus
from .file_lock import FileLock


class DashboardProcessor:
    """仪表盘任务处理器

    负责处理仪表盘任务的调度、执行和状态管理。
    使用文件锁机制防止并发处理导致的竞态条件。
    """

    def __init__(self, task_dir: str = ".", lock_dir: str = ".", timeout: int = 30):
        """
        初始化任务处理器

        Args:
            task_dir: 任务文件目录
            lock_dir: 锁文件目录
            timeout: 锁超时时间（秒）
        """
        self.task_dir = task_dir
        self.lock_dir = lock_dir
        self.timeout = timeout
        self.logger = logging.getLogger(__name__)

        # 确保目录存在
        os.makedirs(task_dir, exist_ok=True)
        os.makedirs(lock_dir, exist_ok=True)

    def find_pending_tasks(self) -> List[str]:
        """
        查找待处理任务

        扫描任务目录，查找状态为"pending"的任务。
        使用文件锁确保并发安全。

        Returns:
            待处理任务ID列表
        """
        pending_tasks = []

        try:
            # 获取任务目录中的所有文件
            if not os.path.exists(self.task_dir):
                self.logger.warning(f"任务目录不存在: {self.task_dir}")
                return []

            for filename in os.listdir(self.task_dir):
                if not filename.endswith('.json'):
                    continue

                task_file = os.path.join(self.task_dir, filename)
                task_id = filename[:-5]  # 移除.json后缀

                try:
                    # 使用文件锁保护任务读取
                    lock = FileLock.create_task_lock(
                        task_id=task_id,
                        lock_dir=self.lock_dir,
                        timeout=self.timeout
                    )

                    with lock:
                        # 读取任务数据
                        import json
                        with open(task_file, 'r', encoding='utf-8') as f:
                            task_data = json.load(f)

                        # 检查任务状态
                        if task_data.get("status") == "pending":
                            pending_tasks.append(task_id)

                except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
                    self.logger.warning(f"读取任务文件失败 {task_file}: {e}")
                    continue
                except TimeoutError:
                    self.logger.warning(f"获取任务锁超时 {task_id}")
                    continue

        except Exception as e:
            self.logger.error(f"查找待处理任务失败: {e}")

        return pending_tasks

    def process_task(self, task_id: str) -> bool:
        """
        处理任务

        使用文件锁确保同一任务不会被多个进程同时处理。

        Args:
            task_id: 任务ID

        Returns:
            bool: 处理是否成功
        """
        task_file = os.path.join(self.task_dir, f"{task_id}.json")
        status_file = os.path.join(self.task_dir, f"{task_id}_status.json")

        if not os.path.exists(task_file):
            self.logger.error(f"任务文件不存在: {task_file}")
            return False

        # 创建任务锁
        lock = FileLock.create_task_lock(
            task_id=task_id,
            lock_dir=self.lock_dir,
            timeout=self.timeout * 2  # 处理时间可能较长，使用更长的超时
        )

        try:
            # 获取锁
            with lock:
                self.logger.info(f"开始处理任务: {task_id}")

                # 读取任务数据
                import json
                with open(task_file, 'r', encoding='utf-8') as f:
                    task_data = json.load(f)

                # 更新任务状态为处理中
                task_data["status"] = "processing"
                task_data["start_time"] = datetime.now().isoformat()

                with open(task_file, 'w', encoding='utf-8') as f:
                    json.dump(task_data, f, ensure_ascii=False, indent=2)

                # 创建任务状态
                task_status = TaskStatus(
                    task_id=task_id,
                    current_status="processing",
                    progress_percent=0,
                    current_step="开始处理",
                    start_time=datetime.now()
                )

                # 保存任务状态
                with open(status_file, 'w', encoding='utf-8') as f:
                    json.dump(task_status.to_dict(), f, ensure_ascii=False, indent=2)

                # 模拟任务处理（实际应用中应替换为实际处理逻辑）
                try:
                    # 根据任务类型执行不同处理
                    task_type = task_data.get("task_type")
                    if not task_type:
                        raise ValueError("任务数据缺少必需的'task_type'字段")

                    self._process_by_type(task_id, task_type, task_data, task_status)

                    # 更新任务状态为完成
                    task_data["status"] = "completed"
                    task_data["end_time"] = datetime.now().isoformat()

                    task_status.current_status = "completed"
                    task_status.progress_percent = 100
                    task_status.current_step = "处理完成"
                    task_status.last_update = datetime.now()

                except Exception as e:
                    # 处理失败
                    self.logger.error(f"任务处理失败 {task_id}: {e}")

                    task_data["status"] = "failed"
                    task_data["error"] = str(e)
                    task_data["end_time"] = datetime.now().isoformat()

                    task_status.current_status = "failed"
                    task_status.error_message = str(e)
                    task_status.last_update = datetime.now()

                # 保存更新后的任务数据和状态
                with open(task_file, 'w', encoding='utf-8') as f:
                    json.dump(task_data, f, ensure_ascii=False, indent=2)

                with open(status_file, 'w', encoding='utf-8') as f:
                    json.dump(task_status.to_dict(), f, ensure_ascii=False, indent=2)

                self.logger.info(f"任务处理完成: {task_id}, 状态: {task_status.current_status}")
                return task_status.current_status == "completed"

        except TimeoutError:
            self.logger.error(f"获取任务锁超时: {task_id}")
            return False
        except Exception as e:
            self.logger.error(f"处理任务失败 {task_id}: {e}")
            return False

    def _process_by_type(self, task_id: str, task_type: str, task_data: Dict[str, Any], task_status: TaskStatus):
        """
        根据任务类型执行处理

        Args:
            task_id: 任务ID
            task_type: 任务类型
            task_data: 任务数据
            task_status: 任务状态对象
        """
        if task_type == "data_filter":
            self._process_data_filter(task_id, task_data, task_status)
        elif task_type == "strategy_backtest":
            self._process_strategy_backtest(task_id, task_data, task_status)
        elif task_type == "indicator_adjust":
            self._process_indicator_adjust(task_id, task_data, task_status)
        else:
            raise ValueError(f"不支持的任务类型: {task_type}")

    def _process_data_filter(self, task_id: str, task_data: Dict[str, Any], task_status: TaskStatus):
        """处理数据筛选任务"""
        self.logger.info(f"处理数据筛选任务: {task_id}")

        # 模拟处理步骤
        steps = [
            ("读取配置", 10),
            ("获取数据", 30),
            ("应用筛选条件", 50),
            ("生成结果", 80),
            ("保存结果", 100)
        ]

        for step_name, progress in steps:
            time.sleep(0.5)  # 模拟处理时间
            task_status.progress_percent = progress
            task_status.current_step = step_name
            task_status.last_update = datetime.now()

            # 更新状态文件
            status_file = os.path.join(self.task_dir, f"{task_id}_status.json")
            import json
            with open(status_file, 'w', encoding='utf-8') as f:
                json.dump(task_status.to_dict(), f, ensure_ascii=False, indent=2)

        # 设置结果路径
        task_status.result_path = f"results/{task_id}_filtered.csv"

    def _process_strategy_backtest(self, task_id: str, task_data: Dict[str, Any], task_status: TaskStatus):
        """处理策略回测任务"""
        self.logger.info(f"处理策略回测任务: {task_id}")

        # 模拟处理步骤
        steps = [
            ("加载策略", 10),
            ("获取历史数据", 25),
            ("执行回测", 50),
            ("计算指标", 75),
            ("生成报告", 100)
        ]

        for step_name, progress in steps:
            time.sleep(0.8)  # 模拟处理时间
            task_status.progress_percent = progress
            task_status.current_step = step_name
            task_status.last_update = datetime.now()

            # 更新状态文件
            status_file = os.path.join(self.task_dir, f"{task_id}_status.json")
            import json
            with open(status_file, 'w', encoding='utf-8') as f:
                json.dump(task_status.to_dict(), f, ensure_ascii=False, indent=2)

        # 设置结果路径
        task_status.result_path = f"results/{task_id}_backtest_report.pdf"

    def _process_indicator_adjust(self, task_id: str, task_data: Dict[str, Any], task_status: TaskStatus):
        """处理技术指标调整任务"""
        self.logger.info(f"处理技术指标调整任务: {task_id}")

        # 模拟处理步骤
        steps = [
            ("解析指标参数", 15),
            ("计算技术指标", 40),
            ("优化参数", 65),
            ("验证结果", 85),
            ("保存配置", 100)
        ]

        for step_name, progress in steps:
            time.sleep(0.6)  # 模拟处理时间
            task_status.progress_percent = progress
            task_status.current_step = step_name
            task_status.last_update = datetime.now()

            # 更新状态文件
            status_file = os.path.join(self.task_dir, f"{task_id}_status.json")
            import json
            with open(status_file, 'w', encoding='utf-8') as f:
                json.dump(task_status.to_dict(), f, ensure_ascii=False, indent=2)

        # 设置结果路径
        task_status.result_path = f"results/{task_id}_indicator_config.json"

    def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """
        获取任务状态

        Args:
            task_id: 任务ID

        Returns:
            TaskStatus对象或None（如果任务不存在）
        """
        status_file = os.path.join(self.task_dir, f"{task_id}_status.json")

        if not os.path.exists(status_file):
            return None

        try:
            import json
            with open(status_file, 'r', encoding='utf-8') as f:
                status_data = json.load(f)

            return TaskStatus.from_dict(status_data)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            self.logger.error(f"读取任务状态失败 {task_id}: {e}")
            return None

    def cleanup_expired_locks(self, max_age_seconds: int = 3600):
        """
        清理过期的锁文件

        Args:
            max_age_seconds: 最大年龄（秒），超过此时间的锁文件将被清理
        """
        try:
            if not os.path.exists(self.lock_dir):
                return

            current_time = time.time()
            for filename in os.listdir(self.lock_dir):
                if filename.startswith('.lock_'):
                    lock_file = os.path.join(self.lock_dir, filename)

                    try:
                        file_stat = os.stat(lock_file)
                        file_age = current_time - file_stat.st_mtime

                        if file_age > max_age_seconds:
                            self.logger.info(f"清理过期锁文件: {lock_file} (年龄: {file_age:.1f}秒)")
                            os.remove(lock_file)
                    except OSError as e:
                        self.logger.warning(f"清理锁文件失败 {lock_file}: {e}")

        except Exception as e:
            self.logger.error(f"清理过期锁文件失败: {e}")