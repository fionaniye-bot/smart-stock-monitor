"""安全验证器测试

测试SecurityValidator类的路径验证、文件名清理和任务内容验证功能。
"""

import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

# 导入待测试的模块（稍后创建）
try:
    from src.dashboard.security import SecurityValidator
    from src.dashboard.shared_dirs import SharedDirectoryManager
    from src.dashboard.task_manager import TaskManager
    from src.dashboard.models import DashboardTask
except ImportError:
    # 如果模块不存在，我们将在测试中创建它们
    pass


class TestSecurityValidator:
    """SecurityValidator测试类"""

    def setup_method(self):
        """每个测试方法前的设置"""
        self.validator = SecurityValidator()
        self.test_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """每个测试方法后的清理"""
        import shutil
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_validate_file_path_valid(self):
        """测试有效的文件路径验证"""
        # 创建测试文件
        test_file = os.path.join(self.test_dir, "test.json")
        with open(test_file, "w") as f:
            f.write("{}")

        # 验证有效路径
        result = self.validator.validate_file_path(test_file, self.test_dir)
        assert result is True

    def test_validate_file_path_path_traversal(self):
        """测试路径遍历攻击检测"""
        # 尝试使用../进行路径遍历
        malicious_path = os.path.join(self.test_dir, "../sensitive_file.json")
        result = self.validator.validate_file_path(malicious_path, self.test_dir)
        assert result is False

        # 尝试使用..\进行路径遍历（Windows风格）
        malicious_path2 = os.path.join(self.test_dir, "..\\sensitive_file.json")
        result = self.validator.validate_file_path(malicious_path2, self.test_dir)
        assert result is False

        # 尝试使用绝对路径
        malicious_path3 = "/etc/passwd"
        result = self.validator.validate_file_path(malicious_path3, self.test_dir)
        assert result is False

    def test_validate_file_path_dangerous_extension(self):
        """测试危险文件扩展名检测"""
        # 测试不允许的扩展名
        dangerous_files = [
            "test.exe",
            "test.bat",
            "test.sh",
            "test.php",
            "test.py",
            "test.dll",
            "test.so"
        ]

        for filename in dangerous_files:
            file_path = os.path.join(self.test_dir, filename)
            result = self.validator.validate_file_path(file_path, self.test_dir)
            assert result is False, f"应该拒绝危险扩展名: {filename}"

    def test_validate_file_path_allowed_extension(self):
        """测试允许的文件扩展名"""
        # 测试允许的扩展名
        allowed_files = [
            "test.json",
            "test.yaml",
            "test.yml",
            "test.txt",
            "test.log",
            "data.json",
            "config.yaml"
        ]

        for filename in allowed_files:
            file_path = os.path.join(self.test_dir, filename)
            # 先创建文件
            with open(file_path, "w") as f:
                f.write("{}")
            result = self.validator.validate_file_path(file_path, self.test_dir)
            assert result is True, f"应该允许扩展名: {filename}"

    def test_sanitize_filename_basic(self):
        """测试基本文件名清理"""
        test_cases = [
            ("normal_file.json", "normal_file.json"),
            ("file with spaces.json", "file_with_spaces.json"),
            ("FILE-UPPER.json", "FILE-UPPER.json"),
            ("123_numbers.json", "123_numbers.json"),
        ]

        for input_name, expected in test_cases:
            result = self.validator.sanitize_filename(input_name)
            assert result == expected, f"清理失败: {input_name} -> {result}"

    def test_sanitize_filename_dangerous_chars(self):
        """测试危险字符清理"""
        test_cases = [
            ("file/with/slash.json", "file_with_slash.json"),
            ("file\\with\\backslash.json", "file_with_backslash.json"),
            ("file:with:colon.json", "file_with_colon.json"),
            ("file*with*asterisk.json", "file_with_asterisk.json"),
            ("file?with?question.json", "file_with_question.json"),
            ('file"with"quote.json', "file_with_quote.json"),
            ("file<with>angle.json", "file_with_angle.json"),
            ("file|with|pipe.json", "file_with_pipe.json"),
            ("file;with;semicolon.json", "file_with_semicolon.json"),
        ]

        for input_name, expected in test_cases:
            result = self.validator.sanitize_filename(input_name)
            assert result == expected, f"清理失败: {input_name} -> {result}"

    def test_sanitize_filename_path_traversal(self):
        """测试路径遍历清理"""
        test_cases = [
            ("../evil.json", ".._evil.json"),
            ("../../secret.json", ".._.._secret.json"),
            ("./current.json", "._current.json"),
            ("..\\windows.json", ".._windows.json"),
        ]

        for input_name, expected in test_cases:
            result = self.validator.sanitize_filename(input_name)
            assert result == expected, f"清理失败: {input_name} -> {result}"

    def test_sanitize_filename_length_limit(self):
        """测试文件名长度限制"""
        # 创建超长文件名
        long_name = "a" * 300 + ".json"
        result = self.validator.sanitize_filename(long_name)

        # 检查长度是否被限制
        assert len(result) <= 255, f"文件名过长: {len(result)}"
        assert result.endswith(".json"), "应该保留扩展名"

    def test_validate_task_content_valid(self):
        """测试有效的任务内容验证"""
        valid_tasks = [
            {
                "task_id": "test-123",
                "task_type": "data_filter",
                "status": "pending",
                "user_config": {"stock_symbols": ["AAPL", "GOOGL"]}
            },
            {
                "task_id": "backtest-456",
                "task_type": "strategy_backtest",
                "status": "pending",
                "user_config": {"strategy_name": "moving_average"}
            },
            {
                "task_id": "indicator-789",
                "task_type": "indicator_adjust",
                "status": "pending",
                "user_config": {"indicator_params": {"period": 20}}
            }
        ]

        for task_data in valid_tasks:
            result = self.validator.validate_task_content(task_data)
            assert result is True, f"应该验证有效任务: {task_data}"

    def test_validate_task_content_missing_required(self):
        """测试缺少必需字段的任务内容"""
        invalid_tasks = [
            {},  # 完全空
            {"task_type": "data_filter"},  # 缺少task_id
            {"task_id": "test-123"},  # 缺少task_type
        ]

        for task_data in invalid_tasks:
            result = self.validator.validate_task_content(task_data)
            assert result is False, f"应该拒绝无效任务: {task_data}"

    def test_validate_task_content_invalid_type(self):
        """测试无效任务类型"""
        task_data = {
            "task_id": "test-123",
            "task_type": "invalid_type",  # 无效类型
            "status": "pending"
        }

        result = self.validator.validate_task_content(task_data)
        assert result is False, "应该拒绝无效任务类型"

    def test_validate_task_content_invalid_status(self):
        """测试无效任务状态"""
        task_data = {
            "task_id": "test-123",
            "task_type": "data_filter",
            "status": "invalid_status"  # 无效状态
        }

        result = self.validator.validate_task_content(task_data)
        assert result is False, "应该拒绝无效任务状态"

    def test_validate_task_content_malicious_content(self):
        """测试恶意任务内容"""
        malicious_tasks = [
            {
                "task_id": "../../etc/passwd",  # 路径遍历
                "task_type": "data_filter",
                "status": "pending"
            },
            {
                "task_id": "test'; DROP TABLE users;--",  # SQL注入
                "task_type": "data_filter",
                "status": "pending"
            },
            {
                "task_id": "test-123",
                "task_type": "data_filter",
                "status": "pending",
                "user_config": {
                    "__import__": "os",
                    "system": "rm -rf /"
                }
            }
        ]

        for task_data in malicious_tasks:
            result = self.validator.validate_task_content(task_data)
            assert result is False, f"应该拒绝恶意任务: {task_data}"

    def test_validate_task_content_size_limit(self):
        """测试任务内容大小限制"""
        # 创建超大的用户配置
        huge_config = {"data": "x" * 1000000}  # 1MB数据

        task_data = {
            "task_id": "test-123",
            "task_type": "data_filter",
            "status": "pending",
            "user_config": huge_config
        }

        result = self.validator.validate_task_content(task_data)
        assert result is False, "应该拒绝过大的任务内容"

    def test_validate_task_content_nested_structure(self):
        """测试嵌套结构验证"""
        valid_nested = {
            "task_id": "test-123",
            "task_type": "data_filter",
            "status": "pending",
            "user_config": {
                "stock_symbols": ["AAPL", "GOOGL"],
                "time_range": {"start": "2024-01-01", "end": "2024-12-31"},
                "filter_conditions": {
                    "min_price": 100,
                    "max_volume": 1000000
                }
            },
            "metadata": {
                "created_by": "user123",
                "priority": "high"
            }
        }

        result = self.validator.validate_task_content(valid_nested)
        assert result is True, "应该允许有效的嵌套结构"

    def test_validate_task_content_with_dashboard_task(self):
        """测试与DashboardTask模型的兼容性"""
        # 创建有效的DashboardTask
        task_data = {
            "task_id": "test-123",
            "task_type": "data_filter",
            "status": "pending",
            "user_config": {"stock_symbols": ["AAPL"]},
            "priority": "normal",
            "metadata": {"created_by": "test"}
        }

        # 验证任务内容
        result = self.validator.validate_task_content(task_data)
        assert result is True, "应该验证有效的DashboardTask数据"

        # 尝试从字典创建DashboardTask
        try:
            task = DashboardTask.from_dict(task_data)
            assert task.task_id == "test-123"
            assert task.task_type == "data_filter"
        except Exception as e:
            pytest.fail(f"创建DashboardTask失败: {e}")


