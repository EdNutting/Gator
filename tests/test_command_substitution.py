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

from gator.common.utility import find_command_substitutions


class TestFindCommandSubstitutions:
    """Test suite for finding command substitutions in text"""

    def test_find_simple_command_substitution(self):
        """Test finding simple $(cmd) patterns"""
        text = "echo $(hostname)"
        subs = find_command_substitutions(text)
        assert subs == ["$(hostname)"]

    def test_find_backticks(self):
        """Test finding `cmd` backtick patterns"""
        text = "echo `hostname`"
        subs = find_command_substitutions(text)
        assert subs == ["`hostname`"]

    def test_find_multiple_substitutions(self):
        """Test finding multiple command substitutions in one string"""
        text = "echo $(cmd) and `another`"
        subs = find_command_substitutions(text)
        assert subs == ["$(cmd)", "`another`"]

    def test_find_with_variables(self):
        """Test that variables don't interfere with finding command substitutions"""
        text = "echo $HOME and $(hostname)"
        subs = find_command_substitutions(text)
        assert subs == ["$(hostname)"]

    def test_no_command_substitutions(self):
        """Test text with no command substitutions"""
        text = "echo hello world"
        subs = find_command_substitutions(text)
        assert subs == []

    def test_empty_string(self):
        """Test empty string"""
        subs = find_command_substitutions("")
        assert subs == []

    def test_command_with_args(self):
        """Test command substitution with arguments"""
        text = "echo $(ls -la)"
        subs = find_command_substitutions(text)
        assert subs == ["$(ls -la)"]

    def test_multiple_dollar_parens(self):
        """Test multiple $() substitutions"""
        text = "$(date) - $(whoami)"
        subs = find_command_substitutions(text)
        assert subs == ["$(date)", "$(whoami)"]
