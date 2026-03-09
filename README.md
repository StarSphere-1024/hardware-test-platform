# hardware-test-platform

面向嵌入式与硬件验证场景的通用测试平台。当前仓库以配置驱动的 Python 执行为核心，围绕 Function -> Case -> Fixture 三层测试资产组织方式，提供配置解析、执行调度、平台能力抽象、终端 Dashboard 与结果产物输出，面向内部 SE、TE、EE 协作使用。

## 项目定位

这个仓库要解决的问题不是“再写一批板卡专用脚本”，而是把多平台测试中的共性部分收敛到统一内核：

- 用 JSON 配置描述测试对象、运行参数和场景编排。
- 用统一执行模型承载单函数、单 case 和整套 fixture。
- 用 platform capability 隔离测试逻辑与底层 Linux/设备接口差异。
- 用统一快照、事件流、日志和报告支持执行中观测与执行后追溯。

仓库内的设计背景和边界说明见 [doc/软件设计文档.md](doc/%E8%BD%AF%E4%BB%B6%E8%AE%BE%E8%AE%A1%E6%96%87%E6%A1%A3.md) 与 [doc/嵌入式测试通用软件框架需求.md](doc/%E5%B5%8C%E5%85%A5%E5%BC%8F%E6%B5%8B%E8%AF%95%E9%80%9A%E7%94%A8%E8%BD%AF%E4%BB%B6%E6%A1%86%E6%9E%B6%E9%9C%80%E6%B1%82.md)。

## 当前范围与已实现能力

基于当前仓库代码、配置和测试，已能确认的范围如下：

- 已提供源码级 CLI 入口：fixture、case、function、dashboard。
- 已实现配置加载与解析链路：global config、board profile、fixture、case、CLI override、模板解析。
- 已实现执行内核：fixture runner、case runner、scheduler、function executor。
- 已实现基础策略：sequential 执行、function 级 retry/timeout、case 或 fixture 级 stop_on_failure。
- 已实现平台装配：LinuxAdapter + network、serial、gpio、i2c、rtc、system_info capability 注册。
- 已实现观测链路：tmp 快照、logs/events JSONL 事件流、执行日志、text/json 报告、终端 Dashboard。
- 已落地的真实函数资产位于以下模块：network、uart、rtc、gpio、i2c。

当前仓库内可直接看到的测试资产：

- 默认 fixture：fixtures/linux_host_pc.json
- 默认 board profile：config/global_config.json 中的 linux_host_pc
- 备选 board profile：config/boards/rk3576.json
- 已落地 case：cases/linux_host_pc 下的 eth、uart、rtc、i2c，以及根目录的 gpio_case.json

当前默认 fixture linux_host_pc 包含 4 个 case：ETH、UART、RTC、I2C。GPIO 已有独立 case 和函数资产，但尚未纳入默认 fixture。

## 分层与架构概览

### 测试资产分层

- Function：最小原子测试单元，对应 functions/ 下的 Python callable，例如 test_eth_ping。
- Case：围绕单一模块组织的一组 Function 调用，对应 cases/ 下的 JSON。
- Fixture：围绕一次完整验证场景组织的一组 Case，对应 fixtures/ 下的 JSON。

典型调用链：

```text
CLI
  -> ConfigResolver
  -> FixtureRunner / Scheduler
  -> FunctionExecutor
  -> PlatformRegistry / Capability
  -> ResultStore / EventStore / ReportGenerator / Dashboard
```

### 框架分层

- framework/cli：命令行入口与请求构造。
- framework/config：配置模型、加载、校验、解析。
- framework/domain：请求、执行上下文、结果、事件等领域对象。
- framework/execution：任务图、调度、Runner、重试与中止策略。
- framework/platform：adapter、capability、板级 profile 装配。
- framework/observability：快照、事件流、日志、报告生成。
- framework/dashboard：终端 Dashboard。
- framework/monitoring：Dashboard 使用的系统监控辅助能力。

## 环境要求与快速开始

仓库当前没有打包后的 console_scripts 入口，也没有根级 pyproject.toml 或 setup.py。建议直接以源码方式运行。

### 运行依赖

- Python 3 环境
- pip
- Linux 主机可用系统工具：ip、ping、ethtool
- Python 依赖：rich、psutil、pyserial，见 requirements.txt

### 初始化示例

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

如果你要运行 tests/ 下的自动化测试，还需要确保当前环境中已经安装 pytest。仓库当前的 requirements.txt 没有声明测试依赖。

