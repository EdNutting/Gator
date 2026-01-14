# Incomplete Implementations

**Priority Level:** MEDIUM
**Estimated Effort:** 2-4 weeks
**Action:** Complete in next development cycle

---

## Table of Contents

1. [NotImplementedError Instances](#1-notimplementederror-instances)
2. [README TODO List](#2-readme-todo-list)
3. [Stub Methods in BaseDatabase](#3-stub-methods-in-basedatabase)
4. [Empty Validation Methods](#4-empty-validation-methods)
5. [Missing Features](#5-missing-features)

---

## 1. NotImplementedError Instances

### Issue 1.1: BaseScheduler.update_options()
**Severity:** Medium
**Effort:** Small
**Feature Status:** Not implemented

**Location:** [gator/scheduler/common.py:65](../gator/scheduler/common.py#L65)

**Description:**
The base scheduler defines `update_options()` but doesn't implement it. This is called when parent tiers need to update child scheduler options dynamically (e.g., adjusting concurrency).

**Current Code:**
```python
async def update_options(self, child: Child, options: Dict[str, int]) -> None:
    """Inform scheduler of updated concurrency for a child job"""
    raise NotImplementedError()
```

**Recommended Implementation:**

```python
# In LocalScheduler
async def update_options(self, ident: str, updates: Dict[str, int]) -> None:
    """Update scheduler options for a running job"""
    async with self.update_lock:
        if ident not in self.launched_children:
            await self.logger.warning(
                f"Cannot update options for unknown child: {ident}"
            )
            return

        # Update concurrency allocation
        if "concurrency" in updates:
            old_slots = self.slots.get(ident, 0)
            new_slots = updates["concurrency"]
            delta = new_slots - old_slots

            if delta > 0 and self.concurrency >= delta:
                # Allocate more concurrency
                self.concurrency -= delta
                self.slots[ident] = new_slots
                await self.logger.info(
                    f"Increased concurrency for '{ident}' to {new_slots}"
                )
            elif delta < 0:
                # Release concurrency back to pool
                self.concurrency += abs(delta)
                self.slots[task.ident] = granted

# Update scheduler interface
class BaseScheduler(ABC):
    @abstractmethod
    async def update_options(self, ident: str, options: Dict[str, Any]) -> None:
        """Update scheduler options for a running job"""
        raise NotImplementedError("Scheduler must implement update_options()")
```

**Usage in Tier:**
```python
async def update_scheduler_opts(self, ident: str, opts: Dict[str, Any]) -> None:
    """Update scheduler options for a child (e.g., reallocate resources)"""
    if self.scheduler:
        await self.scheduler.update_options(ident, opts)
        await self.logger.info(f"Updated scheduler options for {ident}")
```

**Impact:**
- ✅ Enables dynamic resource allocation
- ✅ Better resource utilization
- ✅ Supports adaptive scheduling
- ✅ Required for advanced scheduling features

---

## 5. README TODO List Features

### Overview
**Location:** [README.md:112-121](../README.md#L112-L121)

The README lists several features that are not yet implemented. These represent the roadmap for future development.

### Feature 1: Hub Working (Partially Complete)

**Status:** Partially implemented
**Effort:** Large
**Description:**
The Hub is partially implemented but marked as needing completion. Basic registration and query functionality exists, but needs additional features.

**Missing Pieces:**
- Real-time job updates via WebSocket to frontend
- Historical job browsing and filtering
- Performance metrics visualization
- User authentication and authorization
- Multi-user support

**Implementation Notes:**
- Backend exists in [gator/hub/](../gator/hub/)
- Frontend exists in [gator-hub/](../gator-hub/)
- Database models defined
- API endpoints partially implemented

---

## 2. Artifact Passing Between Jobs

### Issue: Artifact-Based Dependencies Not Implemented
**Severity:** Medium
**Effort:** Large
**Feature Type:** Core functionality

**Location:** [README.md:115](../README.md#L115) TODO item

**Description:**
Jobs currently cannot pass artifacts (files, data) to dependent jobs. Dependencies only control execution order, not data flow.

**Current Limitation:**
```yaml
!JobGroup
  jobs:
  - !Job
      ident: generate_data
      command: python
      args: ["generate_data.py"]
      # ❌ No way to pass output to next job
  - !Job
      ident: process_data
      on_pass: [generate_data]
      command: python
      args: ["process.py"]  # ❌ How does it know where the data is?
```

**Recommended Design:**

```python
# Add to Job spec
class Job(SpecBase):
    artifacts: Optional[Dict[str, str]] = None  # {"output": "path/to/file"}
    depends_artifacts: Optional[Dict[str, str]] = None  # {"input": "parent_job.output"}

# Example YAML spec
!Job
  ident: producer
  command: echo
  args: ["result.txt"]
  artifacts:
    output: "result.txt"

!Job
  ident: consumer
  depends:
    - target: producer
      on: pass
      artifacts:
        input_file: output.txt  # Map dependency artifact to local name
  command: process
  args: ["$GATOR_ARTIFACT_input_file"]
```

**Implementation Approach:**
```python
# In gator/common/artifacts.py (new file)
class ArtifactManager:
    """Manage artifact passing between jobs"""

    def __init__(self, tracking_dir: Path):
        self.tracking_dir = tracking_dir
        self.artifact_dir = tracking_dir / "artifacts"
        self.artifact_dir.mkdir(exist_ok=True)

    async def store_artifact(self, job_id: str, name: str, path: Path) -> None:
        """Store an artifact from a job"""
        artifact_path = self.artifact_dir / job_id / name
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(path, artifact_path)

    async def retrieve_artifact(self, job_id: str, name: str) -> Path:
        """Retrieve an artifact from a completed job"""
        artifact_path = self.artifact_dir / job_id / name
        if not artifact_path.exists():
            raise FileNotFoundError(f"Artifact {name} not found for job {job_id}")
        return artifact_path
```

**Configuration:**
```yaml
!Job
  ident: producer
  command: python
  args: ["generate_data.py"]
  artifacts:
    outputs:
      - name: "results"
        path: "./results/*.json"

!Job
  ident: consumer
  command: python
  args: ["process.py"]
  depends:
    - job: producer
      artifacts: ["results.csv"]  # Wait for and access this artifact
```

**Impact:**
- Enable data pipelines
- Better job orchestration
- Cache intermediate results
- Support complex workflows

---

## 3. Generalized Metrics System

### Feature: Replace Warning/Error Counts with Arbitrary Metrics
**Priority:** Medium
**Effort:** Large
**From:** [README.md](../README.md) TODO list

**Description:**
The current system tracks warnings and errors as specific metrics. This should be generalized to support arbitrary metrics with various aggregation strategies.

**Current Limitation:**
```python
# Only warnings and errors are tracked
summary = Summary(
    warnings=sum(child.warnings for child in children),
    errors=sum(child.errors for child in children)
)
```

**Proposed Design:**

```python
# gator/common/metrics.py (new file)
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Callable

class AggregationType(Enum):
    SUM = "sum"
    MIN = "min"
    MAX = "max"
    MEAN = "mean"
    COUNT = "count"
    FIRST = "first"
    LAST = "last"

@dataclass
class MetricDefinition:
    """Definition of a custom metric"""
    name: str
    aggregation: AggregationType
    description: str = ""
    unit: str = ""

@dataclass
class Metric:
    """A recorded metric value"""
    name: str
    value: float
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    metadata: Dict[str, Any] = field(default_factory=dict)

class MetricsRegistry:
    """Registry for custom metrics"""
    def __init__(self):
        self._metrics: Dict[str, MetricDefinition] = {}
        self._register_builtin_metrics()

    def _register_builtin_metrics(self):
        """Register built-in metrics"""
        self.register(MetricDefinition("warnings", AggregationType.SUM, "Number of warnings"))
        self.register(MetricDefinition("errors", AggregationType.SUM, "Number of errors"))
        self.register(MetricDefinition("duration", AggregationType.SUM, "Execution time", "seconds"))
        self.register(MetricDefinition("cpu_peak", AggregationType.MAX, "Peak CPU usage", "%"))
        self.register(MetricDefinition("memory_peak", AggregationType.MAX, "Peak memory", "MB"))

    def register(self, metric: MetricDefinition):
        """Register a custom metric"""
        self._metrics[metric.name] = metric

    def aggregate(self, metric_name: str, values: List[float]) -> float:
        """Aggregate values for a metric"""
        if not values:
            return 0.0

        definition = self._metrics.get(metric_name)
        if not definition:
            raise ValueError(f"Unknown metric: {metric_name}")

        aggregation = definition.aggregation
        if aggregation == AggregationType.SUM:
            return sum(values)
        elif aggregation == AggregationType.MIN:
            return min(values)
        elif aggregation == AggregationType.MAX:
            return max(values)
        elif aggregation == AggregationType.MEAN:
            return sum(values) / len(values)
        elif aggregation == AggregationType.COUNT:
            return len(values)
        elif aggregation == AggregationType.FIRST:
            return values[0]
        elif aggregation == AggregationType.LAST:
            return values[-1]
```

**Usage in Specifications:**
```yaml
!Job
  ident: analyze_data
  command: python
  args: ["analyze.py"]
  metrics:
    - name: rows_processed
      aggregation: sum
      description: "Total rows processed"
    - name: max_latency
      aggregation: max
      unit: ms
```

**Impact:**
- ✅ Flexible metric collection
- ✅ Custom aggregation strategies
- ✅ Better monitoring capabilities
- ✅ Extensible framework

---

## 5. Random Number Seeding

### Feature: Reproducible Random Number Generation
**Status:** TODO
**Effort:** Small
**Value:** Reproducibility

**Description:**
From README TODO: "Random number seeding" - Add support for seeding random number generators for reproducible results in jobs that use randomness.

**Proposed Design:**

```python
# In job specifications
!Job
  ident: monte_carlo
  command: python
  args: ["simulate.py"]
  seed: 42  # ✅ Reproducible results

!JobArray
  ident: parallel_sims
  repeats: 100
  seed: 1000  # Base seed
  jobs:
    - !Job
        ident: sim
        command: python
        args: ["simulate.py"]
        # Each array iteration gets seed: base_seed + array_index
```

**Implementation:**

```python
# In wrapper.py, when launching subprocess
async def launch(self) -> Summary:
    # Set random seeds in environment
    seed = self.spec.get('seed')
    if seed is not None:
        # Add to environment variables
        env = os.environ.copy()
        env['GATOR_SEED'] = str(seed)
        env['PYTHONHASHSEED'] = str(seed)  # For Python
        env['RANDOM_SEED'] = str(seed)     # Generic

        # For arrays, add array index offset
        if hasattr(self, 'array_index'):
            effective_seed = seed + self.array_index
            env['GATOR_SEED'] = str(effective_seed)
            env['PYTHONHASHSEED'] = str(effective_seed)

        # Launch with seeded environment
        self.proc = await asyncio.create_subprocess_exec(
            self.command,
            *self.args,
            env=env,  # Use seeded environment
            # ...
        )
```

**User Code:**
```python
# Users access via environment variable
import os
import random
import numpy as np

# Get seed from Gator
seed = int(os.environ.get('GATOR_SEED', 0))

# Seed all RNGs
random.seed(seed)
np.random.seed(seed)

# Now random operations are reproducible
```

**Impact:**
- ✅ Reproducible results
- ✅ Better for testing
- ✅ Easier debugging
- ✅ Scientific rigor

---

## 6. Hooks System

### Feature: Execution Hooks
**Status:** TODO
**Effort:** Medium
**Value:** Extensibility

**Description:**
From README TODO: "Hooks" - Add hook points for custom code execution at various stages of job lifecycle.

**Proposed Hook Points:**

```python
# gator/common/hooks.py (new file)
from typing import Callable, Awaitable, List, Any
from enum import Enum

class HookPoint(Enum):
    """Lifecycle hook points"""
    # Job hooks
    PRE_JOB = "pre_job"           # Before job starts
    POST_JOB = "post_job"         # After job completes
    JOB_FAIL = "job_fail"         # When job fails
    JOB_TIMEOUT = "job_timeout"   # When job times out

    # Tier hooks
    PRE_TIER = "pre_tier"         # Before tier starts
    POST_TIER = "post_tier"       # After tier completes

    # Log hooks
    LOG_WARNING = "log_warning"   # When warning logged
    LOG_ERROR = "log_error"       # When error logged

    # Resource hooks
    MEMORY_LIMIT = "memory_limit" # When memory limit exceeded
    CPU_LIMIT = "cpu_limit"       # When CPU limit exceeded

HookCallback = Callable[[Dict[str, Any]], Awaitable[None]]

class HookManager:
    """Manages execution hooks"""
    def __init__(self):
        self._hooks: Dict[HookPoint, List[HookCallback]] = {}

    def register(self, hook_point: HookPoint, callback: HookCallback):
        """Register a hook callback"""
        if hook_point not in self._hooks:
            self._hooks[hook_point] = []
        self._hooks[hook_point].append(callback)

    async def trigger(self, hook_point: HookPoint, context: Dict[str, Any]):
        """Trigger all hooks for a hook point"""
        if hook_point not in self._hooks:
            return

        for callback in self._hooks[hook_point]:
            try:
                await callback(context)
            except Exception as e:
                # Log but don't fail on hook errors
                print(f"Hook {hook_point} failed: {e}")

# Global hook manager
hooks = HookManager()
```

**Usage in YAML:**
```yaml
!Job
  ident: important_job
  command: python
  args: ["script.py"]
  hooks:
    pre_job: "scripts/setup.sh"
    post_job: "scripts/cleanup.sh"
    job_fail: "scripts/notify_failure.sh"
```

**Usage in Code:**
```python
# Custom hook scripts can register Python callbacks
from gator.common.hooks import hooks, HookPoint

async def notify_on_failure(context: Dict[str, Any]):
    """Send notification when job fails"""
    job_ident = context['ident']
    error = context['error']
    # Send email, Slack message, etc.
    await send_notification(f"Job {job_ident} failed: {error}")

hooks.register(HookPoint.JOB_FAIL, notify_on_failure)
```

**Integration in Wrapper:**
```python
async def launch(self) -> Summary:
    # Trigger pre-job hooks
    await self.hooks.trigger(HookPoint.PRE_JOB, {
        'ident': self.ident,
        'spec': self.spec,
    })

    try:
        # Execute job
        result = await self._execute()
    except Exception as e:
        # Trigger failure hooks
        await self.hooks.trigger(HookPoint.JOB_FAIL, {
            'ident': self.ident,
            'error': str(e),
        })
        raise
    finally:
        # Trigger post-job hooks
        await self.hooks.trigger(HookPoint.POST_JOB, {
            'ident': self.ident,
            'result': result,
        })
```

**Impact:**
- ✅ Extensible without code changes
- ✅ Custom notifications
- ✅ Pre/post processing
- ✅ Integration with external systems

---

## 7. Tool-Based Log Parsers

### Feature: Pluggable Log Parsing
**Status:** TODO
**Effort:** Medium-Large
**Value:** Tool integration

**Description:**
From README TODO: "Tool based log parsers" - Add specialized parsers for different tools' log formats.

**Proposed Design:**

```python
# gator/parsers/base.py (new directory)
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Pattern
import re

@dataclass
class LogEntry:
    """Parsed log entry"""
    severity: str
    message: str
    timestamp: Optional[float] = None
    file: Optional[str] = None
    line: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

class LogParser(ABC):
    """Base class for log parsers"""
    @abstractmethod
    def parse_line(self, line: str) -> Optional[LogEntry]:
        """Parse a single log line"""
        pass

    @abstractmethod
    def extract_metrics(self, lines: List[str]) -> Dict[str, float]:
        """Extract metrics from logs"""
        pass

# gator/parsers/gcc.py
class GCCParser(LogParser):
    """Parser for GCC/Clang compiler output"""
    ERROR_PATTERN = re.compile(r'(.+):(\d+):(\d+): error: (.+)')
    WARNING_PATTERN = re.compile(r'(.+):(\d+):(\d+): warning: (.+)')

    def parse_line(self, line: str) -> Optional[LogEntry]:
        # Try error pattern
        match = self.ERROR_PATTERN.match(line)
        if match:
            return LogEntry(
                severity='ERROR',
                message=match.group(4),
                file=match.group(1),
                line=int(match.group(2)),
                metadata={'column': int(match.group(3))}
            )

        # Try warning pattern
        match = self.WARNING_PATTERN.match(line)
        if match:
            return LogEntry(
                severity='WARNING',
                message=match.group(4),
                file=match.group(1),
                line=int(match.group(2)),
                metadata={'column': int(match.group(3))}
            )

        return None

# gator/parsers/pytest.py
class PytestParser(LogParser):
    """Parser for pytest output"""
    def extract_metrics(self, lines: List[str]) -> Dict[str, float]:
        metrics = {}
        # Parse "5 passed, 2 failed, 1 skipped in 10.2s"
        summary_pattern = re.compile(
            r'(\d+) passed(?:, (\d+) failed)?(?:, (\d+) skipped)? in ([\d.]+)s'
        )
        for line in lines:
            match = summary_pattern.search(line)
            if match:
                metrics['tests_passed'] = int(match.group(1))
                metrics['tests_failed'] = int(match.group(2) or 0)
                metrics['tests_skipped'] = int(match.group(3) or 0)
                metrics['test_duration'] = float(match.group(4))
        return metrics
```

**Usage in Specifications:**
```yaml
!Job
  ident: compile
  command: gcc
  args: ["-Wall", "main.c"]
  parser: gcc  # Use GCC parser

!Job
  ident: run_tests
  command: pytest
  parser: pytest  # Use pytest parser
```

**Impact:**
- ✅ Better error reporting
- ✅ Tool-specific metric extraction
- ✅ Structured log analysis
- ✅ Easier integration

---

## 8. Custom Runners

### Feature: Non-Shell Runners
**Status:** TODO
**Effort:** Medium
**Value:** Flexibility

**Description:**
From README TODO: "Custom runners - currently everything is shell, perhaps support other things?"

**Proposed Runners:**

```python
# gator/runners/base.py (new directory)
from abc import ABC, abstractmethod

class Runner(ABC):
    """Base class for job runners"""
    @abstractmethod
    async def execute(self, spec: Dict[str, Any]) -> subprocess.Process:
        """Execute a job with this runner"""
        pass

# gator/runners/shell.py
class ShellRunner(Runner):
    """Execute via shell (current behavior)"""
    async def execute(self, spec: Dict[str, Any]) -> subprocess.Process:
        return await asyncio.create_subprocess_exec(
            spec['command'],
            *spec['args'],
            # ...
        )

# gator/runners/docker.py
class DockerRunner(Runner):
    """Execute in Docker container"""
    async def execute(self, spec: Dict[str, Any]) -> subprocess.Process:
        image = spec.get('image', 'ubuntu:latest')
        return await asyncio.create_subprocess_exec(
            'docker', 'run', '--rm',
            '-v', f"{os.getcwd()}:/work",
            image,
            spec['command'],
            *spec['args'],
            # ...
        )

# gator/runners/singularity.py
class SingularityRunner(Runner):
    """Execute in Singularity container"""
    async def execute(self, spec: Dict[str, Any]) -> subprocess.Process:
        image = spec['image']
        return await asyncio.create_subprocess_exec(
            'singularity', 'exec',
            image,
            spec['command'],
            *spec['args'],
            # ...
        )

# gator/runners/python.py
class PythonRunner(Runner):
    """Execute Python code directly (no subprocess)"""
    async def execute(self, spec: Dict[str, Any]) -> subprocess.Process:
        # Load and execute Python module
        module_path = spec['module']
        function = spec.get('function', 'main')
        # Import and execute directly
        # ...
```

**Usage in Specifications:**
```yaml
!Job
  ident: containerized
  runner: docker
  image: python:3.11
  command: python
  args: ["script.py"]

!Job
  ident: hpc_job
  runner: singularity
  image: /path/to/image.sif
  command: python
  args: ["compute.py"]

!Job
  ident: native_python
  runner: python
  module: my_module.tasks
  function: process_data
  args: ["input.csv"]
```

**Impact:**
- ✅ Container support
- ✅ Better isolation
- ✅ HPC compatibility
- ✅ Direct Python execution

---

## 9. Non-Environment Variable Parameters

### Feature: Parameter Passing Beyond Environment Variables
**Status:** TODO
**Effort:** Small-Medium
**Value:** Flexibility

**Description:**
From README TODO: "Non-environment variable based parameters" - Add additional ways to pass parameters to jobs.

**Proposed Methods:**

**1. File-Based Parameters:**
```yaml
!Job
  ident: data_processor
  command: python
  args: ["process.py"]
  parameters:
    method: file
    path: /tmp/gator_params.json
    format: json
    data:
      input_file: data.csv
      output_dir: results/
      batch_size: 100
```

**2. Command Line Substitution:**
```yaml
!Job
  ident: analyzer
  command: python
  args:
    - "analyze.py"
    - "--input"
    - "{{ input_file }}"  # Template substitution
    - "--batch-size"
    - "{{ batch_size }}"
  parameters:
    input_file: data.csv
    batch_size: 100
```

**3. Standard Input:**
```yaml
!Job
  ident: processor
  command: python
  args: ["process.py"]
  parameters:
    method: stdin
    format: json
    data:
      config: value
```

**Implementation:**
```python
# In wrapper.py
async def _prepare_parameters(self) -> Dict[str, str]:
    """Prepare parameters based on method"""
    params = self.spec.get('parameters', {})
    method = params.get('method', 'env')

    if method == 'env':
        # Current behavior - return env vars
        return {f"GATOR_{k.upper()}": str(v) for k, v in params.get('data', {}).items()}

    elif method == 'file':
        # Write parameters to file
        path = params['path']
        format = params.get('format', 'json')
        data = params['data']

        if format == 'json':
            with open(path, 'w') as f:
                json.dump(data, f)
        elif format == 'yaml':
            with open(path, 'w') as f:
                yaml.dump(data, f)

        return {'GATOR_PARAMS_FILE': path}

    elif method == 'stdin':
        # Prepare data for stdin
        self._stdin_data = json.dumps(params['data'])
        return {}

    elif method == 'args':
        # Template substitution in args
        self.args = [
            self._substitute_template(arg, params['data'])
            for arg in self.args
        ]
        return {}
```

**Impact:**
- ✅ More flexible parameter passing
- ✅ Better for complex configurations
- ✅ Support for tools that don't use env vars
- ✅ Cleaner command lines

---

## Summary Table

| Feature | Status | Effort | Value | README Item |
|---------|--------|--------|-------|-------------|
| NotImplementedError fixes | Incomplete | Small | High | - |
| Hub functionality | In Progress | Large | High | ✅ |
| Artifact passing | TODO | Medium | High | ✅ |
| Generalized metrics | TODO | Medium | High | ✅ |
| Random seeding | TODO | Small | Medium | ✅ |
| Hooks system | TODO | Medium | High | ✅ |
| Log parsers | TODO | Medium-Large | Medium | ✅ |
| Custom runners | TODO | Medium | High | ✅ |
| Non-env parameters | TODO | Small-Medium | Medium | ✅ |
| BaseDatabase stubs | Incomplete | Small | Medium | - |

**Total Estimated Effort:** 4-6 weeks of focused development

---

## Implementation Priority

### Phase 1 (Immediate - 1 week)
1. Fix all NotImplementedError instances
2. Implement missing BaseDatabase methods
3. Add random number seeding

### Phase 2 (Near Term - 2-3 weeks)
4. Artifact passing between jobs
5. Generalized metrics system
6. Hooks framework

### Phase 3 (Medium Term - 2-3 weeks)
7. Custom runners (Docker, Singularity)
8. Tool-based log parsers
9. Non-environment variable parameters
10. Complete Hub functionality

---

*These incomplete features represent significant value-add opportunities. Prioritize based on user needs and use cases.*
