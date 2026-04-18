#!/usr/bin/env python3
"""
文件锁机制演示

演示如何使用FileLock类防止并发处理导致的竞态条件
"""
import os
import time
import tempfile
import threading
from src.dashboard.file_lock import FileLock


def worker(worker_id: int, lock_file: str, results: list):
    """工作线程函数"""
    print(f"Worker {worker_id}: 尝试获取锁...")

    lock = FileLock(lock_file, timeout=5, poll_interval=0.1)

    try:
        with lock:
            print(f"Worker {worker_id}: 成功获取锁，开始处理...")
            # 模拟处理时间
            time.sleep(2)
            results.append(worker_id)
            print(f"Worker {worker_id}: 处理完成，释放锁")
    except TimeoutError:
        print(f"Worker {worker_id}: 获取锁超时")


def demo_basic_lock():
    """基本锁演示"""
    print("=" * 50)
    print("基本文件锁演示")
    print("=" * 50)

    with tempfile.TemporaryDirectory() as tmpdir:
        lock_file = os.path.join(tmpdir, ".lock_demo")

        # 创建锁
        lock = FileLock(lock_file, timeout=3)

        # 获取锁
        print("1. 获取锁...")
        acquired = lock.acquire()
        print(f"   获取结果: {acquired}")

        # 尝试再次获取（应该失败）
        print("2. 尝试再次获取锁...")
        lock2 = FileLock(lock_file, timeout=1)
        acquired2 = lock2.acquire()
        print(f"   获取结果: {acquired2} (应该为False)")

        # 释放锁
        print("3. 释放锁...")
        lock.release()

        # 再次获取（应该成功）
        print("4. 释放后再次获取锁...")
        lock3 = FileLock(lock_file, timeout=1)
        acquired3 = lock3.acquire()
        print(f"   获取结果: {acquired3} (应该为True)")
        lock3.release()

        print("\n基本锁演示完成 [OK]")


def demo_context_manager():
    """上下文管理器演示"""
    print("\n" + "=" * 50)
    print("上下文管理器演示")
    print("=" * 50)

    with tempfile.TemporaryDirectory() as tmpdir:
        lock_file = os.path.join(tmpdir, ".lock_context")

        print("使用with语句获取锁...")
        try:
            with FileLock(lock_file, timeout=2) as lock:
                print("   在with块内，锁已获取")
                print(f"   锁状态: {lock.is_locked}")
                # 模拟工作
                time.sleep(1)
            print("   退出with块，锁已自动释放")
            print(f"   锁状态: {lock.is_locked}")
        except TimeoutError as e:
            print(f"   错误: {e}")

        print("\n上下文管理器演示完成 [OK]")


def demo_concurrent_access():
    """并发访问演示"""
    print("\n" + "=" * 50)
    print("并发访问演示")
    print("=" * 50)

    with tempfile.TemporaryDirectory() as tmpdir:
        lock_file = os.path.join(tmpdir, ".lock_concurrent")
        results = []

        print("启动5个工作线程并发访问...")
        threads = []
        for i in range(5):
            t = threading.Thread(target=worker, args=(i, lock_file, results))
            threads.append(t)
            t.start()

        # 等待所有线程完成
        for t in threads:
            t.join()

        print(f"\n处理完成的工作线程: {results}")
        print("注意：只有一个线程能同时获取锁")

        print("\n并发访问演示完成 [OK]")


def demo_task_lock():
    """任务锁演示"""
    print("\n" + "=" * 50)
    print("任务锁演示")
    print("=" * 50)

    with tempfile.TemporaryDirectory() as tmpdir:
        task_ids = ["task_001", "task_002", "task_003"]

        print("为不同任务创建锁...")
        locks = []
        for task_id in task_ids:
            lock = FileLock.create_task_lock(
                task_id=task_id,
                lock_dir=tmpdir,
                timeout=10
            )
            locks.append(lock)
            print(f"   创建任务锁: {task_id} -> {lock.lock_file}")

        print("\n获取任务锁...")
        for i, lock in enumerate(locks):
            if lock.acquire():
                print(f"   成功获取任务锁: {task_ids[i]}")
                # 模拟处理
                time.sleep(0.5)
                lock.release()
                print(f"   释放任务锁: {task_ids[i]}")
            else:
                print(f"   获取任务锁失败: {task_ids[i]}")

        print("\n任务锁演示完成 [OK]")


def demo_lock_expiration():
    """锁过期演示"""
    print("\n" + "=" * 50)
    print("锁过期演示")
    print("=" * 50)

    with tempfile.TemporaryDirectory() as tmpdir:
        lock_file = os.path.join(tmpdir, ".lock_expired")

        print("1. 创建过期锁文件...")
        import json
        lock_data = {
            "locked_at": time.time() - 20,  # 20秒前
            "timeout": 5,  # 5秒超时
            "process": os.getpid()
        }
        with open(lock_file, 'w') as f:
            json.dump(lock_data, f)

        print("2. 尝试获取锁（应该成功，因为锁已过期）...")
        lock = FileLock(lock_file, timeout=2)
        acquired = lock.acquire()
        print(f"   获取结果: {acquired} (应该为True)")

        if acquired:
            lock.release()

        print("\n锁过期演示完成 [OK]")


def main():
    """主函数"""
    print("文件锁机制演示")
    print("=" * 50)

    try:
        demo_basic_lock()
        demo_context_manager()
        demo_concurrent_access()
        demo_task_lock()
        demo_lock_expiration()

        print("\n" + "=" * 50)
        print("所有演示完成！")
        print("=" * 50)

    except Exception as e:
        print(f"\n演示过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()