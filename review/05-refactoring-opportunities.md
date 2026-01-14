# Refactoring Opportunities

**Priority Level:** MEDIUM to LOW
**Estimated Effort:** 2-3 weeks
**Action:** Improve code quality gradually

---

## Table of Contents

1. [Duplicate Code Patterns](#1-duplicate-code-patterns)
2. [Complex Functions](#2-complex-functions)
3. [Abstraction Opportunities](#3-abstraction-opportunities)
4. [Design Pattern Improvements](#4-design-pattern-improvements)
5. [Type System Enhancements](#5-type-system-enhancements)
6. [Module Organization](#6-module-organization)

---

## 1. Duplicate Code Patterns

### Issue 1.1: Duplicate Retry Logic
**Severity:** Medium | **Effort:** Small | **Value:** DRY principle

**Locations:**
- [gator/scheduler/slurm.py:108-136](../gator/scheduler/slurm.py#L108-L136) - `_retry_post`
- [gator/scheduler/slurm.py:138-165](../gator/scheduler/slurm.py#L138-L165) - `_retry_get`
- [gator/common/http_api.py:46-75](../gator/common/http_api.py#L46-L75) - GET method
- [gator/common/http_api.py:77-111](../gator/common/http_api.py#L77-L111) - POST method

**Description:**
Both Slurm scheduler and HTTP API implement nearly identical retry logic with exponential backoff.

**Current Pattern:**
```python
# Repeated in multiple places
for attempt in range(retries):
    try:
        # Execute operation
        response = await execute()
        if success:
            return response
        raise Exception("Failed")
    except Exception as e:
        if attempt == retries - 1:
            raise
        await asyncio.sleep(backoff * (2 ** attempt))
```

**Recommended Refactoring:**
```python
# gator/common/retry.py (new file)
from typing import TypeVar, Callable, Awaitable, Optional
from functools import wraps

T = TypeVar('T')

class RetryConfig:
    """Configuration for retry behavior"""
    def __init__(
        self,
        max_attempts: int = 3,
        backoff: float = 1.0,
        max_backoff: float = 60.0,
        exponential: bool = True,
        exceptions: tuple = (Exception,)
    ):
        self.max_attempts = max_attempts
        self.backoff = backoff
        self.max_backoff = max_backoff
        self.exponential = exponential
        self.exceptions = exceptions

async def retry_async(
    func: Callable[..., Awaitable[T]],
    config: RetryConfig,
    logger: Optional['Logger'] = None
) -> T:
    """Execute async function with retry logic"""
    for attempt in range(config.max_attempts):
        try:
            return await func()
        except config.exceptions as e:
            if attempt == config.max_attempts - 1:
                raise

            # Calculate backoff
            if config.exponential:
                sleep_time = min(
                    config.backoff * (2 ** attempt),
                    config.max_backoff
                )
            else:
                sleep_time = config.backoff

            if logger:
                await logger.warning(
                    f"Attempt {attempt + 1}/{config.max_attempts} failed: {e}. "
                    f"Retrying in {sleep_time}s..."
                )

            await asyncio.sleep(sleep_time)

    raise RuntimeError("Retry logic error")  # Should never reach

def retryable(config: RetryConfig):
    """Decorator for automatic retry"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await retry_async(
                lambda: func(*args, **kwargs),
                config
            )
        return wrapper
    return decorator
```

**Usage:**
```python
# In Slurm scheduler
from gator.common.retry import retry_async, RetryConfig

async def _request(self, method: str, route: str, **kwargs):
    """Make HTTP request with retry"""
    config = RetryConfig(
        max_attempts=self.retries,
        backoff=self.backoff,
        exceptions=(aiohttp.ClientError,)
    )

    async def execute():
        async with self.session.request(method, url, **kwargs) as response:
            response.raise_for_status()
            return await response.json()

    return await retry_async(execute, config, self.logger)

# Simplified methods
async def _retry_post(self, route: str, data: Dict) -> Dict:
    return await self._request('POST', route, json=data)

async def _retry_get(self, route: str) -> Dict:
    return await self._request('GET', route)
```

**Impact:**
- ✅ Single source of truth for retry logic
- ✅ Easier to maintain and test
- ✅ Consistent retry behavior across codebase
- ✅ Configurable retry strategies

---

### Issue 1.2: Duplicate Context Manager Pattern
**Severity:** Low-Medium | **Effort:** Small | **Value:** Code reduction

**Locations:**
- [gator/common/db_client.py](../gator/common/db_client.py) - Multiple async context managers

**Description:**
Multiple similar async context managers with empty finally blocks.

**Recommended Refactoring:**
```python
# Create base context manager
from contextlib import asynccontextmanager
from typing import AsyncGenerator, TypeVar

T = TypeVar('T')

@asynccontextmanager
async def managed_client(
    client_factory: Callable[[], Awaitable[T]],
    cleanup: Optional[Callable[[T], Awaitable[None]]] = None
) -> AsyncGenerator[T, None]:
    """Generic context manager for clients"""
    client = await client_factory()
    try:
        yield client
    finally:
        if cleanup:
            await cleanup(client)

# Usage
@asynccontextmanager
async def resolve_client(job: Job, job_map: Dict[str, Job]) -> AsyncGenerator:
    if job.get("ws") is not None:
        async with managed_client(lambda: websocket_client(job)) as ws:
            yield ws
    elif job.get("db_file") is not None:
        async with managed_client(lambda: database_client(job["db_file"])) as db:
            yield db
    else:
        raise RuntimeError(f"Can't resolve job {job}")
```

---

### Issue 1.3: Duplicate Copyright Headers
**Severity:** Low | **Effort:** Small | **Value:** Consistency

**Location:** [gator/common/ws_router.py:1-27](../gator/common/ws_router.py#L1-L27)

**Description:**
The copyright header appears twice in the file.

**Recommended Fix:**
Remove the duplicate lines 15-27, keeping only lines 1-13.

---

## 2. Complex Functions

### Issue 2.1: Tier.__launch() Method
**Severity:** Medium | **Effort:** Medium | **Value:** Readability

**Location:** [gator/tier.py](../gator/tier.py) - `__launch()` method (likely 100+ lines)

**Description:**
The launch method handles job launching, dependency resolution, and postponement in a single large function.

**Recommended Refactoring:**
```python
async def __launch(self) -> None:
    """Launch child jobs with dependency management"""
    await self._parse_jobs()
    await self._launch_independent_jobs()
    await self._setup_dependent_jobs()
    await self._wait_for_completion()

async def _parse_jobs(self) -> None:
    """Parse and validate job specifications"""
    for idx, spec in enumerate(self.spec.jobs):
        child = Child(...)
        if not spec.depends:
            self.jobs_pending[child.ident] = child
        else:
            self.jobs_waiting[child.ident] = child

async def _launch_independent_jobs(self) -> None:
    """Launch jobs with no dependencies"""
    for ident, child in list(self.jobs_pending.items()):
        await self._launch_child(child)

async def _setup_dependent_jobs(self) -> None:
    """Setup postpone tasks for dependent jobs"""
    for ident, child in self.jobs_waiting.items():
        task = asyncio.create_task(self._wait_for_dependencies(child))
        self.postpone_tasks[ident] = task

async def _wait_for_dependencies(self, child: Child) -> None:
    """Wait for job dependencies and launch when ready"""
    deps = child.spec.depends
    await self._wait_for_deps(deps)

    if self._should_launch(child, deps):
        await self._launch_child(child)
    else:
        await self._prune_child(child)

def _should_launch(self, child: Child, deps: List[Dependency]) -> bool:
    """Check if job should launch based on dependency results"""
    for dep in deps:
        dep_child = self.jobs_completed.get(dep.target)
        if not dep_child:
            return False

        if dep.on == DependencyType.ON_PASS and dep_child.result != JobResult.SUCCESS:
            return False
        elif dep.on == DependencyType.ON_FAIL and dep_child.result == JobResult.SUCCESS:
            return False

    return True
```

**Impact:**
- ✅ Easier to understand
- ✅ Easier to test individual pieces
- ✅ Better error handling per stage
- ✅ Clearer logic flow

---

### Issue 2.2: Database define_transform() Method
**Severity:** Low-Medium | **Effort:** Medium | **Value:** Maintainability

**Location:** [gator/common/db.py](../gator/common/db.py) - `define_transform()` method

**Description:**
This method generates multiple nested closures and SQL statements dynamically, making it hard to follow.

**Recommended Approach:**
- Extract SQL generation to separate methods
- Use SQL query builder library (e.g., SQLAlchemy Core)
- Create explicit transformation classes instead of closures

---

## 3. Abstraction Opportunities

### Issue 3.1: Process Management Abstraction
**Severity:** Low-Medium | **Effort:** Medium | **Value:** Reusability

**Description:**
Process launching, monitoring, and termination logic is scattered across Wrapper and LocalScheduler.

**Recommended Abstraction:**
```python
# gator/common/process.py (new file)
class ProcessManager:
    """Manages process lifecycle"""

    async def launch(
        self,
        command: str,
        args: List[str],
        env: Dict[str, str],
        cwd: Optional[Path] = None
    ) -> asyncio.subprocess.Process:
        """Launch a process safely"""
        # Validation
        # Environment setup
        # Launch with proper error handling

    async def monitor(
        self,
        proc: asyncio.subprocess.Process,
        interval: float = 1.0
    ) -> AsyncGenerator[ProcessStats, None]:
        """Monitor process resource usage"""
        while proc.returncode is None:
            stats = await self._collect_stats(proc)
            yield stats
            await asyncio.sleep(interval)

    async def terminate(
        self,
        proc: asyncio.subprocess.Process,
        timeout: float = 5.0,
        kill_children: bool = True
    ) -> None:
        """Gracefully terminate process"""
        if kill_children:
            await self._terminate_children(proc)

        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()

    async def _collect_stats(self, proc) -> ProcessStats:
        """Collect process statistics"""
        try:
            p = psutil.Process(proc.pid)
            return ProcessStats(
                cpu_percent=p.cpu_percent(),
                memory_mb=p.memory_info().rss / (1024 * 1024),
                num_threads=p.num_threads(),
                # ...
            )
        except psutil.NoSuchProcess:
            return None
```

**Usage:**
```python
# In Wrapper
self.process_manager = ProcessManager()

async def launch(self):
    self.proc = await self.process_manager.launch(
        self.command,
        self.args,
        self.env,
        self.cwd
    )

    async for stats in self.process_manager.monitor(self.proc):
        await self.record_stats(stats)
```

---

### Issue 3.2: Configuration Management
**Severity:** Medium | **Effort:** Medium | **Value:** Flexibility

**Description:**
Configuration is scattered across CLI arguments, environment variables, and hardcoded values.

**Recommended Abstraction:**
```python
# gator/common/config.py (new file)
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import os

@dataclass
class GatorConfig:
    """Centralized configuration"""
    # Paths
    tracking_dir: Path = field(default_factory=lambda: Path.cwd() / ".gator")
    log_dir: Optional[Path] = None

    # Logging
    log_level: str = "INFO"
    log_file: Optional[Path] = None
    log_max_messages: Dict[str, int] = field(default_factory=lambda: {
        "WARNING": 100,
        "ERROR": 100,
        "CRITICAL": 100
    })

    # Resources
    default_concurrency: int = field(default_factory=os.cpu_count)
    default_memory_mb: int = 1024

    # Monitoring
    heartbeat_interval: float = 1.0
    resource_monitor_interval: float = 1.0

    # Timeouts
    websocket_timeout: float = 30.0
    shutdown_timeout: float = 10.0

    # Hub
    hub_url: Optional[str] = None
    hub_auth_token: Optional[str] = None

    @classmethod
    def from_env(cls) -> 'GatorConfig':
        """Load configuration from environment variables"""
        return cls(
            tracking_dir=Path(os.getenv('GATOR_TRACKING_DIR', '.gator')),
            log_level=os.getenv('GATOR_LOG_LEVEL', 'INFO'),
            hub_url=os.getenv('GATOR_HUB_URL'),
            hub_auth_token=os.getenv('GATOR_HUB_TOKEN'),
            # ...
        )

    @classmethod
    def from_file(cls, path: Path) -> 'GatorConfig':
        """Load configuration from YAML file"""
        import yaml
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**data)

    def to_file(self, path: Path) -> None:
        """Save configuration to YAML file"""
        import yaml
        with open(path, 'w') as f:
            yaml.dump(dataclasses.asdict(self), f)
```

---

## 4. Design Pattern Improvements

### Issue 4.1: Add Builder Pattern for Job Specifications
**Severity:** Low | **Effort:** Small | **Value:** Usability

**Description:**
Job specifications are currently created directly from YAML. A builder pattern would enable programmatic job creation.

**Implementation:**
```python
# gator/specs/builder.py (new file)
class JobBuilder:
    """Builder for Job specifications"""

    def __init__(self, ident: str):
        self._spec = {'ident': ident}

    def command(self, cmd: str) -> 'JobBuilder':
        self._spec['command'] = cmd
        return self

    def args(self, *args: str) -> 'JobBuilder':
        self._spec['args'] = list(args)
        return self

    def env(self, **kwargs: str) -> 'JobBuilder':
        self._spec.setdefault('env', {}).update(kwargs)
        return self

    def depends_on(self, target: str, on: str = 'pass') -> 'JobBuilder':
        dep = {'target': target, 'on': on}
        self._spec.setdefault('depends', []).append(dep)
        return self

    def cores(self, count: int) -> 'JobBuilder':
        self._spec['cores'] = count
        return self

    def memory(self, mb: int) -> 'JobBuilder':
        self._spec['memory'] = mb
        return self

    def build(self) -> Job:
        return Job(**self._spec)

# Usage
job = (JobBuilder('analysis')
    .command('python')
    .args('analyze.py', '--input', 'data.csv')
    .env(PYTHONPATH='/custom/path')
    .cores(4)
    .memory(8192)
    .depends_on('preparation', 'pass')
    .build())
```

---

### Issue 4.2: Strategy Pattern for Aggregation
**Severity:** Low | **Effort:** Small | **Value:** Extensibility

**Description:**
Metric aggregation is hardcoded. Use strategy pattern for pluggable aggregation.

**Implementation:**
```python
# gator/common/aggregation.py (new file)
from abc import ABC, abstractmethod
from typing import List

class AggregationStrategy(ABC):
    @abstractmethod
    def aggregate(self, values: List[float]) -> float:
        pass

class SumAggregation(AggregationStrategy):
    def aggregate(self, values: List[float]) -> float:
        return sum(values)

class MaxAggregation(AggregationStrategy):
    def aggregate(self, values: List[float]) -> float:
        return max(values) if values else 0.0

class MeanAggregation(AggregationStrategy):
    def aggregate(self, values: List[float]) -> float:
        return sum(values) / len(values) if values else 0.0

# Usage
class MetricAggregator:
    def __init__(self):
        self.strategies = {
            'sum': SumAggregation(),
            'max': MaxAggregation(),
            'mean': MeanAggregation(),
        }

    def aggregate(self, metric_name: str, values: List[float]) -> float:
        strategy_name = self.get_strategy_for_metric(metric_name)
        strategy = self.strategies[strategy_name]
        return strategy.aggregate(values)
```

---

## 5. Type System Enhancements

### Issue 5.1: Add Mypy Support
**Severity:** Low-Medium | **Effort:** Medium | **Value:** Type safety

**Description:**
While the codebase has good type hints, there's no static type checking with mypy.

**Implementation:**
```toml
# Add to pyproject.toml
[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
disallow_untyped_decorators = false
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_no_return = true
warn_unreachable = true
strict_equality = true

[[tool.mypy.overrides]]
module = "psutil.*"
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = "aiosqlite.*"
ignore_missing_imports = true
```

```yaml
# Add to .github/workflows/ci.yml
- name: Type check
  run: poetry run mypy gator/
```

---

### Issue 5.2: Use Protocol for Duck Typing
**Severity:** Low | **Effort:** Small | **Value:** Type safety

**Description:**
Use typing.Protocol for interfaces instead of ABC where appropriate.

**Example:**
```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class Loggable(Protocol):
    """Protocol for objects that can be logged"""
    async def log(self, severity: str, message: str) -> None: ...

@runtime_checkable
class Monitorable(Protocol):
    """Protocol for objects that can be monitored"""
    async def get_stats(self) -> Dict[str, float]: ...

# Usage - no inheritance needed
def setup_logging(obj: Loggable) -> None:
    """Works with any object that implements log()"""
    ...
```

---

## 6. Module Organization

### Issue 6.1: Split Large Modules
**Severity:** Low | **Effort:** Medium | **Value:** Organization

**Description:**
Some modules are quite large and could be split for better organization.

**Recommendations:**

**1. Split `gator/specs/jobs.py`**
```
gator/specs/
  ├── __init__.py
  ├── base.py         # SpecBase
  ├── job.py          # Job
  ├── job_group.py    # JobGroup
  ├── job_array.py    # JobArray
  └── dependency.py   # Dependency classes
```

**2. Split `gator/common/types.py`**
```
gator/common/types/
  ├── __init__.py
  ├── job_types.py    # JobResult, Summary, etc.
  ├── child.py        # Child class
  ├── metrics.py      # Metric types
  └── resources.py    # Resource types
```

**3. Create domain-specific packages**
```
gator/
  ├── execution/      # Tier, Wrapper, launch
  ├── scheduling/     # Schedulers
  ├── monitoring/     # Resource monitoring, logging
  ├── communication/  # WebSocket, HTTP
  └── storage/        # Database, caching
```

---

## Summary Table

| Refactoring | Severity | Effort | Value | Files Affected |
|-------------|----------|--------|-------|----------------|
| Duplicate retry logic | Medium | Small | High | 2 files |
| Duplicate context managers | Low-Medium | Small | Medium | 1 file |
| Complex Tier.__launch() | Medium | Medium | High | 1 file |
| Process management abstraction | Low-Medium | Medium | Medium | 2 files |
| Configuration management | Medium | Medium | High | Many |
| Builder pattern | Low | Small | Medium | New code |
| Strategy pattern | Low | Small | Medium | New code |
| Add mypy support | Low-Medium | Medium | High | All files |
| Module splitting | Low | Medium | Medium | Many |

**Recommended Priority:**
1. Duplicate retry logic (quick win)
2. Configuration management (high value)
3. Add mypy support (quality improvement)
4. Complex function refactoring (maintainability)
5. Process management abstraction (reusability)
6. Module organization (long-term maintainability)

---

*These refactorings will improve code quality without changing functionality. Implement gradually to avoid disruption.*
