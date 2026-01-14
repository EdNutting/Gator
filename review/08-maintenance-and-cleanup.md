# Maintenance and Cleanup Tasks

**Priority Level:** LOW to MEDIUM
**Estimated Effort:** 3-5 days
**Action:** Clean up incrementally

---

## Table of Contents

1. [Print Statement Removal](#1-print-statement-removal)
2. [Dead Code Cleanup](#2-dead-code-cleanup)
3. [Import Organization](#3-import-organization)
4. [Code Style Consistency](#4-code-style-consistency)
5. [Dependency Updates](#5-dependency-updates)

---

## 1. Print Statement Removal

### Issue: Production Print Statements
**Priority:** High | **Effort:** Small | **Count:** 10+ instances

**Description:**
Multiple `print()` statements exist in production code that should use the logging system.

### Locations and Fixes

#### Location 1: [gator/wrapper.py:334](../gator/wrapper.py#L334)
```python
# Current:
print(something)

# Fix:
await self.logger.debug(str(something))
```

#### Location 2: [gator/common/ws_router.py:105](../gator/common/ws_router.py#L105)
```python
# Current:
print(f"ERROR: {error}", file=sys.stderr)

# Fix:
await self.logger.error(f"WebSocket routing error: {error}")
```

#### Location 3: [gator/common/http_api.py](../gator/common/http_api.py) (multiple)
```python
# Lines 62, 70, 97, 105 - Current:
print(f"HTTP Error: {e}", file=sys.stderr)

# Fix:
await self.logger.error(f"HTTP request failed: {e}")
```

#### Location 4: [gator/common/ws_wrapper.py:106](../gator/common/ws_wrapper.py#L106)
```python
# Current:
print("WEBSOCKET CLOSED UNEXPECTEDLY")

# Fix:
await self.logger.warning(
    f"WebSocket connection to {self.ident} closed unexpectedly"
)
```

#### Location 5: [gator/adapters/parent.py:111](../gator/adapters/parent.py#L111)
```python
# Current:
print(f"Timeout: {e}", file=sys.stderr)

# Fix:
await self.logger.debug(f"Receive timeout on parent adapter: {e}")
```

### Bulk Replace Script
```python
# scripts/replace_prints.py
import re
from pathlib import Path

def replace_prints_in_file(file_path: Path):
    """Replace print statements with logger calls"""
    content = file_path.read_text()

    # Pattern: print("msg") or print(f"msg")
    patterns = [
        (r'print\("([^"]+)"\)', r'await self.logger.info("\1")'),
        (r'print\(f"([^"]+)"\)', r'await self.logger.info(f"\1")'),
        (r'print\([^,]+, file=sys\.stderr\)', r'await self.logger.error(...)'),
    ]

    for pattern, replacement in patterns:
        content = re.sub(pattern, replacement, content)

    file_path.write_text(content)

# Run on all Python files
for py_file in Path("gator").rglob("*.py"):
    replace_prints_in_file(py_file)
```

---

## 2. Dead Code Cleanup

### Issue 2.1: Unused Imports
**Priority:** Low | **Effort:** Small

**Tool:** autoflake or ruff

```bash
# Find unused imports
poetry run ruff check --select F401

# Auto-fix
poetry run ruff check --select F401 --fix
```

### Issue 2.2: Unused Variables
**Priority:** Low | **Effort:** Small

**Example:** [gator/launch.py:58](../gator/launch.py#L58)
```python
# Current: glyph parameter immediately deleted
def launch(..., glyph, ...):
    del glyph  # Why is this here?

# Fix: Remove from signature
def launch(...):
    # Simply don't include glyph
```

### Issue 2.3: Commented-Out Code
**Priority:** Low | **Effort:** Small

**Action:** Remove all commented-out code blocks

**Search Pattern:**
```bash
# Find commented code blocks (3+ consecutive comment lines)
grep -r "^\s*#.*$" gator/ | uniq -c | awk '$1 >= 3'
```

---

## 3. Import Organization

### Issue: Inconsistent Import Order
**Priority:** Low | **Effort:** Small

**Current:** Some files have unorganized imports

**Fix:** Use isort or ruff

```bash
# Configure in pyproject.toml
[tool.ruff]
select = ["I"]  # Enable import sorting

[tool.isort]
profile = "black"
line_length = 100

# Run
poetry run ruff check --select I --fix
```

**Recommended Import Order:**
```python
# Standard library
import asyncio
import os
from pathlib import Path
from typing import Dict, List, Optional

# Third-party
import aiohttp
import click
from rich.console import Console

# Local
from gator.common.logger import Logger
from gator.specs.jobs import Job
from .common import utils
```

---

## 4. Code Style Consistency

### Issue 4.1: Remove Duplicate Copyright Header
**Priority:** Low | **Effort:** Small

**Location:** [gator/common/ws_router.py:1-27](../gator/common/ws_router.py#L1-L27)

**Fix:** Remove duplicate lines 15-27

### Issue 4.2: Consistent String Quotes
**Priority:** Low | **Effort:** Small

**Tool:** Ruff handles this

```toml
# pyproject.toml
[tool.ruff]
select = ["Q"]  # Quote consistency

[tool.ruff.flake8-quotes]
inline-quotes = "double"
multiline-quotes = "double"
docstring-quotes = "double"
```

### Issue 4.3: Line Length Consistency
**Priority:** Low | **Effort:** Small

**Current:** Mostly 100 char limit (good)
**Action:** Verify all files comply

```bash
poetry run ruff check --select E501
```

---

## 5. Dependency Updates

### Issue 5.1: Werkzeug Version Pinned
**Priority:** Low | **Effort:** Small

**Current:** [pyproject.toml](../pyproject.toml)
```toml
Werkzeug = "2.3.7"  # Why pinned?
```

**Action:**
1. Check if issue is resolved in latest Werkzeug
2. Update to latest stable if compatible
3. Document reason if must stay pinned

```bash
# Check latest version
poetry show werkzeug

# Try updating
poetry update werkzeug

# Test
poetry run pytest
```

### Issue 5.2: General Dependency Updates
**Priority:** Low | **Effort:** Small

**Check for updates:**
```bash
# List outdated packages
poetry show --outdated

# Update all (carefully)
poetry update

# Or update one at a time
poetry update package-name
```

**Major Dependencies to Check:**
- aiohttp (currently 3.12.13)
- websockets (currently 11.0.2)
- click (currently 8.1.3)
- rich (currently 13.3.4)
- psutil (currently 5.9.4)

---

## 6. Type Hint Improvements

### Issue: Incomplete Type Hints
**Priority:** Low-Medium | **Effort:** Medium

**Missing Type Hints Examples:**

```python
# Before
def process_data(data):
    return data.transform()

# After
def process_data(data: Dict[str, Any]) -> ProcessedData:
    return data.transform()
```

**Add mypy strict mode gradually:**
```toml
# pyproject.toml
[tool.mypy]
# Start with basics
check_untyped_defs = true
warn_return_any = true

# Gradually enable stricter checks
# disallow_untyped_defs = true
# disallow_incomplete_defs = true
```

---

## 7. Error Message Consistency

### Issue: Inconsistent Error Format
**Priority:** Low | **Effort:** Small

**Standardize error messages:**
```python
# Good pattern
raise RuntimeError(
    f"Failed to {action}: {details}. "
    f"Expected {expected}, got {actual}"
)

# Examples
raise RuntimeError(
    f"Failed to launch job: command not found. "
    f"Expected '{command}' in PATH"
)

raise SpecError(
    f"Invalid job specification: missing required field. "
    f"Field 'command' is required for Job specs"
)
```

---

## 8. Test File Organization

### Issue: Test Files Mirror Source
**Priority:** Low | **Effort:** Small

**Ensure structure matches:**
```
gator/
├── tier.py
├── wrapper.py
└── common/
    ├── logger.py
    └── db.py

tests/
├── test_tier.py
├── test_wrapper.py
└── common/
    ├── test_logger.py
    └── test_db.py
```

---

## 9. License Headers

### Issue: Verify All Files Have Headers
**Priority:** Low | **Effort:** Small

**Check:**
```bash
# Find files without license header
for file in $(find gator -name "*.py"); do
    if ! grep -q "Copyright" "$file"; then
        echo "Missing license: $file"
    fi
done
```

**Add if missing:**
```python
# Copyright 2024 Peter Birch
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
```

---

## 10. Git Hygiene

### Issue: .gitignore Completeness
**Priority:** Low | **Effort:** Small

**Recommended additions:**
```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
ENV/
env/

# IDEs
.vscode/
.idea/
*.swp
*.swo
*~

# Gator specific
.gator/
*.db
*.log

# OS
.DS_Store
Thumbs.db

# Testing
.coverage
htmlcov/
.pytest_cache/
.mypy_cache/
.ruff_cache/
```

---

## Summary Checklist

### Quick Wins (< 1 hour)
- [ ] Replace all print() with logger calls
- [ ] Remove unused imports (ruff --fix)
- [ ] Fix import ordering (ruff --fix)
- [ ] Remove duplicate copyright header
- [ ] Update .gitignore

### Medium Tasks (1-4 hours)
- [ ] Remove unused variables
- [ ] Clean up commented code
- [ ] Standardize error messages
- [ ] Check dependency updates

### Larger Tasks (1-2 days)
- [ ] Add missing type hints
- [ ] Organize test files
- [ ] Verify license headers
- [ ] Complete mypy compliance

**Total Cleanup Effort:** 3-5 days

**Automation Opportunities:**
- Pre-commit hooks for print detection
- CI check for unused imports
- Automated dependency update PRs (Dependabot)

---

*Regular maintenance prevents technical debt accumulation. Schedule cleanup sprints quarterly.*
