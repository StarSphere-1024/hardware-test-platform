# CLAUDE.md

## Package Manager
- Use pip + virtualenv.
- Standard environment:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

- Run Python and pytest via `venv/bin/python`; do not assume `pytest` exists on PATH.

## Build And Test
- Full regression:

```bash
venv/bin/python -m pytest
```

- High-value targeted regression:

```bash
venv/bin/python -m pytest tests/cli/test_cli.py
venv/bin/python -m pytest tests/config/
venv/bin/python -m pytest tests/platform/
venv/bin/python -m pytest tests/smoke/
venv/bin/python -m pytest tests/dashboard/test_cli_dashboard.py
```

- When touching scheduler, locks, parallel execution, or observer state, run at least:

```bash
venv/bin/python -m pytest tests/config/test_resolver.py tests/cli/test_cli.py tests/smoke/test_quick_validation.py
```

## Execution Entry Points
- Use module invocation only; do not add new `console_scripts` entry points.

```bash
python -m framework.cli.run_fixture --config fixtures/<name>.json [--dashboard]
python -m framework.cli.run_case --config cases/<board>/<name>.json
python -m framework.cli.run_function \
  --workspace-root . \
  --board-profile <profile> \
  --callable functions.<module>.<func>:<func> \
  --params '<json>'
```

- CLI root detection is already implemented in `framework/cli/common.py`; keep commands compatible with launching from subdirectories.

## Architecture
- Flow:

```text
Functions -> Cases -> Fixtures
CLI -> Config Resolver -> Scheduler -> Platform Capabilities -> Device/Remote
                                     -> Snapshot / Events / Logs / Reports
```

- `functions/`: atomic test logic; framework injects `capability_registry` and `execution_context`.
- `cases/`: module-level JSON policies, thresholds, retry/timeout, resource declarations.
- `fixtures/`: scenario-level orchestration of cases.
- `config/boards/`: board profile, interfaces, capabilities, product metadata.
- `framework/config/`: config loading, validation, resolution, board assembly.
- `framework/execution/`: fixture/case/function execution, scheduler, retry/timeout, lock handling.
- `framework/domain/`: request, spec, result, event, execution context models.
- `framework/platform/`: adapters, capability contracts, Linux implementation, registry.
- `framework/observability/`: snapshot, event, report, logger plumbing.
- `framework/dashboard/`: terminal dashboard based on current snapshot and event files.

## Current Status
- Linux platform path is the only runnable platform path.
- `framework/platform/capabilities/zephyr/` is still skeleton-only.
- `framework/platform/capabilities/` has been reorganized by platform; shared contracts are in `framework/platform/capabilities/base.py`, Linux implementations are in `framework/platform/capabilities/linux/`, and top-level modules keep compatibility shims.
- Real function assets are in place for `network`, `uart`, `rtc`, `gpio`, `i2c`.
- `tests/smoke/test_quick_validation.py` covers the main fixture flow with mocked capabilities.
- `tests/smoke/test_quick_validation.py` also covers stop-on-failure and precheck failure paths, including snapshot/event/log/report consistency.
- Resource locks are implemented.
- Parallel container scheduling is implemented.
- Parallel execution only runs tasks without resource conflicts in parallel; conflicting resources still serialize via `ResourceLockManager`.
- `stop_on_failure` in parallel mode only blocks pending tasks; already-running tasks are not force-cancelled.
- Dashboard integration is wired through `framework/cli/common.py` `execute_plan`; dashboard reads snapshot/event/log/report artifacts directly instead of legacy `*_result.json` files.
- Dashboard currently separates refresh cadence from timer logic:
  - UI refresh uses `refresh_interval`.
  - Running case elapsed time uses observed start time plus `time.monotonic()` delta.
  - Running cases display quantized whole seconds.
  - Completed cases keep ms / short-second precision.
- `fixtures/linux_host_pc_parallel.json` is the first explicit parallel fixture asset.

## Output Artifacts
- `tmp/{request_id}_snapshot.json`: dashboard snapshot and runtime state.
- `logs/events/{request_id}.jsonl`: full event stream.
- `logs/{request_id}.log`: text execution log.
- `reports/`: text + JSON final reports.

## Key Conventions
- New `functions/**/test_*.py` modules must set `__test__ = False` at module top.
- Function return payload must include at least `code`, `status`, `message`.
- Prefer returning optional `details` and `metrics` instead of ad hoc keys when extra structure is needed.
- Functions must not read global config directly.
- Functions must not hardcode board-specific device paths.
- Board differences belong in `config/boards/*.json`.
- SKU and stage come from board profile `product`, not `config/global_config.json`.
- Case parameter templating may use resolved values such as `${resolved.interfaces.*}`.
- If adding a capability or platform, extend `framework/platform/registry.py` first, then update functions/cases.

## Configuration Rules
- Priority:

```text
CLI overrides -> fixture -> case -> board profile -> global config -> function defaults
```

- Board profiles declare resources and capabilities, not pass/fail thresholds.
- Thresholds and expectations belong in `cases/**/*.json` under function config.
- Resource keys may be explicit in specs; otherwise resolver may derive them from required interfaces/capabilities.
- Resource lock quarantine is a runtime config value and may be overridden from CLI.
- Resource lock quarantine override flag is `--resource-lock-quarantine-seconds`.

## Remote Workflow
- Preferred remote/offline path:

```bash
python scripts/package_and_deploy_offline.py <ip> <user> <pass> <remote_path> --download-missing
```

- Reuse supporting scripts in `scripts/run_remote_*.sh`, `scripts/fetch_remote_artifacts.sh`, `scripts/check_remote_status.sh`.
- Remote bundle flow is source archive + wheelhouse + `python -m framework.cli.*`.
- Remote default dependency baseline is `rich` + `pyserial`; `psutil` is optional and can be supplied via `--with-psutil` when needed.
- Missing `psutil` on the remote side must not block core execution.

## High-Value Files
- `framework/cli/common.py`
- `framework/config/resolver.py`
- `framework/execution/scheduler.py`
- `framework/execution/function_executor.py`
- `framework/observability/logger.py`
- `framework/platform/registry.py`
- `framework/dashboard/cli_dashboard.py`
- `framework/platform/capabilities/base.py`
- `functions/network/test_eth_ping.py`
- `config/boards/rk3576.json`
- `tests/smoke/test_quick_validation.py`
- `tests/dashboard/test_cli_dashboard.py`

## Pitfalls
- Do not treat Zephyr capability stubs as runnable implementation.
- Timeout is not hard cancellation; hardware state may still need cleanup before retry.
- RK3576 UART failures without loopback are expected; do not silently convert them to pass.
- `cases/rk3576/uart_case.json` intentionally uses `timeout=5` and `retry=0` to fail fast in no-loopback scenarios.
- Dashboard reads snapshot/event/log/report files directly; legacy `*_result.json` is not the source of truth here.
- Observer writes are concurrency-sensitive; preserve locking around parallel event/snapshot updates.

## Local Skills
- No repository-local Claude skills are currently defined under `.claude/skills/` in this repo.

