# Testing Improvements

**Priority Level:** HIGH
**Estimated Effort:** 2-3 weeks
**Action:** Expand test coverage systematically

---

## Table of Contents

1. [Test Coverage Gaps](#1-test-coverage-gaps)
2. [Test Quality Improvements](#2-test-quality-improvements)
3. [Integration Testing](#3-integration-testing)
4. [Performance Testing](#4-performance-testing)
5. [CI/CD Setup](#5-cicd-setup)

---

## 1. Test Coverage Gaps

### Current Coverage Status

**Tested Components (Good coverage):**
- ✅ Tier (389 lines) - [tests/test_tier.py](../tests/test_tier.py)
- ✅ Wrapper (374 lines) - [tests/test_wrapper.py](../tests/test_wrapper.py)
- ✅ LocalScheduler - [tests/test_local_scheduler.py](../tests/test_local_scheduler.py)
- ✅ Job specs - [tests/specs/](../tests/specs/)
- ✅ Common modules - [tests/common/](../tests/common/)

**Missing or Incomplete Coverage:**

### Gap 1.1: Slurm Scheduler
**Priority:** High | **Effort:** Medium | **Risk:** High

**Location:** [gator/scheduler/slurm.py](../gator/scheduler/slurm.py) (271 lines)

**Description:**
No test file exists for the Slurm scheduler, which handles cluster integration.

**Recommended Tests:**
```python
# tests/scheduler/test_slurm_scheduler.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from gator.scheduler.slurm import SlurmScheduler

@pytest.mark.asyncio
async def test_slurm_authentication():
    """Test JWT authentication with Slurm REST API"""
    scheduler = SlurmScheduler(
        url="http://localhost:8080",
        username="test_user",
        token="test_token"
    )

    with patch('aiohttp.ClientSession.post') as mock_post:
        mock_post.return_value.__aenter__.return_value.json = AsyncMock(
            return_value={'token': 'jwt_token'}
        )
        await scheduler._SlurmScheduler__authenticate()
        assert scheduler.jwt_token == 'jwt_token'

@pytest.mark.asyncio
async def test_slurm_token_refresh():
    """Test automatic token refresh on expiry"""
    scheduler = SlurmScheduler(...)
    # Simulate expired token
    scheduler.authenticated_at = time.time() - 10000
    # Trigger operation that checks token
    await scheduler._SlurmScheduler__check_token()
    # Verify token was refreshed

@pytest.mark.asyncio
async def test_slurm_job_submission():
    """Test job submission to Slurm cluster"""
    scheduler = SlurmScheduler(...)
    task = MagicMock(ident="test_job")

    with patch.object(scheduler, '_retry_post') as mock_post:
        mock_post.return_value = {'job_id': '12345'}
        await scheduler.launch(task)
        assert task.ident in scheduler.submitted_jobs

@pytest.mark.asyncio
async def test_slurm_job_status_polling():
    """Test polling for job status"""
    scheduler = SlurmScheduler(...)
    # Add mock submitted job
    scheduler.submitted_jobs['test'] = {'job_id': '12345'}

    with patch.object(scheduler, '_retry_get') as mock_get:
        mock_get.return_value = {
            'jobs': [{'job_id': '12345', 'job_state': 'COMPLETED'}]
        }
        await scheduler.wait([MagicMock(ident='test')])

@pytest.mark.asyncio
async def test_slurm_concurrent_token_refresh():
    """Test race condition handling in token refresh"""
    # Test that concurrent operations don't cause multiple refreshes

@pytest.mark.asyncio
async def test_slurm_retry_on_api_failure():
    """Test retry logic when Slurm API fails"""

@pytest.mark.asyncio
async def test_slurm_error_handling():
    """Test error handling for various Slurm errors"""
```

---

### Gap 1.2: Hub Components
**Priority:** High | **Effort:** Large | **Risk:** Medium

**Locations:**
- [gator/hub/app.py](../gator/hub/app.py) - Quart application
- [gator/hub/models.py](../gator/hub/models.py) - Database models

**Recommended Tests:**
```python
# tests/hub/test_hub_app.py
import pytest
from gator.hub.app import app

@pytest.fixture
async def test_client():
    """Create test client for Hub app"""
    async with app.test_client() as client:
        yield client

@pytest.mark.asyncio
async def test_register_job(test_client):
    """Test job registration endpoint"""
    response = await test_client.post('/jobs', json={
        'ident': 'test_job',
        'status': 'running'
    })
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_query_jobs(test_client):
    """Test job query endpoint"""
    response = await test_client.get('/jobs')
    assert response.status_code == 200
    data = await response.json
    assert isinstance(data, list)

@pytest.mark.asyncio
async def test_get_job_tree(test_client):
    """Test job tree retrieval"""

@pytest.mark.asyncio
async def test_websocket_updates(test_client):
    """Test WebSocket updates to frontend"""

# tests/hub/test_hub_models.py
@pytest.mark.asyncio
async def test_job_model_creation():
    """Test creating job database records"""

@pytest.mark.asyncio
async def test_job_model_relationships():
    """Test parent-child job relationships"""
```

---

### Gap 1.3: Babysitter Module
**Priority:** Medium | **Effort:** Small | **Risk:** Low

**Location:** [gator/babysitter.py](../gator/babysitter.py)

**Recommended Tests:**
```python
# tests/test_babysitter.py
@pytest.mark.asyncio
async def test_babysitter_monitors_process():
    """Test babysitter wraps and monitors child process"""

@pytest.mark.asyncio
async def test_babysitter_captures_output():
    """Test babysitter captures stdout/stderr"""

@pytest.mark.asyncio
async def test_babysitter_handles_crash():
    """Test babysitter detects process crashes"""
```

---

### Gap 1.4: Launch Progress Module
**Priority:** Low-Medium | **Effort:** Small | **Risk:** Low

**Location:** [gator/common/progress.py](../gator/common/progress.py)

**Recommended Tests:**
```python
# tests/common/test_progress.py
def test_progress_bar_rendering():
    """Test progress bar renders correctly"""

def test_progress_bar_updates():
    """Test progress bar updates with job status"""

def test_progress_bar_completion():
    """Test progress bar shows completion correctly"""
```

---

### Gap 1.5: HTTP API Client
**Priority:** Medium | **Effort:** Small | **Risk:** Medium

**Location:** [gator/common/http_api.py](../gator/common/http_api.py)

**Recommended Tests:**
```python
# tests/common/test_http_api.py
@pytest.mark.asyncio
async def test_http_get_success():
    """Test successful GET request"""

@pytest.mark.asyncio
async def test_http_get_retry():
    """Test GET request retries on failure"""

@pytest.mark.asyncio
async def test_http_post_success():
    """Test successful POST request"""

@pytest.mark.asyncio
async def test_http_backoff():
    """Test exponential backoff between retries"""
```

---

## 2. Test Quality Improvements

### Issue 2.1: Add Property-Based Testing
**Value:** High | **Effort:** Medium | **Tool:** Hypothesis

**Description:**
Use property-based testing to discover edge cases.

**Implementation:**
```python
# tests/test_properties.py
from hypothesis import given, strategies as st
from gator.specs.jobs import Job

@given(
    command=st.text(min_size=1, max_size=100),
    args=st.lists(st.text(max_size=50), max_size=10)
)
def test_job_spec_validation(command, args):
    """Test job spec validation with random inputs"""
    job = Job(ident="test", command=command, args=args)
    try:
        job.check()
        # If check passes, job should be valid
        assert job.command
    except SpecError:
        # Invalid specs should raise SpecError
        pass

@given(
    concurrency=st.integers(min_value=1, max_value=1000)
)
@pytest.mark.asyncio
async def test_scheduler_concurrency_limits(concurrency):
    """Test scheduler handles various concurrency levels"""
    scheduler = LocalScheduler(concurrency=concurrency)
    # Should never launch more than concurrency jobs
```

---

### Issue 2.2: Add Stress Testing
**Value:** Medium | **Effort:** Medium | **Focus:** Scalability

**Description:**
Test system behavior under heavy load.

**Implementation:**
```python
# tests/stress/test_load.py
@pytest.mark.slow
@pytest.mark.asyncio
async def test_many_concurrent_jobs():
    """Test system with 1000 concurrent jobs"""
    job_count = 1000
    spec = create_job_array_spec(count=job_count)
    result = await launch(spec)
    assert result.completed == job_count

@pytest.mark.slow
@pytest.mark.asyncio
async def test_deep_job_hierarchy():
    """Test deeply nested job groups (100 levels)"""
    spec = create_nested_groups(depth=100)
    result = await launch(spec)
    assert result.result == JobResult.SUCCESS

@pytest.mark.slow
@pytest.mark.asyncio
async def test_high_message_throughput():
    """Test WebSocket message handling under load"""
    # Send 10,000 messages/second
    # Verify no messages lost
    # Verify latency acceptable
```

---

### Issue 2.3: Add Mutation Testing
**Value:** Medium | **Effort:** Medium | **Tool:** mutmut

**Description:**
Use mutation testing to verify test quality.

**Setup:**
```bash
# Install mutmut
poetry add --dev mutmut

# Run mutation testing
mutmut run --paths-to-mutate=gator/
mutmut results
mutmut html  # Generate HTML report
```

---

### Issue 2.4: Improve Test Fixtures
**Value:** Medium | **Effort:** Small | **Focus:** Reusability

**Description:**
Create shared fixtures for common test scenarios.

**Implementation:**
```python
# tests/conftest.py
import pytest
from pathlib import Path
from gator.specs.jobs import Job, JobGroup

@pytest.fixture
def temp_tracking_dir(tmp_path):
    """Create temporary tracking directory"""
    tracking = tmp_path / ".gator"
    tracking.mkdir()
    return tracking

@pytest.fixture
def simple_job_spec():
    """Create simple job specification"""
    return Job(
        ident="test_job",
        command="echo",
        args=["hello"]
    )

@pytest.fixture
def job_group_spec():
    """Create job group with dependencies"""
    return JobGroup(
        ident="test_group",
        jobs=[
            Job(ident="job1", command="echo", args=["1"]),
            Job(
                ident="job2",
                command="echo",
                args=["2"],
                depends=[Dependency(target="job1", on="pass")]
            )
        ]
    )

@pytest.fixture
async def mock_logger():
    """Create mock logger"""
    logger = AsyncMock()
    logger.debug = AsyncMock()
    logger.info = AsyncMock()
    logger.warning = AsyncMock()
    logger.error = AsyncMock()
    return logger

@pytest.fixture
async def mock_scheduler():
    """Create mock scheduler"""
    scheduler = AsyncMock()
    scheduler.launch = AsyncMock()
    scheduler.wait = AsyncMock()
    return scheduler
```

---

## 3. Integration Testing

### Issue 3.1: End-to-End Tests
**Priority:** High | **Effort:** Medium | **Value:** High

**Description:**
Test complete workflows from CLI to completion.

**Implementation:**
```python
# tests/integration/test_e2e.py
import subprocess

@pytest.mark.integration
def test_cli_simple_job():
    """Test running simple job via CLI"""
    result = subprocess.run(
        ['python', '-m', 'gator', 'examples/simple.yaml'],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "Task completed" in result.stdout

@pytest.mark.integration
def test_cli_job_group_with_dependencies():
    """Test job group with dependencies"""
    result = subprocess.run(
        ['python', '-m', 'gator', 'examples/dependencies.yaml'],
        capture_output=True
    )
    assert result.returncode == 0

@pytest.mark.integration
def test_cli_job_array():
    """Test job array execution"""
    result = subprocess.run(
        ['python', '-m', 'gator', 'examples/array.yaml'],
        capture_output=True
    )
    assert result.returncode == 0

@pytest.mark.integration
@pytest.mark.slow
def test_hub_integration():
    """Test full Hub integration"""
    # Start Hub server
    # Register job
    # Query job status
    # Verify WebSocket updates
```

---

### Issue 3.2: Database Integration Tests
**Priority:** Medium | **Effort:** Small | **Value:** Medium

**Implementation:**
```python
# tests/integration/test_database.py
@pytest.mark.asyncio
async def test_database_full_lifecycle():
    """Test complete database lifecycle"""
    db = Database(path=":memory:")
    await db.setup()

    # Push entries
    await db.push_metric(Metric(...))
    await db.push_logentry(LogEntry(...))
    await db.push_procstat(ProcStat(...))

    # Query entries
    metrics = await db.get_metric("test_metric")
    assert len(metrics) > 0

    # Update entries
    await db.update_metric(...)

    await db.teardown()
```

---

## 4. Performance Testing

### Issue 4.1: Benchmarking Suite
**Priority:** Medium | **Effort:** Medium | **Value:** Medium

**Description:**
Create benchmark suite to track performance over time.

**Implementation:**
```python
# tests/benchmarks/test_performance.py
import pytest

@pytest.mark.benchmark
def test_job_launch_overhead(benchmark):
    """Measure overhead of launching simple job"""
    result = benchmark(launch_simple_job)
    assert result.duration < 1.0  # Should launch in < 1 second

@pytest.mark.benchmark
@pytest.mark.asyncio
async def test_websocket_throughput(benchmark):
    """Measure WebSocket message throughput"""
    result = await benchmark(send_many_messages, count=10000)
    assert result.messages_per_second > 1000

@pytest.mark.benchmark
def test_database_write_performance(benchmark):
    """Measure database write performance"""
    result = benchmark(write_many_logs, count=10000)
    assert result.writes_per_second > 5000
```

---

## 5. CI/CD Setup

### Issue 5.1: GitHub Actions Workflow
**Priority:** High | **Effort:** Small | **Value:** High

**Description:**
Set up automated testing in CI/CD pipeline.

**Implementation:**
```yaml
# .github/workflows/test.yml
name: Test Suite

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest]
        python-version: ["3.11", "3.12"]

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install Poetry
        run: |
          curl -sSL https://install.python-poetry.org | python3 -
          echo "$HOME/.local/bin" >> $GITHUB_PATH

      - name: Install dependencies
        run: poetry install

      - name: Run linting
        run: |
          poetry run ruff check gator/
          poetry run ruff format --check gator/

      - name: Run type checking
        run: poetry run mypy gator/

      - name: Run tests
        run: |
          poetry run pytest \
            --cov=gator \
            --cov-report=xml \
            --cov-report=html \
            --cov-report=term \
            -v

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
          flags: unittests
          name: codecov-${{ matrix.os }}-py${{ matrix.python-version }}

  integration:
    runs-on: ubuntu-latest
    needs: test

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: poetry install

      - name: Run integration tests
        run: poetry run pytest -m integration -v

      - name: Run slow tests
        run: poetry run pytest -m slow -v

  security:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Run security scan
        uses: pypa/gh-action-pip-audit@v1

      - name: Run Bandit
        run: |
          pip install bandit
          bandit -r gator/ -f json -o bandit-report.json

      - name: Upload security reports
        uses: actions/upload-artifact@v3
        with:
          name: security-reports
          path: bandit-report.json
```

---

### Issue 5.2: Pre-commit Hooks Enhancement
**Priority:** Medium | **Effort:** Small | **Value:** Medium

**Description:**
Enhance pre-commit hooks to run tests locally.

**Implementation:**
```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: unit-tests
        name: Run unit tests
        entry: poetry run pytest tests/ -x --tb=short
        language: system
        pass_filenames: false
        stages: [commit]

      - id: type-check
        name: Run mypy
        entry: poetry run mypy gator/
        language: system
        types: [python]
        pass_filenames: false
```

---

## 6. Test Documentation

### Issue 6.1: Testing Guide
**Priority:** Low-Medium | **Effort:** Small | **Value:** Medium

**Description:**
Create comprehensive testing documentation.

**Content:**
```markdown
# Testing Guide

## Running Tests

# Run all tests
poetry run pytest

# Run specific test file
poetry run pytest tests/test_tier.py

# Run with coverage
poetry run pytest --cov=gator --cov-report=html

# Run only fast tests
poetry run pytest -m "not slow"

# Run integration tests
poetry run pytest -m integration

## Writing Tests

### Unit Tests
- Test single functions/methods in isolation
- Use mocks for external dependencies
- Fast execution (<100ms per test)

### Integration Tests
- Test component interactions
- Use real dependencies when possible
- Mark with @pytest.mark.integration

### Test Organization
- Mirror source structure in tests/
- One test file per source file
- Group related tests in classes
```

---

## Summary Table

| Area | Priority | Effort | Current Coverage | Target Coverage |
|------|----------|--------|------------------|-----------------|
| Slurm Scheduler | High | Medium | 0% | 80%+ |
| Hub Components | High | Large | 10% | 70%+ |
| Babysitter | Medium | Small | 0% | 80%+ |
| HTTP API | Medium | Small | 0% | 90%+ |
| Core Components | Low | Small | 80% | 90%+ |

**Total Estimated Effort:** 2-3 weeks

**Priority Order:**
1. Set up CI/CD pipeline (immediate)
2. Add Slurm scheduler tests (high risk area)
3. Add Hub component tests (user-facing)
4. Improve test fixtures and utilities (quality of life)
5. Add integration tests (confidence)
6. Add performance benchmarks (ongoing)

---

*Comprehensive testing is critical for production readiness. Prioritize high-risk areas first.*
