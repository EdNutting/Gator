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

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from gator.common.http_api import HTTPAPI


@pytest.mark.asyncio
class TestHTTPAPI:
    """Tests for HTTPAPI class to ensure retry logic consistency"""

    async def test_post_respects_retry_count(self):
        """Test that POST method uses configured retry count (Issue #1)"""
        # Create API with custom retry count
        api = HTTPAPI(retries=5, delay=0.01)
        api.url = "localhost:8080"

        # Mock the session to always fail
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None

        mock_session = MagicMock()
        mock_post = MagicMock()
        mock_post.return_value = mock_response
        mock_session.post = mock_post

        # Mock to raise connection error
        mock_post.side_effect = aiohttp.ClientConnectionError()

        api.session = mock_session

        # Call POST and expect it to fail after retries
        _result = await api.post("test/route", data="test")

        # Verify it tried exactly 5 times (the configured retry count)
        assert mock_post.call_count == 5, f"Expected 5 retry attempts, got {mock_post.call_count}"

    async def test_post_respects_delay(self):
        """Test that POST method uses configured delay between retries (Issue #1)"""
        # Create API with custom delay
        custom_delay = 0.05
        api = HTTPAPI(retries=3, delay=custom_delay)
        api.url = "localhost:8080"

        # Mock the session to always fail
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None

        mock_session = MagicMock()
        mock_post = MagicMock()
        mock_post.return_value = mock_response
        mock_session.post = mock_post

        # Mock to raise connection error
        mock_post.side_effect = aiohttp.ClientConnectionError()

        api.session = mock_session

        # Patch asyncio.sleep to track calls
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            # Call POST and expect it to fail after retries
            _result = await api.post("test/route", data="test")

            # Verify sleep was called with the correct delay
            # Should be called retries times (once after each failed attempt)
            assert mock_sleep.call_count == 3, \
                f"Expected 3 sleep calls, got {mock_sleep.call_count}"

            # Verify the delay value is correct
            for call in mock_sleep.call_args_list:
                assert call[0][0] == custom_delay, \
                    f"Expected delay of {custom_delay}, got {call[0][0]}"

    async def test_get_respects_retry_count(self):
        """Test that GET method uses configured retry count for consistency check"""
        # Create API with custom retry count
        api = HTTPAPI(retries=4, delay=0.01)
        api.url = "localhost:8080"

        # Mock the session to always fail
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None

        mock_session = MagicMock()
        mock_get = MagicMock()
        mock_get.return_value = mock_response
        mock_session.get = mock_get

        # Mock to raise connection error
        mock_get.side_effect = aiohttp.ClientConnectionError()

        api.session = mock_session

        # Call GET and expect it to fail after retries
        _result = await api.get("test/route")

        # Verify it tried exactly 4 times (the configured retry count)
        assert mock_get.call_count == 4, f"Expected 4 retry attempts, got {mock_get.call_count}"

    async def test_post_get_retry_consistency(self):
        """Test that POST and GET methods use the same retry configuration"""
        # Create API with custom settings
        custom_retries = 7
        custom_delay = 0.02
        api = HTTPAPI(retries=custom_retries, delay=custom_delay)
        api.url = "localhost:8080"

        mock_session = MagicMock()
        api.session = mock_session

        # Test POST
        mock_post = MagicMock()
        mock_post.side_effect = aiohttp.ClientConnectionError()
        mock_session.post = mock_post

        with patch("asyncio.sleep", new_callable=AsyncMock):
            await api.post("test/route", data="test")
            post_attempts = mock_post.call_count

        # Test GET
        mock_get = MagicMock()
        mock_get.side_effect = aiohttp.ClientConnectionError()
        mock_session.get = mock_get

        with patch("asyncio.sleep", new_callable=AsyncMock):
            await api.get("test/route")
            get_attempts = mock_get.call_count

        # Both should make the same number of attempts
        assert post_attempts == get_attempts == custom_retries, \
            (f"POST attempts ({post_attempts}) and GET attempts "
             f"({get_attempts}) should both equal {custom_retries}")

    async def test_post_success_on_first_attempt(self):
        """Test that POST succeeds on first attempt when server responds correctly"""
        api = HTTPAPI(retries=5, delay=0.01)
        api.url = "localhost:8080"

        # Mock successful response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"result": "success", "data": "test_data"})
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None

        mock_session = MagicMock()
        mock_post = MagicMock(return_value=mock_response)
        mock_session.post = mock_post
        api.session = mock_session

        # Call POST
        result = await api.post("test/route", data="test")

        # Should succeed on first try
        assert mock_post.call_count == 1, "Should only attempt once when successful"
        assert result == {"result": "success", "data": "test_data"}

    async def test_post_success_after_retries(self):
        """Test that POST succeeds after some failed attempts"""
        api = HTTPAPI(retries=5, delay=0.01)
        api.url = "localhost:8080"

        # Mock response that fails twice then succeeds
        mock_response_fail = AsyncMock()
        mock_response_fail.__aenter__.side_effect = aiohttp.ClientConnectionError()

        mock_response_success = AsyncMock()
        mock_response_success.status = 200
        mock_response_success.json = AsyncMock(return_value={"result": "success"})
        mock_response_success.__aenter__.return_value = mock_response_success
        mock_response_success.__aexit__.return_value = None

        mock_session = MagicMock()
        mock_post = MagicMock()
        # Fail twice, then succeed
        mock_post.side_effect = [
            aiohttp.ClientConnectionError(),
            aiohttp.ClientConnectionError(),
            mock_response_success
        ]
        mock_session.post = mock_post
        api.session = mock_session

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await api.post("test/route", data="test")

        # Should have tried 3 times total
        assert mock_post.call_count == 3, "Should attempt 3 times (2 failures + 1 success)"
        assert result == {"result": "success"}
