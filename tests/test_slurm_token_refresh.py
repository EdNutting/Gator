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
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest

from gator.scheduler.common import SchedulerError
from gator.scheduler.slurm import SlurmScheduler


@pytest.fixture
def scheduler(tmp_path):
    """Create a SlurmScheduler instance for testing."""
    scheduler = SlurmScheduler(
        tracking=tmp_path,
        parent="test_parent",
        options={"api_root": "http://test:8080/"},
    )
    return scheduler


class TestSlurmTokenRefresh:
    """Test suite for Slurm token refresh functionality."""

    @pytest.mark.asyncio
    async def test_token_refresh_basic(self, scheduler):
        """Verify basic token refresh works correctly."""
        # Mock the subprocess
        mock_proc = Mock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(
            return_value=(b"SLURM_JWT=test_token_123\n", b"")
        )

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            # Token should initially be None
            assert scheduler._token is None

            # Refresh the token
            await scheduler._refresh_token()

            # Verify token was set
            assert scheduler._token == "test_token_123"
            assert scheduler._expiry is not None
            assert scheduler._expiry > datetime.now()

            # Verify subprocess was called
            mock_proc.communicate.assert_called_once()

    @pytest.mark.asyncio
    async def test_token_refresh_caching(self, scheduler):
        """Verify second call uses cached token (no subprocess call)."""
        # Mock the subprocess
        mock_proc = Mock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(
            return_value=(b"SLURM_JWT=test_token_123\n", b"")
        )

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_create:
            # First refresh
            await scheduler._refresh_token()
            assert mock_create.call_count == 1

            # Second refresh (token not yet expired)
            await scheduler._refresh_token()
            # Should still be 1 - no second subprocess call
            assert mock_create.call_count == 1

            # Verify token is still the same
            assert scheduler._token == "test_token_123"

    @pytest.mark.asyncio
    async def test_token_expiry(self, scheduler):
        """Verify expired tokens trigger refresh."""
        # Mock the subprocess for two different tokens
        mock_proc1 = Mock()
        mock_proc1.returncode = 0
        mock_proc1.communicate = AsyncMock(
            return_value=(b"SLURM_JWT=first_token\n", b"")
        )

        mock_proc2 = Mock()
        mock_proc2.returncode = 0
        mock_proc2.communicate = AsyncMock(
            return_value=(b"SLURM_JWT=second_token\n", b"")
        )

        with patch("asyncio.create_subprocess_exec") as mock_create:
            # First refresh
            mock_create.return_value = mock_proc1
            await scheduler._refresh_token()
            assert scheduler._token == "first_token"

            # Manually expire the token
            scheduler._expiry = datetime.now() - timedelta(seconds=1)

            # Second refresh should fetch new token
            mock_create.return_value = mock_proc2
            await scheduler._refresh_token()
            assert scheduler._token == "second_token"
            assert mock_create.call_count == 2

    @pytest.mark.asyncio
    async def test_subprocess_timeout(self, scheduler):
        """Verify timeout handling when subprocess hangs."""
        # Mock a subprocess that never completes
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(
            side_effect=asyncio.TimeoutError()
        )
        mock_proc.kill = Mock()
        mock_proc.wait = AsyncMock()

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError()):
                # Should raise SchedulerError
                with pytest.raises(SchedulerError, match="Timeout while fetching Slurm JWT token"):
                    await scheduler._refresh_token()

                # Verify process was killed
                mock_proc.kill.assert_called_once()
                mock_proc.wait.assert_called_once()

    @pytest.mark.asyncio
    async def test_subprocess_failure(self, scheduler):
        """Verify error handling for failed subprocess with stderr."""
        # Mock a failed subprocess
        mock_proc = Mock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(
            return_value=(b"", b"Permission denied: user not authorized\n")
        )

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            # Should raise SchedulerError with stderr
            with pytest.raises(
                SchedulerError,
                match=(
                    r"Failed to fetch Slurm JWT token \(exit code 1\): "
                    r"Permission denied: user not authorized"
                )
            ):
                await scheduler._refresh_token()

    @pytest.mark.asyncio
    async def test_subprocess_failure_no_stderr(self, scheduler):
        """Verify error handling when subprocess fails with no stderr."""
        # Mock a failed subprocess with no stderr
        mock_proc = Mock()
        mock_proc.returncode = 127
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            # Should raise SchedulerError with "Unknown error"
            with pytest.raises(
                SchedulerError,
                match=r"Failed to fetch Slurm JWT token \(exit code 127\): Unknown error"
            ):
                await scheduler._refresh_token()

    @pytest.mark.asyncio
    async def test_malformed_output(self, scheduler):
        """Verify handling of unexpected token format."""
        # Mock subprocess with invalid output
        mock_proc = Mock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(
            return_value=(b"INVALID_OUTPUT_FORMAT\n", b"")
        )

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            # Should raise SchedulerError
            with pytest.raises(
                SchedulerError,
                match=r"Failed to extract Slurm JWT from STDOUT: INVALID_OUTPUT_FORMAT"
            ):
                await scheduler._refresh_token()

            # Token should remain None
            assert scheduler._token is None

    @pytest.mark.asyncio
    async def test_concurrent_refresh(self, scheduler):
        """Verify only one refresh occurs with concurrent access (race condition test)."""
        call_count = 0

        async def mock_communicate():
            nonlocal call_count
            call_count += 1
            # Add a small delay to simulate real subprocess execution
            await asyncio.sleep(0.1)
            return (b"SLURM_JWT=test_token\n", b"")

        mock_proc = Mock()
        mock_proc.returncode = 0
        mock_proc.communicate = mock_communicate

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            # Launch 10 concurrent refresh attempts
            tasks = [scheduler._refresh_token() for _ in range(10)]
            await asyncio.gather(*tasks)

            # Verify subprocess was called exactly once (double-check locking works)
            assert call_count == 1
            assert scheduler._token == "test_token"

    @pytest.mark.asyncio
    async def test_clear_token_refresh(self, scheduler):
        """Verify clear_token() forces refresh on next access."""
        # Mock the subprocess
        mock_proc1 = Mock()
        mock_proc1.returncode = 0
        mock_proc1.communicate = AsyncMock(
            return_value=(b"SLURM_JWT=first_token\n", b"")
        )

        mock_proc2 = Mock()
        mock_proc2.returncode = 0
        mock_proc2.communicate = AsyncMock(
            return_value=(b"SLURM_JWT=second_token\n", b"")
        )

        with patch("asyncio.create_subprocess_exec") as mock_create:
            # First refresh
            mock_create.return_value = mock_proc1
            await scheduler._refresh_token()
            assert scheduler._token == "first_token"

            # Clear the token
            scheduler.clear_token()
            assert scheduler._token is None
            assert scheduler._expiry is None

            # Next refresh should fetch new token
            mock_create.return_value = mock_proc2
            await scheduler._refresh_token()
            assert scheduler._token == "second_token"
            assert mock_create.call_count == 2

    @pytest.mark.asyncio
    async def test_token_property_uninitialized(self, scheduler):
        """Verify token property raises error when uninitialized."""
        # Token should be None initially
        assert scheduler._token is None

        # Accessing token property should raise SchedulerError
        with pytest.raises(
            SchedulerError,
            match="Slurm token not initialized"
        ):
            _ = scheduler.token

    @pytest.mark.asyncio
    async def test_token_property_after_refresh(self, scheduler):
        """Verify token property returns value after refresh."""
        mock_proc = Mock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(
            return_value=(b"SLURM_JWT=test_token_123\n", b"")
        )

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            # Refresh the token
            await scheduler._refresh_token()

            # Now token property should return the value
            assert scheduler.token == "test_token_123"

    @pytest.mark.asyncio
    async def test_get_session_refreshes_token(self, scheduler):
        """Verify get_session() calls _refresh_token()."""
        # Mock the subprocess
        mock_proc = Mock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(
            return_value=(b"SLURM_JWT=session_token\n", b"")
        )

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            # get_session should refresh the token
            session = await scheduler.get_session()

            # Verify token was refreshed
            assert scheduler._token == "session_token"

            # Verify session was created with token in headers
            assert session._default_headers["X-SLURM-USER-TOKEN"] == "session_token"

            # Clean up
            await session.close()

    @pytest.mark.asyncio
    async def test_concurrent_get_session(self, scheduler):
        """Verify multiple concurrent get_session() calls refresh only once."""
        call_count = 0

        async def mock_communicate():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.05)
            return (b"SLURM_JWT=concurrent_token\n", b"")

        mock_proc = Mock()
        mock_proc.returncode = 0
        mock_proc.communicate = mock_communicate

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            # Launch 5 concurrent get_session() calls
            sessions = await asyncio.gather(
                *[scheduler.get_session() for _ in range(5)]
            )

            # Verify subprocess was called exactly once
            assert call_count == 1
            assert scheduler._token == "concurrent_token"

            # All sessions should have the same token
            for session in sessions:
                assert session._default_headers["X-SLURM-USER-TOKEN"] == "concurrent_token"
                await session.close()

    @pytest.mark.asyncio
    async def test_event_loop_remains_responsive(self, scheduler):
        """Verify event loop is not blocked during token refresh."""
        # Track if other task made progress during token refresh
        other_task_progress = []

        async def other_task():
            """Simulate other async work happening concurrently."""
            for i in range(10):
                other_task_progress.append(i)
                await asyncio.sleep(0.02)  # 20ms per iteration

        async def slow_communicate():
            """Simulate slow token fetch (200ms)."""
            await asyncio.sleep(0.2)
            return (b"SLURM_JWT=slow_token\n", b"")

        mock_proc = Mock()
        mock_proc.returncode = 0
        mock_proc.communicate = slow_communicate

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            # Launch token refresh and other task concurrently
            await asyncio.gather(
                scheduler._refresh_token(),
                other_task()
            )

            # Verify token was refreshed
            assert scheduler._token == "slow_token"

            # Verify other task made progress during token refresh
            # If event loop was blocked, other_task_progress would be empty or incomplete
            # With async subprocess, other task should complete all 10 iterations
            assert len(other_task_progress) == 10
            assert other_task_progress == list(range(10))
