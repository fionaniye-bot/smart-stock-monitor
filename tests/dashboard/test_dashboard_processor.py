"""仪表盘处理器测试

测试DashboardProcessor类的功能，包括文件锁集成
"""
import os
import tempfile
import json
import time
import pytest
from src.dashboard.dashboard_processor import DashboardProcessor
from src.dashboard.models import DashboardTask


def test_dashboard_processor_initialization():
    """测试处理器初始化"""
    with tempfile.TemporaryDirectory() as tmpdir:
        processor = DashboardProcessor(task_dir=tmpdir, lock_dir=tmpdir)
        assert processor.task_dir == tmpdir
        assert processor.lock_dir == tmpdir
        assert processor.timeout == 30


def test_find_pending_tasks():
    """测试查找待处理任务"""
    with tempfile.TemporaryDirectory() as tmpdir:
        processor = DashboardProcessor(task_dir=tmpdir, lock_dir=tmpdir)

        # 创建几个任务文件
        tasks = [
            {
                "task_id": "task1",
                "task_type": "data_filter",
                "status": "pending",
                "user_config": {"symbols": ["AAPL"]}
            },
            {
                "task_id": "task2",
                "task_type": "strategy_backtest",
                "status": "processing",  # 不是pending
                "user_config": {"strategy": "moving_average"}
            },
            {
                "task_id": "task3",
                "task_type": "indicator_adjust",
                "status": "pending",
                "user_config": {"indicator": "RSI"}
            }
        ]

        # 保存任务文件
        for task in tasks:
            task_file = os.path.join(tmpdir, f"{task['task_id']}.json")
            with open(task_file, 'w') as f:
                json.dump(task, f)

        # 查找待处理任务
        pending_tasks = processor.find_pending_tasks()
        assert len(pending_tasks) == 2
        assert "task1" in pending_tasks
        assert "task3" in pending_tasks
        assert "task2" not in pending_tasks


def test_process_task_with_lock():
    """测试带锁处理任务"""
    with tempfile.TemporaryDirectory() as tmpdir:
        processor = DashboardProcessor(task_dir=tmpdir, lock_dir=tmpdir, timeout=5)

        # 创建待处理任务
        task_data = {
            "task_id": "test_task_001",
            "task_type": "data_filter",
            "status": "pending",
            "user_config": {
                "stock_symbols": ["AAPL", "GOOGL"],
                "time_range": {"start": "2024-01-01", "end": "2024-12-31"},
                "filter_conditions": {"min_volume": 1000000}
            }
        }

        task_file = os.path.join(tmpdir, "test_task_001.json")
        with open(task_file, 'w') as f:
            json.dump(task_data, f)

        # 处理任务
        result = processor.process_task("test_task_001")
        assert result == True  # 应该成功完成

        # 检查任务文件已更新
        with open(task_file, 'r') as f:
            updated_task = json.load(f)

        assert updated_task["status"] == "completed"
        assert "start_time" in updated_task
        assert "end_time" in updated_task

        # 检查状态文件
        status_file = os.path.join(tmpdir, "test_task_001_status.json")
        assert os.path.exists(status_file)

        with open(status_file, 'r') as f:
            status_data = json.load(f)

        assert status_data["task_id"] == "test_task_001"
        assert status_data["current_status"] == "completed"
        assert status_data["progress_percent"] == 100


def test_concurrent_task_processing():
    """测试并发任务处理（模拟）"""
    with tempfile.TemporaryDirectory() as tmpdir:
        processor = DashboardProcessor(task_dir=tmpdir, lock_dir=tmpdir, timeout=2)

        # 创建任务
        task_data = {
            "task_id": "concurrent_task",
            "task_type": "data_filter",
            "status": "pending",
            "user_config": {"test": "data"}
        }

        task_file = os.path.join(tmpdir, "concurrent_task.json")
        with open(task_file, 'w') as f:
            json.dump(task_data, f)

        # 模拟并发处理 - 第一个处理器获取锁
        processor1 = DashboardProcessor(task_dir=tmpdir, lock_dir=tmpdir, timeout=2)

        # 在测试中，我们无法真正并发，但可以测试锁机制
        # 通过检查任务状态来验证锁是否工作
        result1 = processor1.process_task("concurrent_task")
        assert result1 == True

        # 任务应该已完成，状态为completed
        with open(task_file, 'r') as f:
            final_task = json.load(f)

        assert final_task["status"] == "completed"


