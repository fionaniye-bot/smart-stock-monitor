# 文件锁机制实现文档

## 概述

文件锁机制用于防止仪表盘插件中的并发处理导致的竞态条件。通过基于文件的互斥锁，确保同一任务不会被多个进程同时处理。

## 实现文件

1. `src/dashboard/file_lock.py` - 文件锁核心实现
2. `src/dashboard/dashboard_processor.py` - 任务处理器（集成文件锁）
3. `tests/dashboard/test_file_lock.py` - 文件锁测试
4. `tests/dashboard/test_dashboard_processor.py` - 任务处理器测试
5. `examples/file_lock_demo.py` - 使用示例

## FileLock 类

### 功能特性

- **基于文件的互斥锁**：使用文件系统实现进程间互斥
- **上下文管理器支持**：支持 `with` 语句自动获取和释放锁
- **超时机制**：可配置的获取锁超时时间
- **锁过期检查**：自动检测并清理过期锁
- **进程感知**：检查锁持有进程是否仍在运行
- **任务特定锁**：支持为不同任务创建独立锁

### 核心方法

#### `__init__(lock_file, timeout=30, poll_interval=0.1)`
初始化文件锁。

参数：
- `lock_file`: 锁文件路径
- `timeout`: 超时时间（秒），默认30秒
- `poll_interval`: 轮询间隔（秒），默认0.1秒

#### `acquire() -> bool`
尝试获取锁。如果锁已被其他进程持有，则等待直到超时。

返回：是否成功获取锁

#### `release()`
释放锁。删除锁文件，释放资源。

#### `_is_lock_expired() -> bool`
检查锁是否过期。读取锁文件，检查锁的创建时间是否已超过超时时间。

返回：锁是否已过期

#### `create_task_lock(task_id, lock_dir=".", timeout=30)`
静态方法，创建任务特定锁。

参数：
- `task_id`: 任务ID
- `lock_dir`: 锁文件目录
- `timeout`: 超时时间

返回：FileLock实例

### 使用示例

#### 基本用法
```python
from src.dashboard.file_lock import FileLock

lock = FileLock("/path/to/.lock_file", timeout=10)

if lock.acquire():
    try:
        # 执行需要互斥的操作
        process_data()
    finally:
        lock.release()
```

#### 使用上下文管理器
```python
from src.dashboard.file_lock import FileLock

try:
    with FileLock("/path/to/.lock_file", timeout=10) as lock:
        # 在with块内自动持有锁
        process_data()
        # 退出with块时自动释放锁
except TimeoutError:
    print("获取锁超时")
```

#### 创建任务锁
```python
from src.dashboard.file_lock import FileLock

# 为特定任务创建锁
task_lock = FileLock.create_task_lock(
    task_id="task_123",
    lock_dir="./locks",
    timeout=30
)

with task_lock:
    process_task("task_123")
```

## DashboardProcessor 类

### 功能特性

- **任务处理**：处理仪表盘任务的调度和执行
- **文件锁集成**：自动使用文件锁防止竞态条件
- **状态管理**：跟踪任务处理状态和进度
- **错误处理**：完善的错误处理和恢复机制
- **锁清理**：自动清理过期锁文件

### 核心方法

#### `find_pending_tasks() -> List[str]`
查找待处理任务。扫描任务目录，查找状态为"pending"的任务。

返回：待处理任务ID列表

#### `process_task(task_id) -> bool`
处理任务。使用文件锁确保同一任务不会被多个进程同时处理。

参数：`task_id` - 任务ID
返回：处理是否成功

#### `get_task_status(task_id) -> Optional[TaskStatus]`
获取任务状态。

参数：`task_id` - 任务ID
返回：TaskStatus对象或None（如果任务不存在）

#### `cleanup_expired_locks(max_age_seconds=3600)`
清理过期的锁文件。

参数：`max_age_seconds` - 最大年龄（秒），超过此时间的锁文件将被清理

### 使用示例

