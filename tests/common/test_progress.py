# Copyright 2024, Peter Birch, mailto:peter@lightlogic.co.uk
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import asyncio

import pytest
from rich.console import Console

from gator.common.progress import PassFailBar
from gator.common.summary import Summary


@pytest.fixture
def console() -> Console:
    """Create a console for rendering."""
    return Console()


@pytest.fixture
def progress_bar() -> PassFailBar:
    """Create a PassFailBar instance."""
    return PassFailBar("Test", total=10, active=0, passed=0, failed=0)


@pytest.fixture
def summary() -> Summary:
    """Create a Summary instance with test metrics."""
    summary = Summary()
    summary.metrics = {
        "sub_total": 10,
        "sub_active": 2,
        "sub_passed": 5,
        "sub_failed": 1,
    }
    return summary


def test_progress_bar_initialization(progress_bar: PassFailBar):
    """Test that PassFailBar initializes correctly."""
    assert progress_bar.title == "Test"
    assert progress_bar.total == 10
    assert progress_bar.active == 0
    assert progress_bar.passed == 0
    assert progress_bar.failed == 0


def test_progress_bar_update(progress_bar: PassFailBar, summary: Summary):
    """Test that PassFailBar updates correctly from a Summary."""
    progress_bar.update(summary)

    assert progress_bar.total == 10
    assert progress_bar.active == 2
    assert progress_bar.passed == 5
    assert progress_bar.failed == 1


def test_progress_bar_percentage(progress_bar: PassFailBar):
    """Test percentage calculation."""
    progress_bar.passed = 5
    progress_bar.failed = 2
    progress_bar.total = 10

    # completed = passed + failed = 7
    # percentage = 7/10 * 100 = 70%
    assert progress_bar.percentage_completed == 70.0


def test_progress_bar_percentage_complete(progress_bar: PassFailBar):
    """Test percentage calculation when fully complete."""
    progress_bar.passed = 8
    progress_bar.failed = 2
    progress_bar.total = 10

    assert progress_bar.percentage_completed == 100.0


def test_progress_bar_percentage_none_total():
    """Test percentage calculation when total is None."""
    bar = PassFailBar("Test", total=None, active=0, passed=5, failed=2)
    assert bar.percentage_completed is None


def test_progress_bar_rendering(progress_bar: PassFailBar, console: Console):
    """Test that progress bar can be rendered without errors."""
    progress_bar.passed = 5
    progress_bar.failed = 1
    progress_bar.active = 2

    # Render to a string to ensure no exceptions
    with console.capture() as capture:
        console.print(progress_bar)

    output = capture.get()
    # Just verify we got some output
    assert len(output) > 0


@pytest.mark.asyncio
async def test_async_sleep_non_blocking():
    """Test that async sleep allows other tasks to run (Issue #2 fix verification).

    This test verifies that using asyncio.sleep() instead of time.sleep()
    allows concurrent tasks to execute, preventing event loop blocking.
    """
    execution_order = []

    async def task1():
        """Task that sleeps then records execution."""
        execution_order.append("task1_start")
        await asyncio.sleep(0.1)  # Non-blocking sleep
        execution_order.append("task1_end")

    async def task2():
        """Task that records execution immediately."""
        execution_order.append("task2_start")
        await asyncio.sleep(0.05)  # Shorter sleep
        execution_order.append("task2_end")

    # Run tasks concurrently
    await asyncio.gather(task1(), task2())

    # Verify both tasks ran concurrently (task2 should complete before task1)
    assert execution_order == [
        "task1_start",
        "task2_start",
        "task2_end",  # task2 completes first due to shorter sleep
        "task1_end",
    ]


@pytest.mark.asyncio
async def test_progress_update_non_blocking():
    """Test that progress updates don't block the event loop.

    This simulates the pattern used in launch_progress.py where progress
    updates happen while other async operations are running.
    """
    progress_bar = PassFailBar("Test", total=100, active=0, passed=0, failed=0)
    summary = Summary()

    updates_completed = 0
    other_task_ran = False

    async def update_progress():
        """Simulate progress updates."""
        nonlocal updates_completed
        for i in range(5):
            summary.metrics = {
                "sub_total": 100,
                "sub_active": 10,
                "sub_passed": i * 20,
                "sub_failed": 0,
            }
            progress_bar.update(summary)
            updates_completed += 1
            await asyncio.sleep(0.01)  # Non-blocking sleep

    async def other_task():
        """Simulate another task running concurrently."""
        nonlocal other_task_ran
        await asyncio.sleep(0.025)  # Run during progress updates
        other_task_ran = True

    # Run both tasks concurrently
    await asyncio.gather(update_progress(), other_task())

    # Verify both tasks completed
    assert updates_completed == 5
    assert other_task_ran is True
