"""安全验证器

实现路径验证、文件名清理和任务内容验证功能，防止安全攻击。
"""

import os
import re
import json
from typing import Dict, Any, Optional, List
from pathlib import Path

# 导入模型中的验证函数
from .models import validate_task_type, validate_task_status, VALID_TASK_TYPES, VALID_TASK_STATUSES


class SecurityValidator:
    """安全验证器类

    提供文件路径验证、文件名清理和任务内容验证功能。
    防止路径遍历攻击、恶意文件扩展名和危险内容。
    """

    # 允许的文件扩展名（白名单）
    ALLOWED_EXTENSIONS = {
        '.json', '.yaml', '.yml', '.txt', '.log', '.csv',
        '.pdf', '.cache', '.lock', '.tmp', '.dat'
    }

    # 危险文件扩展名（黑名单）
    DANGEROUS_EXTENSIONS = {
        '.exe', '.bat', '.cmd', '.sh', '.bash', '.ps1',  # 可执行文件
        '.dll', '.so', '.dylib',  # 动态库
        '.php', '.py', '.rb', '.pl', '.js',  # 脚本文件
        '.jar', '.war', '.ear',  # Java归档
        '.vbs', '.vbe', '.wsf',  # Windows脚本
        '.scr', '.pif', '.com',  # 其他可执行文件
    }

    # 路径遍历模式
    PATH_TRAVERSAL_PATTERNS = [
        r'\.\./',  # Unix风格
        r'\.\.\\',  # Windows风格
        r'\./',  # 当前目录
        r'\.\\',  # 当前目录（Windows）
    ]

    # 危险字符模式（用于文件名清理）
    DANGEROUS_CHARS_PATTERN = r'[<>:"/\\|?*;\s]'  # 包含空格

    # 恶意内容模式
    MALICIOUS_PATTERNS = [
        r'<\s*script\b',  # 脚本标签
        r'javascript:',  # JavaScript协议
        r'on\w+\s*=',  # 事件处理器
        r'eval\s*\(',  # eval函数
        r'document\.',  # document对象
        r'window\.',  # window对象
        r'alert\s*\(',  # alert函数
        r'prompt\s*\(',  # prompt函数
        r'confirm\s*\(',  # confirm函数
        r'<\s*iframe',  # iframe标签
        r'<\s*object',  # object标签
        r'<\s*embed',  # embed标签
        r'<\s*applet',  # applet标签
        r'\.\./',  # 路径遍历
        r'\.\.\\',  # 路径遍历（Windows）
        r'DROP\s+TABLE',  # SQL注入
        r'DELETE\s+FROM',  # SQL注入
        r'INSERT\s+INTO',  # SQL注入
        r'UPDATE\s+\w+\s+SET',  # SQL注入
        r'SELECT\s+\*',  # SQL注入
        r'UNION\s+SELECT',  # SQL注入
        r'__import__',  # Python危险函数
        r'os\.system',  # 系统命令执行
        r'subprocess\.',  # 子进程执行
        r'exec\s*\(',  # exec函数
        r'compile\s*\(',  # compile函数
    ]

    # 任务内容大小限制（字节）
    MAX_TASK_CONTENT_SIZE = 1024 * 1024  # 1MB

    def __init__(self):
        """初始化安全验证器"""
        # 编译正则表达式以提高性能
        self.path_traversal_regex = re.compile('|'.join(self.PATH_TRAVERSAL_PATTERNS))
        self.dangerous_chars_regex = re.compile(self.DANGEROUS_CHARS_PATTERN)
        self.malicious_regex = re.compile('|'.join(self.MALICIOUS_PATTERNS), re.IGNORECASE)

    def validate_file_path(self, file_path: str, base_directory: str) -> bool:
        """验证文件路径是否安全

        Args:
            file_path: 要验证的文件路径
            base_directory: 基础目录，文件必须在此目录内

        Returns:
            bool: 如果路径安全则返回True，否则返回False
        """
        try:
            # 转换为绝对路径
            abs_file_path = os.path.abspath(file_path)
            abs_base_dir = os.path.abspath(base_directory)

            # 检查路径遍历
            if self._contains_path_traversal(abs_file_path):
                return False

            # 检查文件是否在基础目录内
            if not abs_file_path.startswith(abs_base_dir):
                return False

            # 检查文件扩展名
            if not self._is_allowed_extension(abs_file_path):
                return False

            # 检查文件名是否包含危险字符
            filename = os.path.basename(abs_file_path)
            if self.dangerous_chars_regex.search(filename):
                return False

            return True

        except Exception:
            # 任何异常都视为不安全
            return False

    def sanitize_filename(self, filename: str) -> str:
        """清理文件名，移除不安全字符

        Args:
            filename: 原始文件名

        Returns:
            str: 清理后的安全文件名
        """
        if not filename:
            return "unnamed"

        # 移除路径分隔符和危险字符
        sanitized = self.dangerous_chars_regex.sub('_', filename)

        # 处理路径遍历模式
        sanitized = self.path_traversal_regex.sub('_', sanitized)

        # 移除控制字符和非打印字符
        sanitized = ''.join(char for char in sanitized if ord(char) >= 32 and ord(char) != 127)

        # 限制长度（保留扩展名）
        name, ext = os.path.splitext(sanitized)
        if len(name) > 200:  # 限制基本名称长度
            name = name[:200]

        # 重新组合
        sanitized = name + ext

        # 确保不是空文件名
        if not sanitized.strip('._'):
            sanitized = "sanitized_file"

        return sanitized

    def validate_task_content(self, task_data: Dict[str, Any]) -> bool:
        """验证任务数据内容是否安全

        Args:
            task_data: 任务数据字典

        Returns:
            bool: 如果任务内容安全则返回True，否则返回False
        """
        try:
            # 检查必需字段
            required_fields = ['task_id', 'task_type']
            for field in required_fields:
                if field not in task_data:
                    return False

            # 验证任务ID
            task_id = task_data['task_id']
            if not isinstance(task_id, str) or not task_id.strip():
                return False

            # 检查任务ID是否包含恶意内容
            if self._contains_malicious_content(task_id):
                return False

            # 验证任务类型
            task_type = task_data['task_type']
            if not validate_task_type(task_type):
                return False

            # 验证任务状态（如果存在）
            status = task_data.get('status', 'pending')
            if not validate_task_status(status):
                return False

            # 验证用户配置（如果存在）
            user_config = task_data.get('user_config', {})
            if not self._validate_user_config(user_config):
                return False

            # 检查任务数据大小
            if self._is_content_too_large(task_data):
                return False

            # 检查整个任务数据是否包含恶意内容
            task_json = json.dumps(task_data)
            if self._contains_malicious_content(task_json):
                return False

            return True

        except Exception:
            # 任何异常都视为不安全
            return False

    def _contains_path_traversal(self, path: str) -> bool:
        """检查路径是否包含路径遍历模式"""
        return bool(self.path_traversal_regex.search(path))

    def _is_allowed_extension(self, file_path: str) -> bool:
        """检查文件扩展名是否允许"""
        ext = os.path.splitext(file_path)[1].lower()

        # 首先检查黑名单
        if ext in self.DANGEROUS_EXTENSIONS:
            return False

        # 然后检查白名单
        if ext in self.ALLOWED_EXTENSIONS:
            return True

        # 如果没有扩展名，允许（可能是目录）
        if not ext:
            return True

        # 其他扩展名不允许
        return False

    def _contains_malicious_content(self, content: str) -> bool:
        """检查内容是否包含恶意模式"""
        return bool(self.malicious_regex.search(content))

    def _validate_user_config(self, user_config: Dict[str, Any]) -> bool:
        """验证用户配置"""
        if not isinstance(user_config, dict):
            return False

        # 检查配置大小（用户配置单独限制为500KB）
        try:
            config_size = len(json.dumps(user_config))
            if config_size > 500 * 1024:  # 500KB
                return False
        except Exception:
            return False

        # 递归检查嵌套结构
        return self._validate_nested_structure(user_config)

    def _validate_nested_structure(self, data: Any, depth: int = 0) -> bool:
        """递归验证嵌套数据结构"""
        # 防止深度过大
        if depth > 10:
            return False

        if isinstance(data, dict):
            for key, value in data.items():
                # 检查键
                if not isinstance(key, str):
                    return False
                if self._contains_malicious_content(key):
                    return False

                # 递归检查值
                if not self._validate_nested_structure(value, depth + 1):
                    return False

        elif isinstance(data, list):
            for item in data:
                if not self._validate_nested_structure(item, depth + 1):
                    return False

        elif isinstance(data, str):
            # 检查字符串是否包含恶意内容
            if self._contains_malicious_content(data):
                return False

        elif isinstance(data, (int, float, bool, type(None))):
            # 基本类型允许
            pass

        else:
            # 其他类型不允许
            return False

        return True

    def _is_content_too_large(self, data: Dict[str, Any]) -> bool:
        """检查内容是否过大"""
        try:
            content_size = len(json.dumps(data))
            return content_size > self.MAX_TASK_CONTENT_SIZE
        except Exception:
            return True

    def validate_directory_path(self, dir_path: str, base_directory: str) -> bool:
        """验证目录路径是否安全

        Args:
            dir_path: 要验证的目录路径
            base_directory: 基础目录，目录必须在此目录内

        Returns:
            bool: 如果目录路径安全则返回True，否则返回False
        """
        try:
            # 转换为绝对路径
            abs_dir_path = os.path.abspath(dir_path)
            abs_base_dir = os.path.abspath(base_directory)

            # 检查路径遍历
            if self._contains_path_traversal(abs_dir_path):
                return False

            # 检查目录是否在基础目录内
            if not abs_dir_path.startswith(abs_base_dir):
                return False

            # 检查目录名是否包含危险字符
            dir_name = os.path.basename(abs_dir_path.rstrip('/\\'))
            if self.dangerous_chars_regex.search(dir_name):
                return False

            return True

        except Exception:
            return False

    def get_safe_filename(self, original_name: str, suffix: str = "") -> str:
        """获取安全的文件名（带可选后缀）

        Args:
            original_name: 原始文件名
            suffix: 可选后缀（如任务ID）

        Returns:
            str: 安全的文件名
        """
        # 清理原始文件名
        safe_name = self.sanitize_filename(original_name)

        # 添加后缀（如果提供）
        if suffix:
            name, ext = os.path.splitext(safe_name)
            safe_name = f"{name}_{suffix}{ext}"

        return safe_name


# 创建全局验证器实例
security_validator = SecurityValidator()