class TestSecurityValidatorIntegration:
    """SecurityValidator集成测试"""

    def test_validator_with_shared_dirs(self):
        """测试与SharedDirectoryManager的集成"""
        # 创建临时目录结构
        base_dir = tempfile.mkdtemp()
        tasks_dir = os.path.join(base_dir, "tasks")
        os.makedirs(tasks_dir, exist_ok=True)

        # 创建验证器
        validator = SecurityValidator()

        # 测试有效路径
        valid_path = os.path.join(tasks_dir, "task1.json")
        result = validator.validate_file_path(valid_path, base_dir)
        assert result is True, f"有效路径应该通过验证: {valid_path}"

        # 测试危险扩展名 - 应该被拒绝
        dangerous_path = os.path.join(tasks_dir, "evil.exe")
        result = validator.validate_file_path(dangerous_path, base_dir)
        assert result is False, f"危险扩展名应该被拒绝: {dangerous_path}"

        # 清理
        import shutil
        shutil.rmtree(base_dir)

    def test_sanitize_and_validate_workflow(self):
        """测试清理和验证的完整工作流程"""
        validator = SecurityValidator()

        # 原始文件名（包含危险字符）
        original_name = "file/with/dangerous<script>.json"

        # 步骤1: 清理文件名
        sanitized = validator.sanitize_filename(original_name)
        assert "<" not in sanitized
        assert ">" not in sanitized
        assert "/" not in sanitized
        assert sanitized.endswith(".json")

        # 步骤2: 验证清理后的文件名
        test_dir = tempfile.mkdtemp()
        file_path = os.path.join(test_dir, sanitized)

        # 创建文件
        with open(file_path, "w") as f:
            f.write("test")

        result = validator.validate_file_path(file_path, test_dir)
        assert result is True, "清理后的文件应该通过验证"

        # 清理
        import shutil
        shutil.rmtree(test_dir)


