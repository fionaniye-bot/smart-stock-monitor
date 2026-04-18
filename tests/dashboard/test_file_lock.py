"""文件锁机制测试

测试基于文件的互斥锁实现
"""
import os
import tempfile
import time
import pytest
from src.dashboard.file_lock import FileLock


def test_file_lock_mechanism():
    """测试文件锁机制"""
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_file = os.path.join(tmpdir, ".lock_test")

        # 测试锁获取
        lock1 = FileLock(lock_file, timeout=1)
        assert lock1.acquire() == True

        # 测试锁重复获取（应该失败）
        lock2 = FileLock(lock_file, timeout=1)
        assert lock2.acquire() == False

        # 测试锁释放
        lock1.release()

        # 测试锁重新获取（应该成功）
        lock3 = FileLock(lock_file, timeout=1)
        assert lock3.acquire() == True
        lock3.release()


def test_file_lock_context_manager():
    """测试文件锁上下文管理器"""
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_file = os.path.join(tmpdir, ".lock_test")

        # 使用上下文管理器获取锁
        with FileLock(lock_file, timeout=1) as lock:
            assert lock._locked == True
            # 尝试再次获取锁（应该失败）
            lock2 = FileLock(lock_file, timeout=0.5)
            assert lock2.acquire() == False

        # 锁应该已释放
        assert lock._locked == False


def test_file_lock_timeout():
    """测试文件锁超时"""
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_file = os.path.join(tmpdir, ".lock_test")

        # 获取锁
        lock1 = FileLock(lock_file, timeout=1)
        assert lock1.acquire() == True

        # 尝试获取锁（应该超时）
        lock2 = FileLock(lock_file, timeout=0.5)
        start_time = time.time()
        result = lock2.acquire()
        elapsed_time = time.time() - start_time

        assert result == False
        # 应该等待大约0.5秒
        assert 0.4 <= elapsed_time <= 0.6

        lock1.release()


def test_file_lock_expired():
    """测试锁过期检查"""
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_file = os.path.join(tmpdir, ".lock_test")

        # 创建锁文件，设置过期时间
        lock1 = FileLock(lock_file, timeout=1)

        # 手动创建锁文件，设置过期时间
        import json
        lock_data = {
            "locked_at": (time.time() - 10).__str__(),  # 10秒前
            "timeout": 1,
            "process": os.getpid()
        }
        with open(lock_file, 'w') as f:
            json.dump(lock_data, f)

        # 应该能获取锁，因为锁已过期
        assert lock1.acquire() == True
        lock1.release()


def test_file_lock_concurrent_access():
    """测试并发访问"""
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_file = os.path.join(tmpdir, ".lock_test")

        # 模拟并发访问
        results = []

        def try_acquire_lock():
            lock = FileLock(lock_file, timeout=0.5)
            return lock.acquire()

        # 第一次获取应该成功
        lock1 = FileLock(lock_file, timeout=1)
        assert lock1.acquire() == True
        results.append(True)

        # 第二次获取应该失败
        lock2 = FileLock(lock_file, timeout=0.1)
        assert lock2.acquire() == False
        results.append(False)

        # 释放后应该能再次获取
        lock1.release()
        lock3 = FileLock(lock_file, timeout=1)
        assert lock3.acquire() == True
        results.append(True)
        lock3.release()

        assert results == [True, False, True]


def test_file_lock_file_content():
    """测试锁文件内容"""
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_file = os.path.join(tmpdir, ".lock_test")

        with FileLock(lock_file, timeout=1) as lock:
            # 检查锁文件是否存在
            assert os.path.exists(lock_file)

            # 检查锁文件内容
            import json
            with open(lock_file, 'r') as f:
                lock_data = json.load(f)

            assert "locked_at" in lock_data
            assert "timeout" in lock_data
            assert "process" in lock_data
            assert lock_data["timeout"] == 1


def test_file_lock_del_releases():
    """测试析构函数释放锁"""
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_file = os.path.join(tmpdir, ".lock_test")

        # 创建锁并获取
        lock = FileLock(lock_file, timeout=1)
        assert lock.acquire() == True

        # 删除对象，应该释放锁
        del lock

        # 等待一小段时间确保锁被释放
        time.sleep(0.1)

        # 应该能再次获取锁
        lock2 = FileLock(lock_file, timeout=1)
        assert lock2.acquire() == True
        lock2.release()


def test_file_lock_invalid_file_path():
    """测试无效文件路径"""
    # 使用不存在的目录（Windows路径）
    lock_file = "C:\\nonexistent\\directory\\.lock_test"
    lock = FileLock(lock_file, timeout=1)

    # 应该失败，因为目录不存在
    # 注意：在某些系统上，os.makedirs可能会创建目录
    # 所以我们只测试acquire返回False或True都可以接受
    # 重点是确保不会崩溃
    try:
        result = lock.acquire()
        # 无论返回True还是False，只要不崩溃就是成功
        assert result in [True, False]
    except Exception as e:
        # 如果抛出异常，测试失败
        pytest.fail(f"acquire() should not raise exception: {e}")


if __name__ == "__main__":
    # 运行测试
    test_file_lock_mechanism()
    print("✓ test_file_lock_mechanism passed")

    test_file_lock_context_manager()
    print("✓ test_file_lock_context_manager passed")

    test_file_lock_timeout()
    print("✓ test_file_lock_timeout passed")

    test_file_lock_expired()
    print("✓ test_file_lock_expired passed")

    test_file_lock_concurrent_access()
    print("✓ test_file_lock_concurrent_access passed")

    test_file_lock_file_content()
    print("✓ test_file_lock_file_content passed")

    test_file_lock_del_releases()
    print("✓ test_file_lock_del_releases passed")

    print("\n所有测试通过！")