```python
from src.dashboard.dashboard_processor import DashboardProcessor

# 初始化处理器
processor = DashboardProcessor(
    task_dir="./tasks",
    lock_dir="./locks",
    timeout=30
)

# 查找待处理任务
pending_tasks = processor.find_pending_tasks()
print(f"待处理任务: {pending_tasks}")

# 处理任务
for task_id in pending_tasks:
    success = processor.process_task(task_id)
    print(f"任务 {task_id} 处理结果: {success}")

# 获取任务状态
status = processor.get_task_status("task_123")
if status:
    print(f"任务状态: {status.current_status}, 进度: {status.progress_percent}%")

# 清理过期锁
processor.cleanup_expired_locks(max_age_seconds=3600)
```

## 锁文件格式

锁文件使用JSON格式，包含以下信息：

```json
{
  "locked_at": 1678886400.123456,
  "timeout": 30,
  "process": 12345
}
```

- `locked_at`: 锁获取时间（Unix时间戳）
- `timeout`: 锁超时时间（秒）
- `process`: 持有锁的进程ID

## 锁文件命名约定

- 通用锁：`.lock_{自定义名称}`
- 任务锁：`.lock_{task_id}`

## 并发处理保证

文件锁机制提供以下保证：

1. **互斥性**：同一时间只有一个进程能持有特定锁
2. **安全性**：锁释放后，其他进程可以获取
3. **容错性**：进程崩溃时，锁会自动过期
4. **超时处理**：获取锁操作支持超时，避免死锁

## 测试覆盖

### 文件锁测试 (`test_file_lock.py`)
- 测试锁获取和释放
- 测试锁重复获取（应该失败）
- 测试锁过期检查
- 测试并发访问
- 测试上下文管理器
- 测试锁文件内容

### 任务处理器测试 (`test_dashboard_processor.py`)
- 测试处理器初始化
- 测试查找待处理任务
- 测试带锁处理任务
- 测试并发任务处理
- 测试获取任务状态
- 测试清理过期锁
- 测试任务处理失败情况
- 测试DashboardTask集成

## 运行测试

```bash
# 运行文件锁测试
python -m pytest tests/dashboard/test_file_lock.py -v

# 运行任务处理器测试
python -m pytest tests/dashboard/test_dashboard_processor.py -v

# 运行所有测试
python -m pytest tests/dashboard/ -v
```

## 演示脚本

运行演示脚本查看文件锁的实际使用：

```bash
cd smart-stock-monitor
python -c "import sys; sys.path.insert(0, '.'); from examples.file_lock_demo import main; main()"
```

演示内容包括：
1. 基本锁操作
2. 上下文管理器使用
3. 并发访问演示
4. 任务锁创建
5. 锁过期检查

## 集成到现有系统

要将文件锁机制集成到现有系统：

1. 在需要互斥访问的资源处创建FileLock实例
2. 使用 `with` 语句确保锁的正确获取和释放
3. 为不同资源使用不同的锁文件路径
4. 根据处理时间合理设置超时时间
5. 定期清理过期锁文件

## 最佳实践

1. **超时设置**：根据任务处理时间设置合理的超时时间
2. **锁粒度**：为不同的资源使用不同的锁，减少锁竞争
3. **错误处理**：始终处理TimeoutError和其他可能的异常
4. **资源清理**：定期运行 `cleanup_expired_locks()` 清理过期锁
5. **日志记录**：在关键操作处添加日志，便于调试

## 故障排除

### 常见问题

1. **锁获取失败**：检查锁文件权限和目录是否存在
2. **锁不释放**：检查进程是否正常退出，或使用 `cleanup_expired_locks()`
3. **性能问题**：减少锁持有时间，或使用更细粒度的锁
4. **死锁**：确保锁获取顺序一致，设置合理的超时时间

### 调试建议

1. 检查锁文件是否存在及其内容
2. 查看进程ID是否有效
3. 检查系统时间是否同步
4. 查看日志文件中的错误信息

## 性能考虑

1. **文件系统性能**：锁操作依赖文件系统，确保存储性能足够
2. **网络文件系统**：避免在网络文件系统上使用文件锁
3. **锁竞争**：减少锁持有时间，避免长时间持有锁
4. **锁数量**：避免创建过多锁文件，定期清理