class TestSharedDirectoryManager:
    """SharedDirectoryManager测试类"""

    def setup_method(self):
        """每个测试方法前的设置"""
        self.test_dir = tempfile.mkdtemp()
        self.manager = SharedDirectoryManager(base_path=self.test_dir, create_dirs=True)

    def teardown_method(self):
        """每个测试方法后的清理"""
        import shutil
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_initialization(self):
        """测试初始化"""
        # 检查基础目录
        assert os.path.exists(self.test_dir)
        assert self.manager.base_path == os.path.abspath(self.test_dir)

        # 检查子目录是否创建
        for dir_name in ["tasks", "results", "status", "cache", "locks"]:
            dir_path = self.manager.get_subdir_path(dir_name)
            assert os.path.exists(dir_path), f"子目录不存在: {dir_name}"

    def test_get_subdir_path(self):
        """测试获取子目录路径"""
        # 测试有效的子目录
        for dir_name in ["tasks", "results", "status", "cache", "locks"]:
            path = self.manager.get_subdir_path(dir_name)
            assert os.path.isabs(path)
            assert dir_name in path
            assert os.path.exists(path)

        # 测试无效的子目录
        with pytest.raises(ValueError):
            self.manager.get_subdir_path("invalid_dir")

    def test_get_task_path(self):
        """测试获取任务文件路径"""
        task_id = "test-task-123"

        # 测试默认文件名
        path1 = self.manager.get_task_path(task_id)
        assert path1.endswith(f"{task_id}.json")
        assert "tasks" in path1

        # 测试自定义文件名
        path2 = self.manager.get_task_path(task_id, "custom_config.yaml")
        assert path2.endswith("custom_config.yaml")
        assert "tasks" in path2

        # 测试不安全的任务ID
        malicious_id = "../../etc/passwd"
        safe_path = self.manager.get_task_path(malicious_id)
        # sanitize_filename会将"../"替换为".._"，所以".._"是预期的
        # "etc"和"passwd"本身不是危险词，所以会被保留
        assert ".._" in safe_path or ".." not in safe_path
        # 检查路径是否安全（通过验证器）
        validator = SecurityValidator()
        assert validator.validate_file_path(safe_path, self.test_dir)

    def test_get_status_path(self):
        """测试获取状态文件路径"""
        task_id = "test-task-456"
        path = self.manager.get_status_path(task_id)

        assert path.endswith(f"{task_id}_status.json")
        assert "tasks" in path

    def test_get_result_path(self):
        """测试获取结果文件路径"""
        task_id = "test-task-789"

        # 测试不同类型的结果
        test_cases = [
            ("data", ".csv"),
            ("report", ".pdf"),
            ("config", ".json"),
            ("log", ".log"),
            ("summary", ".txt")
        ]

        for result_type, expected_ext in test_cases:
            path = self.manager.get_result_path(task_id, result_type)
            assert path.endswith(f"{task_id}_{result_type}{expected_ext}")
            assert "results" in path

        # 测试无效的结果类型
        with pytest.raises(ValueError):
            self.manager.get_result_path(task_id, "invalid_type")

    def test_get_cache_path(self):
        """测试获取缓存文件路径"""
        cache_key = "user_preferences_123"

        # 测试默认扩展名
        path1 = self.manager.get_cache_path(cache_key)
        assert path1.endswith(f"{cache_key}.cache")
        assert "cache" in path1

        # 测试自定义扩展名
        path2 = self.manager.get_cache_path(cache_key, ".json")
        assert path2.endswith(f"{cache_key}.json")

        # 测试不带点的扩展名
        path3 = self.manager.get_cache_path(cache_key, "tmp")
        assert path3.endswith(f"{cache_key}.tmp")

    def test_get_lock_path(self):
        """测试获取锁文件路径"""
        lock_name = "task_processing_lock"

        path = self.manager.get_lock_path(lock_name)
        assert path.endswith(f".lock_{lock_name}")
        assert "locks" in path

    def test_validate_and_resolve_path(self):
        """测试验证和解析路径"""
        # 测试有效相对路径
        rel_path = "tasks/test.json"
        abs_path = self.manager.validate_and_resolve_path(rel_path)

        assert os.path.isabs(abs_path)
        # 在Windows上，路径分隔符是反斜杠，所以需要处理
        expected_suffix = rel_path.replace("/", os.path.sep)
        assert abs_path.endswith(expected_suffix)
        assert "tasks" in abs_path

        # 测试路径遍历攻击
        malicious_path = "../sensitive/config.yaml"
        with pytest.raises(ValueError):
            self.manager.validate_and_resolve_path(malicious_path)

        # 测试危险扩展名
        dangerous_path = "tasks/evil.exe"
        with pytest.raises(ValueError):
            self.manager.validate_and_resolve_path(dangerous_path)

    def test_list_files(self):
        """测试列出文件"""
        tasks_dir = self.manager.get_subdir_path("tasks")

        # 创建一些测试文件
        test_files = ["task1.json", "task2.json", "config.yaml", "readme.txt"]
        for filename in test_files:
            file_path = os.path.join(tasks_dir, filename)
            with open(file_path, "w") as f:
                f.write("{}")

        # 列出所有文件
        all_files = self.manager.list_files("tasks")
        assert len(all_files) == 4

        # 列出JSON文件
        json_files = self.manager.list_files("tasks", "*.json")
        assert len(json_files) == 2
        for file_path in json_files:
            assert file_path.endswith(".json")

        # 测试不存在的目录
        with pytest.raises(ValueError):
            self.manager.list_files("invalid_dir")

    def test_cleanup_old_files(self):
        """测试清理旧文件"""
        import time
        tasks_dir = self.manager.get_subdir_path("tasks")

        # 创建新旧文件
        old_file = os.path.join(tasks_dir, "old_task.json")
        new_file = os.path.join(tasks_dir, "new_task.json")

        with open(old_file, "w") as f:
            f.write("{}")
        with open(new_file, "w") as f:
            f.write("{}")

        # 修改旧文件的时间戳（设置为10天前）
        ten_days_ago = time.time() - (10 * 24 * 3600)
        os.utime(old_file, (ten_days_ago, ten_days_ago))

        # 清理7天前的文件
        cleaned = self.manager.cleanup_old_files("tasks", max_age_days=7)
        assert cleaned == 1

        # 检查文件是否被删除
        assert not os.path.exists(old_file)
        assert os.path.exists(new_file)

    def test_get_directory_info(self):
        """测试获取目录信息"""
        info = self.manager.get_directory_info()

        assert "base_path" in info
        assert info["base_path"] == self.manager.base_path

        assert "subdirectories" in info
        assert "total_size" in info

        # 检查所有子目录都在信息中
        for dir_name in ["tasks", "results", "status", "cache", "locks"]:
            assert dir_name in info["subdirectories"]
            dir_info = info["subdirectories"][dir_name]
            assert "path" in dir_info
            assert "size_bytes" in dir_info
            assert "file_count" in dir_info

    def test_security_integration(self):
        """测试安全集成"""
        # 测试通过管理器创建的文件路径都是安全的
        task_id = "normal_task"
        task_path = self.manager.get_task_path(task_id)

        # 验证路径
        validator = SecurityValidator()
        assert validator.validate_file_path(task_path, self.test_dir)

        # 尝试创建不安全路径
        unsafe_id = "../../../etc/passwd"
        safe_path = self.manager.get_task_path(unsafe_id)
        assert validator.validate_file_path(safe_path, self.test_dir)

        # 测试危险扩展名会被拒绝
        dangerous_extensions = [".exe", ".bat", ".sh", ".php"]
        for ext in dangerous_extensions:
            with pytest.raises(ValueError):
                self.manager.validate_and_resolve_path(f"tasks/test{ext}")