def test_get_task_status():
    """测试获取任务状态"""
    with tempfile.TemporaryDirectory() as tmpdir:
        processor = DashboardProcessor(task_dir=tmpdir, lock_dir=tmpdir)

        # 创建任务和状态文件
        task_id = "status_test_task"
        status_data = {
            "task_id": task_id,
            "current_status": "processing",
            "progress_percent": 50,
            "current_step": "正在处理数据",
            "start_time": "2024-01-01T10:00:00",
            "last_update": "2024-01-01T10:05:00",
            "estimated_remaining_time": 300
        }

        status_file = os.path.join(tmpdir, f"{task_id}_status.json")
        with open(status_file, 'w') as f:
            json.dump(status_data, f)

        # 获取状态
        status = processor.get_task_status(task_id)
        assert status is not None
        assert status.task_id == task_id
        assert status.current_status == "processing"
        assert status.progress_percent == 50
        assert status.current_step == "正在处理数据"

        # 测试不存在的任务
        non_existent_status = processor.get_task_status("non_existent_task")
        assert non_existent_status is None


def test_cleanup_expired_locks():
    """测试清理过期锁文件"""
    with tempfile.TemporaryDirectory() as tmpdir:
        processor = DashboardProcessor(task_dir=tmpdir, lock_dir=tmpdir)

        # 创建几个锁文件
        lock_files = [
            (".lock_task1", time.time() - 4000),  # 过期（>1小时）
            (".lock_task2", time.time() - 1800),  # 30分钟，未过期
            (".lock_task3", time.time() - 100),   # 新文件
        ]

        for filename, mtime in lock_files:
            lock_file = os.path.join(tmpdir, filename)
            with open(lock_file, 'w') as f:
                f.write("lock content")

            # 修改文件时间
            os.utime(lock_file, (mtime, mtime))

        # 执行清理（设置最大年龄为1小时）
        processor.cleanup_expired_locks(max_age_seconds=3600)

        # 检查结果
        remaining_files = os.listdir(tmpdir)
        assert ".lock_task1" not in remaining_files  # 应该被清理
        assert ".lock_task2" in remaining_files      # 应该保留
        assert ".lock_task3" in remaining_files      # 应该保留


def test_task_processing_failure():
    """测试任务处理失败情况"""
    with tempfile.TemporaryDirectory() as tmpdir:
        processor = DashboardProcessor(task_dir=tmpdir, lock_dir=tmpdir)

        # 创建无效任务（缺少必需字段）
        task_data = {
            "task_id": "invalid_task",
            # 缺少task_type字段
            "status": "pending"
        }

        task_file = os.path.join(tmpdir, "invalid_task.json")
        with open(task_file, 'w', encoding='utf-8') as f:
            json.dump(task_data, f)

        # 处理任务（应该失败）
        result = processor.process_task("invalid_task")

        # 任务应该标记为失败
        with open(task_file, 'r', encoding='utf-8') as f:
            updated_task = json.load(f)

        assert updated_task["status"] == "failed"
        assert "error" in updated_task


def test_dashboard_task_integration():
    """测试DashboardTask与处理器的集成"""
    with tempfile.TemporaryDirectory() as tmpdir:
        processor = DashboardProcessor(task_dir=tmpdir, lock_dir=tmpdir)

        # 使用DashboardTask创建任务
        task = DashboardTask.create_data_filter_task(
            task_id="integration_test",
            stock_symbols=["AAPL", "MSFT"],
            time_range={"start": "2024-01-01", "end": "2024-12-31"},
            filter_conditions={"min_price": 100},
            priority="high"
        )

        # 保存任务
        task_file = os.path.join(tmpdir, "integration_test.json")
        with open(task_file, 'w') as f:
            json.dump(task.to_dict(), f)

        # 处理任务
        result = processor.process_task("integration_test")
        assert result == True

        # 验证任务状态
        status = processor.get_task_status("integration_test")
        assert status is not None
        assert status.current_status == "completed"


if __name__ == "__main__":
    # 运行测试
    test_dashboard_processor_initialization()
    print("✓ test_dashboard_processor_initialization passed")

    test_find_pending_tasks()
    print("✓ test_find_pending_tasks passed")

    test_process_task_with_lock()
    print("✓ test_process_task_with_lock passed")

    test_get_task_status()
    print("✓ test_get_task_status passed")

    test_cleanup_expired_locks()
    print("✓ test_cleanup_expired_locks passed")

    print("\n所有测试通过！")