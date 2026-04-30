# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python-based web automation testing framework for SugonCloud, built on **Playwright + Pytest**. It uses the Page Object Model (POM) pattern and tests cloud services (ECS, EVS, VPC, SLB, etc.) through a web UI, with backend validation via SSH.

## Common Commands

### Environment Setup
```bash
pip install -r requirements.txt
playwright install
```

### Run Tests
```bash
# Run all tests (default: excludes slow tests)
pytest sugon_web/testcase/

# Run a specific module
pytest -k "ecs" sugon_web/testcase/
pytest sugon_web/testcase/compute/test_ecs_basic.py

# Run a specific test class or method
pytest sugon_web/testcase/compute/test_ecs_basic.py::TestECSBasic::test_ecs_operations

# Run with markers
pytest -m "smoke" sugon_web/testcase/
pytest -m "not slow" sugon_web/testcase/

# Run in parallel (used in CI)
pytest -n 2 --dist=loadscope sugon_web/testcase/
```

### Command-Line Options
```bash
pytest sugon_web/testcase/ \
  --host=172.22.1.190 \
  --browser-type=chromium \
  --headless=true \
  --stor=xstor \
  --username=admin \
  --password=keystone_sugon
```

### Generate Allure Report
```bash
# After running tests with --alluredir=allure-result
allure generate allure-result/ -o ./allure-report -c
allure open -h 127.0.0.1 -p 8888 ./allure-report
```

### AI Test Summary
```bash
# Requires DEEPSEEK_API_KEY or DASHSCOPE_API_KEY env var
python -m sugon_web.tools.ai_report

# Dry run (local parse only)
python -m sugon_web.tools.ai_report --dry-run
```

### Docker (CI)
```bash
docker build -t playwright-sugon:latest .
```

## Architecture

### Layer Hierarchy

The codebase follows a strict 4-layer separation:

1. **Page Object** (`sugon_web/pages/`)
   - Encapsulates page elements and single business actions
   - Inherits `BasePage` → `Playwright`
   - Public methods named `service_operation` (e.g., `ecs_create`, `evs_delete`)
   - Private helpers prefixed with `_` (e.g., `_select_cluster`)

2. **Fixture** (`sugon_web/testcase/*/conftest.py`, `_xxx_fixtures.py`)
   - Manages resource lifecycle (create / bind / cleanup)
   - Uses `yield` for teardown
   - Domain-specific fixtures go in `_xxx_fixtures.py` (e.g., `_ecs_fixtures.py`)
   - Module-common fixtures go in `conftest.py`

3. **Scenario Helper** (`_xxx_helpers.py` or module-level private functions)
   - Environment assembly, topology preparation, data normalization
   - No `yield`, no fixture scope — pure functions
   - Private helpers use `_build_xxx`, `_prepare_xxx` naming

4. **Test Class** (`test_*.py`)
   - Contains only test steps, assertions, and local variables
   - No cross-test helper methods

**Decision rule for new code:**
- Page interaction → Page Object
- Resource lifecycle → Fixture
- Environment assembly → Helper
- Single-file use → Private function in test file
- Cross-file reuse → `_xxx_helpers.py`

### Fixture Scopes (Critical)

The `page` fixture is `function`-scoped and creates a fresh tab per test, but reuses the same `class`-scoped `browser_context` to preserve login state within a test class. The `browser` fixture is `session`-scoped.

- `session` → `browser`, `config`, `ssh_host`, `jump_host`
- `class` → `browser_context`, `ssh_vm`
- `function` → `page` (auto-login via `_create_logged_in_page`)

### Configuration System

Config merges three sources in order:
1. `sugon_web/config/base.yaml` — defaults
2. `sugon_web/config/env.yaml` — host-specific overrides
3. CLI arguments (`--host`, `--browser-type`, `--headless`, etc.)

Access via `Config.get("key")` or `Config.get()` for the full dict.

### Service Navigation

Pages use `goto_service("服务名")` which resolves via `SERVICE_PATH_MAP` (URL shortcut) or falls back to `SERVICE_MAP` (menu navigation). The `@submenu("子菜单名")` decorator ensures a method runs within the correct submenu.

### SSH Backend Validation

Tests often validate UI actions against the actual backend using SSH:
- `ssh_host` — direct SSH to the test environment
- `ssh_vm` — SSH through a jump host to VMs
- `ssh_host.run("scli ...")` for OpenStack-style CLI commands

### Key Utilities

- `random_data()` — generates test data (strings, phones, emails, CIDRs, IPs)
- `load_data(case_name, data_file)` — loads parameterized test data from YAML
- `allure_step_log("step name")` — context manager wrapping Allure steps + log capture
- `skip_stor`, `skip_if_nodes_less_than`, `skip_arch` — conditional skip decorators

## Code Conventions

### Page Object
- Inherit `BasePage`
- Reuse common elements from `BasePage` (e.g., `btn_create`, `_input_search`, `popup`)
- Docstrings required on public methods
- Do NOT put scenario orchestration in page objects

### Fixture Naming
- Resource fixtures: `vpc`, `sg`, `ecs`, `vm`, `volume`
- Composite fixtures: `vm_sg_binding`
- Cleanup fixtures: `clean_xxx`

### Test Markers
- `smoke`, `regression`, `slow`, `login`, `evs`, `ecs`

### Allure Annotations
- `@allure.epic`, `@allure.feature`, `@allure.story` on test classes
- `@allure.title("服务-功能验证")` on test methods
- `with allure_step_log("..."):` for step blocks

## File Organization

```
sugon_web/
  common/
    base.py          # BasePage, @submenu decorator, common assertions
    playwright.py    # Playwright wrapper, CustomLocator
    ssh.py           # SSH client for backend validation
    mixins/          # Reusable UI component mixins (e.g., DrawerSelectMixin)
  config/
    base.yaml        # Default configuration
    env.yaml         # Per-host network settings
    config.py        # Config class (merge + override logic)
    constants.py     # SERVICE_MAP, SERVICE_PATH_MAP
  pages/
    compute/         # ECS, image, snapshot, affinity
    network/         # VPC, SG, SLB, EIP, NAT, ACL
    storage/         # EVS, EVSS
    ops.py           # Infrastructure/ops pages
    backup.py        # Backup service
  testcase/
    compute/         # test_ecs_*.py, conftest.py, _ecs_fixtures.py
    network/         # test_vpc_*.py, test_sg_*.py, conftest.py
    storage/         # test_evs_*.py, conftest.py
    conftest.py      # Cross-module fixtures (vm, vpc, sg, etc.)
    test_data/       # YAML test data files
  utils/
    logger.py        # allure_step_log, StepLogCollector
    util.py          # random_data, load_data, skip decorators
    db_util.py       # Database utilities
  tools/
    ai_report.py     # Post-test AI summary generation
```

## Important Notes

- The `vm` fixture in `sugon_web/testcase/conftest.py` is highly parametric. It accepts `VmFixtureParams` dicts via `@pytest.mark.parametrize(..., indirect=True)` and auto-injects dependencies like SG, labels, and affinity based on `inject_dependencies`.
- Screenshots on failure are captured automatically in `pytest_runtest_makereport` and attached to Allure.
- The `page` fixture auto-closes dialogs after login via `close_dialog_if_exists()`.
- Node count and patch version are fetched automatically via SSH at session startup and written into Config for skip decorators.
- `pytest.ini` sets `testpaths = sugon_web/testcase` and disables slow tests by default (`-m 'not slow'`).