class TestTaskManager:
    """TaskManager测试类"""

    def setup_method(self):
        """每个测试方法前的设置"""
        self.test_dir = tempfile.mkdtemp()
        self.manager = TaskManager(base_path=self.test_dir)

    def teardown_method(self):
        """每个测试方法后的清理"""
        import shutil
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_initialization(self):
        """测试初始化"""
        assert os.path.exists(self.test_dir)
        assert self.manager.base_path == os.path.abspath(self.test_dir)

        # 检查目录是否创建
        for dir_name in ["tasks", "results", "status", "cache", "locks"]:
            dir_path = os.path.join(self.test_dir, dir_name)
            assert os.path.exists(dir_path), f"目录不存在: {dir_name}"

    def test_create_task_valid(self):
        """测试创建有效任务"""
        user_config = {
            "stock_symbols": ["AAPL", "GOOGL"],
            "time_range": {"start": "2024-01-01", "end": "2024-12-31"}
        }

        # 创建数据筛选任务
        task = self.manager.create_task(
            task_type="data_filter",
            user_config=user_config,
            priority="normal"
        )

        assert task is not None
        assert task.task_type == "data_filter"
        assert task.status == "pending"
        assert task.priority == "normal"
        assert "task_" in task.task_id

        # 验证任务文件存在
        task_file = os.path.join(self.test_dir, "tasks", f"{task.task_id}.json")
        assert os.path.exists(task_file)

        # 验证状态文件存在
        status_file = os.path.join(self.test_dir, "tasks", f"{task.task_id}_status.json")
        assert os.path.exists(status_file)

    def test_create_task_invalid_type(self):
        """测试创建无效任务类型"""
        user_config = {"test": "data"}

        with pytest.raises(ValueError):
            self.manager.create_task(
                task_type="invalid_type",
                user_config=user_config
            )

    def test_create_task_invalid_priority(self):
        """测试创建无效优先级"""
        user_config = {"test": "data"}

        with pytest.raises(ValueError):
            self.manager.create_task(
                task_type="data_filter",
                user_config=user_config,
                priority="invalid_priority"
            )

    def test_create_task_malicious_config(self):
        """测试创建恶意配置的任务"""
        malicious_config = {
            "__import__": "os",
            "system": "rm -rf /"
        }

        with pytest.raises(ValueError):
            self.manager.create_task(
                task_type="data_filter",
                user_config=malicious_config
            )

    def test_create_task_with_custom_id(self):
        """测试使用自定义ID创建任务"""
        custom_id = "custom_task_123"
        user_config = {"test": "data"}

        task = self.manager.create_task(
            task_type="data_filter",
            user_config=user_config,
            task_id=custom_id
        )

        assert task.task_id == custom_id

        # 验证文件使用自定义ID
        task_file = os.path.join(self.test_dir, "tasks", f"{custom_id}.json")
        assert os.path.exists(task_file)

    def test_get_task(self):
        """测试获取任务"""
        # 先创建任务
        user_config = {"test": "data"}
        task = self.manager.create_task(
            task_type="data_filter",
            user_config=user_config
        )

        # 获取任务
        retrieved_task = self.manager.get_task(task.task_id)

        assert retrieved_task is not None
        assert retrieved_task.task_id == task.task_id
        assert retrieved_task.task_type == task.task_type
        assert retrieved_task.status == task.status

    def test_get_nonexistent_task(self):
        """测试获取不存在的任务"""
        task = self.manager.get_task("nonexistent_task_123")
        assert task is None

    def test_update_task_status(self):
        """测试更新任务状态"""
        # 创建任务
        user_config = {"test": "data"}
        task = self.manager.create_task(
            task_type="data_filter",
            user_config=user_config
        )

        # 更新状态为处理中
        result = self.manager.update_task_status(
            task_id=task.task_id,
            status="processing",
            progress_percent=25
        )

        assert result is True

        # 验证状态更新
        task = self.manager.get_task(task.task_id)
        assert task.status == "processing"

        # 验证状态文件
        status = self.manager.get_task_status(task.task_id)
        assert status is not None
        assert status.current_status == "processing"
        assert status.progress_percent == 25

    def test_update_task_status_invalid(self):
        """测试更新无效状态"""
        # 创建任务
        user_config = {"test": "data"}
        task = self.manager.create_task(
            task_type="data_filter",
            user_config=user_config
        )

        # 尝试更新为无效状态
        result = self.manager.update_task_status(
            task_id=task.task_id,
            status="invalid_status"
        )

        assert result is False

    def test_get_task_status(self):
        """测试获取任务状态"""
        # 创建任务
        user_config = {"test": "data"}
        task = self.manager.create_task(
            task_type="data_filter",
            user_config=user_config
        )

        # 获取状态
        status = self.manager.get_task_status(task.task_id)

        assert status is not None
        assert status.task_id == task.task_id
        assert status.current_status == "pending"
        assert status.progress_percent == 0

    def test_list_tasks(self):
        """测试列出任务"""
        # 创建多个任务
        for i in range(3):
            user_config = {"index": i}
            self.manager.create_task(
                task_type="data_filter",
                user_config=user_config,
                priority="normal" if i % 2 == 0 else "high"
            )

        # 列出所有任务
        tasks = self.manager.list_tasks()
        assert len(tasks) == 3

        # 列出特定状态的任务
        pending_tasks = self.manager.list_tasks(status_filter="pending")
        assert len(pending_tasks) == 3

        # 更新一个任务状态
        if tasks:
            task_id = tasks[0]["task_id"]
            self.manager.update_task_status(task_id, "completed")

            # 列出已完成任务
            completed_tasks = self.manager.list_tasks(status_filter="completed")
            assert len(completed_tasks) == 1

    def test_delete_task(self):
        """测试删除任务"""
        # 创建任务
        user_config = {"test": "data"}
        task = self.manager.create_task(
            task_type="data_filter",
            user_config=user_config
        )

        # 验证任务存在
        assert self.manager.get_task(task.task_id) is not None

        # 删除任务
        result = self.manager.delete_task(task.task_id)
        assert result is True

        # 验证任务已删除
        assert self.manager.get_task(task.task_id) is None

    def test_delete_nonexistent_task(self):
        """测试删除不存在的任务"""
        result = self.manager.delete_task("nonexistent_task_123")
        assert result is False

    def test_cleanup_old_tasks(self):
        """测试清理旧任务"""
        # 这个测试比较复杂，因为需要模拟旧任务
        # 这里只测试函数调用不报错
        cleaned = self.manager.cleanup_old_tasks(max_age_days=0)
        assert isinstance(cleaned, int)
        assert cleaned >= 0

    def test_validate_task_file(self):
        """测试验证任务文件"""
        # 创建有效任务
        user_config = {"test": "data"}
        task = self.manager.create_task(
            task_type="data_filter",
            user_config=user_config
        )

        # 获取任务文件路径
        task_file = os.path.join(self.test_dir, "tasks", f"{task.task_id}.json")

        # 验证有效文件
        result = self.manager.validate_task_file(task_file)
        assert result is True

        # 验证无效文件
        invalid_file = os.path.join(self.test_dir, "invalid.json")
        with open(invalid_file, "w") as f:
            f.write("not valid json")

        result = self.manager.validate_task_file(invalid_file)
        assert result is False

    def test_security_integration(self):
        """测试安全集成"""
        # 测试恶意任务ID会被清理而不是拒绝
        malicious_id = "../../etc/passwd"

        # 尝试使用恶意ID创建任务，ID会被清理
        user_config = {"test": "data"}

        task = self.manager.create_task(
            task_type="data_filter",
            user_config=user_config,
            task_id=malicious_id
        )

        # 验证ID被清理
        assert ".." not in task.task_id or ".._" in task.task_id
        assert "etc" in task.task_id  # "etc"本身不是危险词

        # 验证文件路径安全
        task_file = os.path.join(self.test_dir, "tasks", f"{task.task_id}.json")
        validator = SecurityValidator()
        assert validator.validate_file_path(task_file, self.test_dir)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])