## 远程板离线部署

新平台已经补齐一套面向开发板的源码级远程闭环，支持离线依赖安装、远程执行 case 或 fixture、以及测试产物回传。使用说明见 [doc/远程离线部署与测试.md](doc/%E8%BF%9C%E7%A8%8B%E7%A6%BB%E7%BA%BF%E9%83%A8%E7%BD%B2%E4%B8%8E%E6%B5%8B%E8%AF%95.md)。

## 常用命令

以下命令默认在仓库根目录执行。

### 运行默认 fixture

```bash
python -m framework.cli.run_fixture \
  --workspace-root . \
  --config fixtures/linux_host_pc.json
```

### 运行单个 case

```bash
python -m framework.cli.run_case \
  --workspace-root . \
  --config cases/linux_host_pc/eth_case.json
```

### 运行单个 function

```bash
python -m framework.cli.run_function \
  --workspace-root . \
  --callable functions.network.test_eth_ping:test_eth_ping \
  --params '{"target_ip": "192.168.100.1", "interface": "end0"}'
```

### 切换 board profile

```bash
python -m framework.cli.run_case \
  --workspace-root . \
  --board-profile rk3576 \
  --config cases/gpio_case.json
```

### 启动带 Dashboard 的执行

```bash
python -m framework.cli.run_fixture \
  --workspace-root . \
  --config fixtures/linux_host_pc.json \
  --dashboard
```

### 单独查看 Dashboard

```bash
python -m framework.cli.run_dashboard \
  --workspace-root . \
  --artifacts-root . \
  --fixture linux_host_pc
```

### 运行测试

```bash
python -m pytest
```

说明：CLI 会把执行结果以 JSON 输出到 stdout，同时返回与根结果状态对应的进程退出码。输出 JSON 中会包含 request_id、snapshot_path、event_log_path、report_paths、log_path 等字段。

## 配置模型与测试资产模型

### 1. Global Config

全局配置位于 config/global_config.json，当前包含：

- product：sku、stage、默认 board_profile
- runtime：default_timeout、default_retry、default_retry_interval
- observability：report_enabled、dashboard_enabled 等默认项

### 2. Board Profile

板级 profile 位于 config/boards/。当前仓库内可见 profile：

- linux_host_pc：本地 Linux 主机验证用默认 profile
- rk3576：RK3576 板卡 profile

Board profile 负责声明：

- supported_cases
- interfaces 候选列表
- capabilities 声明
- tools_required
- metadata

当前 profile 中已经声明的接口类别包括 eth、uart、gpio、i2c、rtc。

### 3. Case

Case JSON 负责描述单模块测试，例如：

- 模块名与说明
- 执行方式
- required_interfaces 预检
- function 列表
- 每个 function 的 params、timeout、expect

Case 支持通过模板引用解析后的运行时上下文，例如：

```json
"interface": "${resolved.interfaces.eth.primary}"
```

### 4. Fixture

Fixture JSON 负责把多个 case 组织为一个场景，并声明：

- cases 列表
- execution
- stop_on_failure
- report_enabled
- timeout / retry / retry_interval

### 5. CLI Override

CLI 可以覆盖部分运行参数，例如：

- --board-profile
- --timeout
- --retry
- --retry-interval
- --execution
- --stop-on-failure
- --report-enabled / --no-report

这些覆盖项会进入解析后的 ResolvedExecutionConfig，而不是由 Function 直接读取配置文件。

## 当前已落地函数资产

目前仓库中已有以下真实函数实现，可作为后续扩展示例：

- functions/network/test_eth_ping.py：基于 network capability 执行 ping，并提取 packet loss、avg latency。
- functions/uart/test_uart_loopback.py：基于 serial capability 执行串口 loopback。
- functions/rtc/test_rtc_read.py：基于 rtc capability 读取时间。
- functions/gpio/test_gpio_mapping.py：基于 gpio capability 校验物理脚位映射。
- functions/i2c/test_i2c_scan.py：基于 i2c capability 扫描总线。

这些函数都支持从 capability_registry 或 execution_context 中获取平台能力，符合“Function 不直接读取配置文件”的约束。

## 输出产物与观测

一次执行完成后，默认会在仓库根目录下生成以下产物：

