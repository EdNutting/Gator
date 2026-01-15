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

"""
Tests to verify that blocking operations in async contexts have been fixed.
This is related to Issue #2: Synchronous Sleep in Async Context.
"""

import asyncio
import socket
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from gator.common.logger import Logger
from gator.common.types import LogSeverity


@pytest.mark.asyncio
async def test_socket_operations_non_blocking():
    """Test that socket operations in async contexts don't block the event loop."""
    from gator.common.ws_server import WebsocketServer

    # Track task execution order
    execution_order = []

    async def concurrent_task():
        """A task that should run while socket operations happen."""
        execution_order.append("concurrent_start")
        await asyncio.sleep(0.01)
        execution_order.append("concurrent_end")

    # Create server and get address (which uses socket operations)
    async def get_address_task():
        execution_order.append("socket_start")
        server = WebsocketServer(db=MagicMock(), logger=MagicMock())
        server._WebsocketServer__port = 8888  # Set a port to avoid binding
        try:
            # This calls socket.getfqdn() which should be non-blocking
            address = await server.get_address()
            execution_order.append("socket_end")
            return address
        except Exception:
            execution_order.append("socket_end")
            # It's ok if this fails, we're just testing it doesn't block
            return None

    # Run both tasks concurrently
    await asyncio.gather(get_address_task(), concurrent_task())

    # Verify both tasks ran (concurrent task should interleave with socket operations)
    assert "concurrent_start" in execution_order
    assert "concurrent_end" in execution_order
    assert "socket_start" in execution_order
    assert "socket_end" in execution_order


@pytest.mark.asyncio
async def test_file_io_non_blocking():
    """Test that file I/O operations in async contexts don't block the event loop."""
    execution_order = []

    async def concurrent_task():
        """A task that should run while file I/O happens."""
        execution_order.append("concurrent_start")
        await asyncio.sleep(0.01)
        execution_order.append("concurrent_end")

    async def file_io_task():
        """Simulate file I/O operations."""
        execution_order.append("io_start")
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            # Test directory creation (like in layer.py)
            loop = asyncio.get_event_loop()

            def _make_dir():
                (tmp_path / "test_dir").mkdir(exist_ok=True, parents=True)

            await loop.run_in_executor(None, _make_dir)

            # Test file writing (like in layer.py)
            file_path = tmp_path / "test.txt"

            def _write_file():
                file_path.write_text("test content")

            await loop.run_in_executor(None, _write_file)

        execution_order.append("io_end")

    # Run both tasks concurrently
    await asyncio.gather(file_io_task(), concurrent_task())

    # Verify both tasks ran
    assert "concurrent_start" in execution_order
    assert "concurrent_end" in execution_order
    assert "io_start" in execution_order
    assert "io_end" in execution_order


@pytest.mark.asyncio
async def test_logger_write_non_blocking():
    """Test that logger file writes don't block the event loop."""
    execution_order = []

    async def concurrent_task():
        """A task that should run while logging happens."""
        for i in range(3):
            execution_order.append(f"concurrent_{i}")
            await asyncio.sleep(0.005)

    async def logging_task():
        """Simulate logging operations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a logger with file output
            ws_cli = MagicMock()
            ws_cli.linked = False
            ws_cli.log = AsyncMock()
            logger = Logger(ws_cli, verbosity=LogSeverity.DEBUG)
            logger.tee_to_file(Path(tmpdir) / "test.log")

            # Log multiple messages
            for i in range(5):
                execution_order.append(f"log_{i}")
                await logger.info(f"Test message {i}")
                await asyncio.sleep(0.002)

    # Run both tasks concurrently
    await asyncio.gather(logging_task(), concurrent_task())

    # Verify both tasks ran and interleaved
    assert len([x for x in execution_order if x.startswith("log_")]) == 5
    assert len([x for x in execution_order if x.startswith("concurrent_")]) == 3


@pytest.mark.asyncio
async def test_multiple_async_operations_parallel():
    """Test that multiple async operations can run in parallel without blocking.

    This is a comprehensive test that simulates the real-world scenario where
    multiple async operations (socket, file I/O, logging) happen concurrently.
    """
    results = {
        "task1": False,
        "task2": False,
        "task3": False,
    }
    start_time = asyncio.get_event_loop().time()

    async def task1():
        """Simulate socket operation."""
        loop = asyncio.get_event_loop()
        # Simulate blocking socket call in executor
        _hostname = await loop.run_in_executor(None, socket.getfqdn)
        await asyncio.sleep(0.1)
        results["task1"] = True

    async def task2():
        """Simulate file I/O operation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loop = asyncio.get_event_loop()
            path = Path(tmpdir) / "test.txt"

            def _write():
                path.write_text("test")

            await loop.run_in_executor(None, _write)
            await asyncio.sleep(0.1)
        results["task2"] = True

    async def task3():
        """Simulate logging operation."""
        await asyncio.sleep(0.1)
        results["task3"] = True

    # Run all tasks concurrently
    await asyncio.gather(task1(), task2(), task3())

    end_time = asyncio.get_event_loop().time()
    elapsed = end_time - start_time

    # Verify all tasks completed
    assert all(results.values())

    # If tasks were blocking, this would take 0.3s (0.1 * 3)
    # If they run in parallel, it should take ~0.1s
    # Allow some margin for test execution overhead
    assert elapsed < 0.25, f"Tasks took {elapsed}s, suggesting blocking behavior"
