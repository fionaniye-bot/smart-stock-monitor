"""基于文件的互斥锁实现

用于防止并发处理导致的竞态条件
"""
import os
import time
import json
import errno
from typing import Optional
from datetime import datetime


class FileLock:
    """文件锁类，基于文件系统实现互斥锁

    使用基于文件的互斥锁防止并发处理导致的竞态条件。
    锁文件命名格式：`.lock_{task_id}`
    锁文件内容包含锁信息：locked_at, timeout, process

    Attributes:
        lock_file: 锁文件路径
        timeout: 超时时间（秒）
        poll_interval: 轮询间隔（秒）
        _locked: 是否已获取锁
    """

    def __init__(self, lock_file: str, timeout: int = 30, poll_interval: float = 0.1):
        """
        初始化文件锁

        Args:
            lock_file: 锁文件路径
            timeout: 超时时间（秒）
            poll_interval: 轮询间隔（秒）
        """
        self.lock_file = lock_file
        self.timeout = timeout
        self.poll_interval = poll_interval
        self._locked = False

    def acquire(self) -> bool:
        """
        获取锁

        尝试获取锁，如果锁已被其他进程持有，则等待直到超时。
        使用轮询机制检查锁状态。

        Returns:
            bool: 是否成功获取锁
        """
        start_time = time.time()
        end_time = start_time + self.timeout

        while time.time() < end_time:
            try:
                # 检查锁是否已过期
                if self._is_lock_expired():
                    # 锁已过期，尝试清理并获取
                    try:
                        os.remove(self.lock_file)
                    except OSError:
                        pass  # 文件可能已被其他进程删除

                # 尝试创建锁文件
                try:
                    # 确保目录存在
                    lock_dir = os.path.dirname(self.lock_file)
                    if lock_dir and not os.path.exists(lock_dir):
                        try:
                            os.makedirs(lock_dir, exist_ok=True)
                        except OSError:
                            # 目录创建失败，继续等待
                            time.sleep(self.poll_interval)
                            continue

                    # 尝试以独占模式创建文件
                    fd = os.open(self.lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                    try:
                        # 写入锁信息
                        lock_data = {
                            "locked_at": time.time(),
                            "timeout": self.timeout,
                            "process": os.getpid()
                        }
                        os.write(fd, json.dumps(lock_data).encode('utf-8'))
                        os.close(fd)
                        self._locked = True
                        return True
                    except Exception:
                        # 写入失败，关闭文件描述符
                        try:
                            os.close(fd)
                        except OSError:
                            pass
                        # 删除可能已创建的文件
                        try:
                            os.remove(self.lock_file)
                        except OSError:
                            pass
                except OSError as e:
                    if e.errno == errno.EEXIST:
                        # 文件已存在，锁被其他进程持有
                        pass
                    else:
                        # 其他错误，可能是权限问题或路径无效
                        return False

                # 等待一段时间后重试
                time.sleep(self.poll_interval)

            except Exception:
                # 发生异常，等待后重试
                time.sleep(self.poll_interval)

        # 超时，未能获取锁
        return False

    def release(self):
        """释放锁

        删除锁文件，释放资源。
        如果锁未被当前进程持有，则不执行任何操作。
        """
        if not self._locked:
            return

        try:
            # 检查锁文件是否存在且属于当前进程
            if os.path.exists(self.lock_file):
                try:
                    with open(self.lock_file, 'r') as f:
                        lock_data = json.load(f)
                    # 检查是否由当前进程持有
                    if lock_data.get("process") == os.getpid():
                        os.remove(self.lock_file)
                except (json.JSONDecodeError, KeyError, OSError):
                    # 文件内容无效或读取失败，直接删除
                    try:
                        os.remove(self.lock_file)
                    except OSError:
                        pass
        except OSError:
            # 文件可能已被其他进程删除
            pass
        finally:
            self._locked = False

    def _is_lock_expired(self) -> bool:
        """检查锁是否过期

        读取锁文件，检查锁的创建时间是否已超过超时时间。

        Returns:
            bool: 锁是否已过期
        """
        if not os.path.exists(self.lock_file):
            return False

        try:
            with open(self.lock_file, 'r') as f:
                try:
                    lock_data = json.load(f)
                except json.JSONDecodeError:
                    # 文件内容无效，视为过期
                    return True

            # 检查必需字段
            if "locked_at" not in lock_data or "timeout" not in lock_data:
                return True

            locked_at = float(lock_data["locked_at"])
            lock_timeout = float(lock_data["timeout"])
            current_time = time.time()

            # 检查锁是否过期
            if current_time - locked_at > lock_timeout:
                return True

            # 检查进程是否仍在运行
            if "process" in lock_data:
                try:
                    import psutil
                    pid = int(lock_data["process"])
                    if not psutil.pid_exists(pid):
                        return True
                except (ImportError, ValueError, psutil.NoSuchProcess):
                    # psutil不可用或进程不存在，视为过期
                    return True

            return False

        except (OSError, IOError, ValueError):
            # 文件读取失败或数据无效，视为过期
            return True

    def __enter__(self):
        """上下文管理器入口

        获取锁，如果失败则抛出TimeoutError。

        Returns:
            self: FileLock实例

        Raises:
            TimeoutError: 获取锁超时
        """
        if not self.acquire():
            raise TimeoutError(
                f"Failed to acquire lock for {self.lock_file} within {self.timeout} seconds"
            )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口

        释放锁。
        """
        self.release()

    def __del__(self):
        """析构函数，确保锁被释放"""
        if self._locked:
            try:
                self.release()
            except Exception:
                # 忽略析构函数中的异常
                pass

    @property
    def is_locked(self) -> bool:
        """检查锁是否被当前实例持有

        Returns:
            bool: 是否已获取锁
        """
        return self._locked

    @staticmethod
    def create_task_lock(task_id: str, lock_dir: str = ".", timeout: int = 30) -> "FileLock":
        """
        创建任务锁

        根据任务ID创建锁文件。

        Args:
            task_id: 任务ID
            lock_dir: 锁文件目录
            timeout: 超时时间（秒）

        Returns:
            FileLock实例
        """
        lock_file = os.path.join(lock_dir, f".lock_{task_id}")
        return FileLock(lock_file, timeout=timeout)