- tmp/{request_id}_snapshot.json：当前执行快照
- logs/events/{request_id}.jsonl：顺序事件流
- logs/{request_id}.log：统一执行日志
- reports/{sku}_{request_id}_{timestamp}_{status}.report：文本报告
- reports/{sku}_{request_id}_{timestamp}_{status}.report.json：结构化报告

Dashboard 直接消费 tmp、logs/events、logs、reports 下的当前产物，不依赖旧平台的 result.json 约定。

## 目录结构

```text
hardware-test-platform/
├── cases/                  # Case 配置
├── config/                 # Global config 与 board profiles
├── doc/                    # 需求、设计、方案文档
├── fixtures/               # Fixture 配置
├── framework/
│   ├── cli/                # run_fixture / run_case / run_function / run_dashboard
│   ├── config/             # loader / validator / resolver / models
│   ├── domain/             # requests / execution / results / events
│   ├── execution/          # runner / scheduler / policies
│   ├── dashboard/          # 终端 Dashboard
│   ├── monitoring/         # Dashboard 监控辅助
│   ├── observability/      # snapshot / event / report / logger
│   └── platform/           # adapters / capabilities / registry
├── functions/              # 测试函数资产
├── logs/                   # 执行日志与事件
├── reports/                # 文本与 JSON 报告
├── tests/                  # CLI / config / execution / platform / smoke 测试
└── tmp/                    # 执行快照与中间状态
```

## 如何新增测试资产

### 新增 Function

1. 在 functions/<module>/ 下新增 Python 文件。
2. 暴露可调用函数，返回 dict 结果。
3. 尽量通过 capability_registry 或 execution_context 获取平台能力。
4. 保持返回结构稳定，至少包含 code、message，必要时附带 details、metrics、status。

最小示例：

```python
from typing import Any


def test_demo(
    capability_registry: dict[str, Any] | None = None,
    execution_context: Any | None = None,
) -> dict[str, Any]:
    return {
        "code": 0,
        "status": "passed",
        "message": "demo passed",
    }
```

### 新增 Case

1. 在 cases/ 下新增 JSON。
2. 声明 case_name、module、functions。
3. 如果依赖特定接口，补 required_interfaces。
4. 如果需要绑定特定 board profile，确认 case_name 在 profile 的 supported_cases 中。

### 新增 Fixture

1. 在 fixtures/ 下新增 JSON。
2. 组合已有 case。
3. 根据场景声明 stop_on_failure、retry、timeout、report_enabled。

### 新增 Board Profile

1. 在 config/boards/ 下新增 profile。
2. 明确 interfaces、supported_cases、capabilities、tools_required。
3. 通过 global_config 或 CLI 的 --board-profile 选择它。

## 开发与验证建议

- 改动配置解析链路后，优先回归 tests/config 和 tests/cli。
- 改动执行内核后，优先回归 tests/execution 与 tests/smoke/test_quick_validation.py。
- 改动 Dashboard 或产物格式后，优先回归 tests/dashboard 与 tests/observability。
- 新增函数资产时，至少补一个对应模块测试，并确认 CLI 自动发现路径仍然可用。

## 当前限制与待补充

- 当前仓库以本地 Python 进程内执行为主，尚未提供打包后的命令行安装体验。
- 当前平台适配实际落地为 LinuxAdapter，其他平台形态仍属于后续扩展位。
- 默认 fixture 仅覆盖 ETH、UART、RTC、I2C；GPIO 还未并入默认场景。
- 仓库中已有 rk3576 board profile，但没有与之配套的专用 fixture 样例。
- requirements.txt 只覆盖运行依赖，测试依赖需要单独准备。

## 参考文档

- [doc/软件设计文档.md](doc/%E8%BD%AF%E4%BB%B6%E8%AE%BE%E8%AE%A1%E6%96%87%E6%A1%A3.md)
- [doc/首期实现方案.md](doc/%E9%A6%96%E6%9C%9F%E5%AE%9E%E7%8E%B0%E6%96%B9%E6%A1%88.md)
- [doc/控制接口总结.md](doc/%E6%8E%A7%E5%88%B6%E6%8E%A5%E5%8F%A3%E6%80%BB%E7%BB%93.md)
- [doc/嵌入式测试通用软件框架需求.md](doc/%E5%B5%8C%E5%85%A5%E5%BC%8F%E6%B5%8B%E8%AF%95%E9%80%9A%E7%94%A8%E8%BD%AF%E4%BB%B6%E6%A1%86%E6%9E%B6%E9%9C%80%E6%B1%82.md)