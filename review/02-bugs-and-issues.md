# Bugs and Issues

**Priority Level:** HIGH to MEDIUM
**Estimated Effort:** 1-2 weeks
**Action:** Address in next sprint

---

## Table of Contents

1. [Hardcoded Retry Count](#1-hardcoded-retry-count)
2. [Synchronous Sleep in Async Context](#2-synchronous-sleep-in-async-context)
3. [Unclear Error Messages](#3-unclear-error-messages)
4. [Inefficient String Operations](#4-inefficient-string-operations)
5. [Hardcoded Sleep Duration](#5-hardcoded-sleep-duration)
6. [Unused Variable Deletion](#6-unused-variable-deletion)
7. [Inconsistent Error Handling](#7-inconsistent-error-handling)
8. [Missing Validation](#8-missing-validation)

---

## ✅ DONE: 1. Hardcoded Retry Count

### Issue: POST Method Uses Hardcoded Retry Count
**Severity:** Medium
**Effort:** Small
**Bug Type:** Configuration inconsistency

**Location:** [gator/common/http_api.py:90](../gator/common/http_api.py#L90)

**Description:**
The `post()` method hardcodes `range(10)` for retries, while the GET method correctly uses `self.retries`. This creates inconsistent behavior and ignores the configured retry setting.

**Current Code:**
```python
async def post(self, route: str, data: Dict[str, Any] = {}) -> Dict[str, Any]:
    # ...
    for attempt in range(10):  # ❌ Hardcoded, should use self.retries
        try:
            async with self.session.post(url, json=data, headers=headers) as response:
                # ...
```

**Compare with GET method:**
```python
async def get(self, route: str) -> Dict[str, Any]:
    # ...
    for attempt in range(self.retries):  # ✅ Correctly uses self.retries
        try:
            async with self.session.get(url, headers=headers) as response:
                # ...
```

**Recommended Fix:**
```python
async def post(self, route: str, data: Dict[str, Any] = {}) -> Dict[str, Any]:
    # Build URL
    url = f"{self.url}/{route.lstrip('/')}"
    # Log
    await self.logger.debug(f"HTTP POST: {url}")
    # Iterate over retries
    for attempt in range(self.retries):  # ✅ Now consistent with GET
        try:
            async with self.session.post(url, json=data, headers=headers) as response:
                # Handle response...
                if response.status == 200:
                    return await response.json()
                else:
                    raise Exception(f"HTTP {response.status}")
        except Exception as error:
            # Log and retry
            await self.logger.warning(f"POST attempt {attempt + 1}/{self.retries} failed: {error}")
            if attempt == self.retries - 1:
                raise
            await asyncio.sleep(self.backoff * (2**attempt))
```

**Impact:**
- ✅ Consistent retry behavior across GET and POST
- ✅ Respects configured retry count
- ✅ Easier to configure for different environments
- ✅ Better error handling control

---

## ✅ DONE: 2. Synchronous Sleep in Async Context

### Issue: Blocking Operations in Async Contexts
**Severity:** Medium
**Effort:** Small
**Bug Type:** Performance/Blocking

**Original Location:** [gator/common/progress.py:186](../gator/common/progress.py#L186)

**Description:**
The progress bar demo code used `time.sleep(0.25)` instead of `await asyncio.sleep(0.25)`. A thorough investigation revealed multiple blocking operations in async contexts throughout the codebase that could block the entire event loop.

**Problem:**
In an async application, blocking operations prevent:
- WebSocket message processing
- Database operations
- Other concurrent tasks
- Can cause timeouts and degraded performance

**Fixed Locations:**
1. **[gator/common/progress.py:187](../gator/common/progress.py#L187)** - Changed `time.sleep(0.25)` to `await asyncio.sleep(0.25)` in demo code
2. **[gator/common/ws_server.py:61](../gator/common/ws_server.py#L61)** - Fixed blocking `socket.getfqdn()` using `run_in_executor()`
3. **[gator/common/ws_server.py:66](../gator/common/ws_server.py#L66)** - Fixed blocking `socket.gethostbyname_ex()` using `run_in_executor()`
4. **[gator/common/ws_server.py:73-78](../gator/common/ws_server.py#L73-L78)** - Fixed blocking socket operations using `run_in_executor()`
5. **[gator/common/ws_server.py:124-131](../gator/common/ws_server.py#L124-L131)** - Fixed blocking socket bind/setsockopt using `run_in_executor()`
6. **[gator/wrapper.py:298](../gator/wrapper.py#L298)** - Fixed blocking `socket.getfqdn()` using `run_in_executor()`
7. **[gator/wrapper.py:134-137](../gator/wrapper.py#L134-L137)** - Fixed blocking file open in `__monitor_stdio()` using `run_in_executor()`
8. **[gator/wrapper.py:144](../gator/wrapper.py#L144)** - Fixed blocking file writes in `__monitor_stdio()` using `run_in_executor()`
9. **[gator/wrapper.py:153-154](../gator/wrapper.py#L153-L154)** - Fixed blocking file flush/close using `run_in_executor()`
10. **[gator/common/layer.py:288-291](../gator/common/layer.py#L288-L291)** - Fixed blocking `mkdir()` using `run_in_executor()`
11. **[gator/common/layer.py:296-299](../gator/common/layer.py#L296-L299)** - Fixed blocking `write_text()` using `run_in_executor()`
12. **[gator/common/logger.py:197](../gator/common/logger.py#L197)** - Fixed blocking file writes in `log()` using `run_in_executor()`

**Solution Applied:**
All blocking I/O and system calls in async contexts now use `asyncio.get_event_loop().run_in_executor()`:
```python
# Example for socket operations
loop = asyncio.get_event_loop()
hostname = await loop.run_in_executor(None, socket.getfqdn)

# Example for file I/O
def _write_file():
    path.write_text(content)
await loop.run_in_executor(None, _write_file)
```

**Additional Fixes:**
- Added missing `completed` property to `PassFailBar` class (was causing AttributeError)
- Converted demo code to proper async pattern using `asyncio.run(main())`

**Tests Added:**
- **[tests/common/test_progress.py](../tests/common/test_progress.py)** - 9 tests for progress bar functionality and async behavior
- **[tests/test_async_blocking.py](../tests/test_async_blocking.py)** - 4 comprehensive tests verifying non-blocking behavior across socket, file I/O, and logging operations

**Test Results:**
- ✅ All 184 tests pass
- ✅ All Ruff linter checks pass
- ✅ Code coverage: 74%

**Impact:**
- ✅ Non-blocking progress updates
- ✅ Better async performance throughout the application
- ✅ Prevents event loop stalls
- ✅ More responsive application
- ✅ Proper concurrency for WebSocket, database, and other async operations

---

## 3. Unclear Error Messages

### Issue: Cryptic RuntimeError Messages
**Severity:** Low-Medium
**Effort:** Small
**Bug Type:** Developer Experience

**Location:** [gator/common/db_client.py:205](../gator/common/db_client.py#L205)

**Description:**
The error message "No Exist" is unclear and doesn't provide enough context for debugging.

**Current Code:**
```python
async def get_tree(self) -> Dict[str, Any]:
    raise RuntimeError("No Exist")  # ❌ Unclear what doesn't exist
```

**Recommended Fix:**
```python
async def get_tree(self) -> Dict[str, Any]:
    raise NotImplementedError(
        "get_tree() is not supported for database clients. "
        "Tree traversal requires WebSocket connections to child jobs."
    )
```

**Alternative (if it's truly a runtime error):**
```python
async def get_tree(self) -> Dict[str, Any]:
    raise RuntimeError(
        "Cannot retrieve job tree: database client does not support tree operations. "
        "Ensure job has an active WebSocket connection."
    )
```

**Impact:**
- ✅ Clear error messages for debugging
- ✅ Helps users understand the issue
- ✅ Reduces support burden
- ✅ Professional error handling

### Related Issue: Unclear Validation Error
**Location:** [gator/common/db_client.py:51](../gator/common/db_client.py#L51)

**Current Code:**
```python
else:
    raise RuntimeError(f"Can't resolve job {job}")  # ❌ Why can't it resolve?
```

**Recommended Fix:**
```python
else:
    raise RuntimeError(
        f"Cannot resolve job {job.get('ident', 'unknown')}: "
        f"job must have either 'ws' (WebSocket) or 'db_file' (database) attribute"
    )
```

---

## 4. Inefficient String Operations

### Issue: Inefficient Timestamp Formatting
**Severity:** Low
**Effort:** Small
**Bug Type:** Performance/Code Quality

**Location:** [gator/wrapper.py:343](../gator/wrapper.py#L343)

**Description:**
Uses string manipulation to format duration instead of proper timedelta formatting.

**Current Code:**
```python
elapsed = str(stopped_at - started_at).split(".")[0]  # ❌ Inefficient string parsing
```

**Recommended Fix:**
```python
# Option 1: Use timedelta's total_seconds()
from datetime import timedelta

elapsed = timedelta(seconds=int((stopped_at - started_at).total_seconds()))
elapsed_str = str(elapsed)  # Clean HH:MM:SS format

# Option 2: Custom formatting for better control
def format_duration(delta: timedelta) -> str:
    """Format timedelta as HH:MM:SS"""
    total_seconds = int(delta.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

elapsed_str = format_duration(stopped_at - started_at)
```

**Impact:**
- ✅ More efficient
- ✅ More readable
- ✅ Better control over formatting
- ✅ Easier to maintain

---

## 5. Hardcoded Sleep Duration

### Issue: Magic Number Sleep Duration
**Severity:** Low
**Effort:** Small
**Bug Type:** Configuration

**Location:** [gator/scheduler/slurm.py:251](../gator/scheduler/slurm.py#L251)

**Description:**
The Slurm scheduler uses a hardcoded 5-second sleep in the job wait loop, making it difficult to tune performance.

**Current Code:**
```python
async def wait(self, children: List[Child]) -> None:
    while <condition>:
        # ... check job status ...
        await asyncio.sleep(5)  # ❌ Hardcoded polling interval
```

**Recommended Fix:**
```python
class SlurmScheduler(BaseScheduler):
    def __init__(self, *args, polling_interval: float = 5.0, **kwargs):
        super().__init__(*args, **kwargs)
        self.polling_interval = polling_interval

    async def wait(self, children: List[Child]) -> None:
        while <condition>:
            # ... check job status ...
            await asyncio.sleep(self.polling_interval)  # ✅ Configurable
```

**Configuration:**
```python
# Allow CLI override
@click.option('--slurm-poll-interval', default=5.0, help='Slurm job polling interval in seconds')
def main(slurm_poll_interval, ...):
    if scheduler_type == 'slurm':
        scheduler = SlurmScheduler(polling_interval=slurm_poll_interval)
```

**Impact:**
- ✅ Configurable polling rate
- ✅ Can optimize for different cluster sizes
- ✅ Faster feedback in dev environments
- ✅ Reduced API load in production

---

## 6. Unused Variable Deletion

### Issue: Immediately Deleted Variable
**Severity:** Low
**Effort:** Small
**Bug Type:** Code smell

**Location:** [gator/launch.py:58](../gator/launch.py#L58)

**Description:**
The `glyph` parameter is imported then immediately deleted, suggesting unclear design intent.

**Current Code:**
```python
def launch(spec_path, spec, ws, level, ident, glyph, track, interval) -> Summary:
    # ... other code ...
    del glyph  # ❌ Why import it if we're going to delete it?
```

**Analysis:**
This pattern suggests one of these scenarios:
1. The parameter was used previously but is now obsolete
2. The parameter is needed by the interface but not the implementation
3. The parameter should be used but the implementation is incomplete

**Recommended Approaches:**

**Option 1: Remove if truly unused**
```python
def launch(spec_path, spec, ws, level, ident, track, interval) -> Summary:
    # Simply remove the parameter
```

**Option 2: Mark as intentionally unused**
```python
def launch(spec_path, spec, ws, level, ident, glyph, track, interval) -> Summary:
    # Use underscore prefix to indicate intentionally unused
    _ = glyph  # Explicitly mark as unused for interface compatibility
```

**Option 3: If it should be used**
```python
def launch(spec_path, spec, ws, level, ident, glyph, track, interval) -> Summary:
    # Actually use the glyph parameter
    logger = Logger(console=..., glyph=glyph)  # Example usage
```

**Impact:**
- ✅ Clearer code intent
- ✅ Removes confusion
- ✅ Better maintainability

---

## 7. Inconsistent Error Handling

### Issue: Broad Exception Catching
**Severity:** Medium
**Effort:** Small
**Bug Type:** Error handling

**Locations:**
- [gator/wrapper.py:228](../gator/wrapper.py#L228)
- [gator/common/ws_wrapper.py:104](../gator/common/ws_wrapper.py#L104)
- [gator/common/ws_wrapper.py:113](../gator/common/ws_wrapper.py#L113)

**Description:**
Multiple locations catch broad `Exception` or `BaseException` without specific handling, making it difficult to understand what errors are expected and how they should be handled.

**Current Code (Wrapper):**
```python
try:
    # ... subprocess code ...
except Exception:
    pass  # ❌ What exceptions are we expecting?
```

**Current Code (WebSocket):**
```python
try:
    await self._websocket.send(payload)
except Exception:  # ❌ Too broad
    pass
```

**Recommended Fix:**
```python
# Wrapper - Be specific about what can fail
try:
    # ... subprocess code ...
except subprocess.SubprocessError as e:
    await self.logger.error(f"Subprocess error: {e}")
except OSError as e:
    await self.logger.error(f"OS error launching process: {e}")
except Exception as e:
    await self.logger.error(f"Unexpected error: {e}")
    raise  # Re-raise unexpected errors

# WebSocket - Handle connection errors specifically
from websockets.exceptions import ConnectionClosed, WebSocketException

try:
    await self._websocket.send(payload)
except ConnectionClosed as e:
    await self.logger.warning(f"Connection closed: {e}")
    # Trigger reconnection logic
except WebSocketException as e:
    await self.logger.error(f"WebSocket error: {e}")
    raise
except Exception as e:
    await self.logger.error(f"Unexpected send error: {e}")
    raise
```

**Impact:**
- ✅ More specific error handling
- ✅ Better debugging information
- ✅ Unexpected errors are visible
- ✅ Can handle different error types appropriately

---

## 8. Missing Validation

### Issue: No Input Validation for Job Specifications
**Severity:** Medium
**Effort:** Medium
**Bug Type:** Validation

**Locations:**
- [gator/specs/jobs.py](../gator/specs/jobs.py) - Job specification classes
- [gator/launch.py](../gator/launch.py) - Job launching

**Description:**
While there are `check()` methods in spec classes, there's limited validation for:
- Command injection patterns
- Path traversal in file paths
- Resource limit sanity checks
- Circular dependency detection
- Array index bounds

**Current Code:**
```python
class Job(SpecBase):
    def check(self):
        """Check spec is valid"""
        super().check()
        # ❌ No validation of command safety
        # ❌ No validation of args content
        # ❌ No validation of environment variables
```

**Recommended Additions:**

```python
import re
from pathlib import Path

class Job(SpecBase):
    # Dangerous patterns in commands/args
    DANGEROUS_PATTERNS = [
        r';.*rm\s+-rf',  # Command chaining with rm
        r'\|.*sh',       # Piping to shell
        r'`.*`',         # Command substitution
        r'\$\(.*\)',     # Command substitution
    ]

    def check(self):
        """Check spec is valid with security validation"""
        super().check()

        # Validate command exists and is executable
        if self.command:
            # Check for dangerous patterns
            for pattern in self.DANGEROUS_PATTERNS:
                if re.search(pattern, self.command):
                    raise SpecError(
                        f"Potentially dangerous command pattern detected: {pattern}"
                    )

        # Validate arguments
        if self.args:
            for arg in self.args:
                # Check each argument for dangerous patterns
                for pattern in self.DANGEROUS_PATTERNS:
                    if re.search(pattern, str(arg)):
                        raise SpecError(
                            f"Potentially dangerous argument pattern: {arg}"
                        )

        # Validate resource limits are reasonable
        if self.cores and self.cores > 1000:
            raise SpecError(f"Unreasonable core count: {self.cores}")

        if self.memory and self.memory > 1_000_000:  # > 1TB
            raise SpecError(f"Unreasonable memory allocation: {self.memory}MB")

        # Validate working directory
        if self.cwd:
            try:
                cwd_path = Path(self.cwd).resolve()
                if not cwd_path.exists():
                    self.logger.warning(f"Working directory does not exist: {self.cwd}")
            except Exception as e:
                raise SpecError(f"Invalid working directory: {e}")
```

**Array Validation:**
```python
class JobArray(SpecBase):
    def check(self):
        """Check array spec with bounds validation"""
        super().check()

        # Validate array range
        if self.start is not None and self.stop is not None:
            if self.start >= self.stop:
                raise SpecError(
                    f"Array start ({self.start}) must be less than stop ({self.stop})"
                )

            # Check for unreasonable array sizes
            array_size = self.stop - self.start
            if array_size > 100_000:
                raise SpecError(
                    f"Array size too large: {array_size}. "
                    "Consider splitting into smaller arrays."
                )
```

**Dependency Validation:**
```python
class JobGroup(SpecBase):
    def check(self):
        """Check group spec with dependency validation"""
        super().check()

        # Build dependency graph
        graph = self._build_dependency_graph()

        # Check for circular dependencies
        if self._has_cycle(graph):
            raise SpecError("Circular dependency detected in job group")

        # Check all dependencies reference valid jobs
        all_jobs = {job.label for job in self.jobs}
        for job in self.jobs:
            for dep in job.depends:
                if dep.target not in all_jobs:
                    raise SpecError(
                        f"Job '{job.label}' depends on unknown job '{dep.target}'"
                    )

    def _build_dependency_graph(self) -> Dict[str, List[str]]:
        """Build adjacency list for dependency graph"""
        graph = defaultdict(list)
        for job in self.jobs:
            for dep in job.depends:
                graph[job.label].append(dep.target)
        return graph

    def _has_cycle(self, graph: Dict[str, List[str]]) -> bool:
        """Detect cycles using DFS"""
        visited = set()
        rec_stack = set()

        def dfs(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)

            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        for node in graph:
            if node not in visited:
                if dfs(node):
                    return True
        return False
```

**Impact:**
- ✅ Prevents invalid configurations
- ✅ Catches errors early
- ✅ Better security
- ✅ Clearer error messages
- ✅ Prevents runtime failures

---

## Summary Table

| Issue | Location | Severity | Effort | Impact |
|-------|----------|----------|--------|--------|
| Hardcoded retry count | http_api.py:90 | Medium | Small | Consistency |
| Synchronous sleep | progress.py:186 | Medium | Small | Performance |
| Unclear errors | db_client.py:205 | Low-Medium | Small | DX |
| Inefficient strings | wrapper.py:343 | Low | Small | Performance |
| Hardcoded sleep | slurm.py:251 | Low | Small | Flexibility |
| Unused variable | launch.py:58 | Low | Small | Code smell |
| Broad exceptions | Multiple | Medium | Small | Debugging |
| Missing validation | specs/*.py | Medium | Medium | Security |

**Total Estimated Effort:** 1-2 weeks

**Priority Order:**
1. Fix hardcoded retry count (quick win)
2. Fix synchronous sleep (blocking issue)
3. Add input validation (security)
4. Improve error messages (debugging)
5. Fix broad exception handling (debugging)
6. Optimize string operations (performance)
7. Make sleep configurable (flexibility)
8. Clean up unused variables (code quality)

---

## Testing Requirements

Add tests for these fixes:

```python
# test_bugs.py
async def test_post_retry_consistency():
    """Ensure POST and GET use same retry count"""

async def test_progress_non_blocking():
    """Ensure progress bar doesn't block event loop"""

async def test_input_validation():
    """Ensure dangerous inputs are rejected"""

async def test_dependency_cycle_detection():
    """Ensure circular dependencies are caught"""

async def test_error_messages_clear():
    """Ensure error messages provide useful context"""
```

---

*These issues should be addressed in the next development sprint to improve reliability and maintainability.*
