# hardware-test-platform

面向嵌入式与硬件验证场景的通用测试平台。当前仓库以配置驱动的 Python 执行为核心，提供统一的测试资产组织方式、多平台设备抽象、以及实时的终端监控与规范化的测试报告。

## ✨ 核心能力

- **分层资产编排**：支持原子级函数 (`Function`)、模块级用例 (`Case`) 到场景级套件 (`Fixture`) 的自由组合。
- **配置驱动执行**：完全通过 JSON 描述测试对象、运行参数和重试/超时策略，隔离代码逻辑与执行诉求。
- **平台硬件抽象**：基于 `Board Profile`、公共 capability contract 和平台实现包，统一测试语义并隔离 Linux/Zephyr 等平台差异。
- **全链路可观测性**：内置实时终端大盘 (Dashboard)、完整的执行快照 (Snapshot)、事件流 (JSONL) 以及标准的文本与结构化 JSON 报告。

## 🚀 安装与部署

推荐以源码方式运行，并在隔离的 Python 虚拟环境中进行依赖管理。

### 1. 本地基础环境初始

**环境要求**
- Python 3.8+
- pip
- 基础 Linux 系统工具 (`ip`, `ping`, `ethtool` 等)

**克隆与安装**
```bash
git clone <repository_url>
cd hardware-test-platform

# 创建并激活虚拟环境
python -m venv .venv
source .venv/bin/activate

# 安装运行依赖包
pip install -r requirements.txt
```
*(注：如果需要运行 `tests/` 目录下的自动化测试，请额外安装 `pytest`)*

### 2. 远程开发板（离线）部署

针对嵌入式硬件，平台已全部跑通面向目标开发板的本地源码打包、离线环境推送与远端闭环测试的回传链路。
详细操作指引请阅读： 🔗 [远程离线部署与测试使用指南](doc/远程离线部署与测试.md)。

离线部署的示例命令如下（请根据实际环境替换 IP、用户名、密码和远程路径）：
```bash
python scripts/package_and_deploy_offline.py 192.168.100.119 seeed seeed /home/seeed/hardware_test_platform --download-missing
```

## 💻 快速上手与使用

使用之前，需激活虚拟环境
```bash
cd hardware_test_platform
source venv/bin/activate
```

由于当前未作全局 `console_scripts` 安装，各类核心执行命令统一通过 `python -m framework.cli.*` 的方式调用。若当前就在项目根目录，通常可省略 `--workspace-root`；若从子目录、脚本或 CI 环境发起，建议显式传入 `--workspace-root .` 以固定配置解析与产物输出根目录。

### 场景一：执行整套测试套件（Fixture）

执行一套完整的验证场景（例如 Linux 主机的默认全量检查）：
```bash
python -m framework.cli.run_fixture --config fixtures/linux_host_pc.json
```

** 带实时的交互监控运行（强烈推荐）：**
只需在上述命令末尾追加 `--dashboard` 参数即可唤起 TUI dashboard，实时查看测试流及单项状态：
```bash
python -m framework.cli.run_fixture --config fixtures/linux_host_pc.json --dashboard
```

### 场景二：执行特定模块用例（Case）

如果在开发阶段仅需跑单模块（如：跑通`网络测试` 模块下的所有动作）：
```bash
python -m framework.cli.run_case --config cases/linux_host_pc/eth_case.json
```

### 场景三：极简调试原子测试（Function）

可以直调最细粒度的“测试函数”，支持挂入自定义参数和指定板级配置（如指定 RK3576 测试物理引脚）：
```bash
python -m framework.cli.run_function \
  --workspace-root . \
  --board-profile rk3576 \
  --callable functions.gpio.test_gpio_mapping:test_gpio_mapping \
  --params '{"pin_mapping": {"UART2_TX_M0": 8}, "required_signals": ["UART2_TX_M0"]}'
```

### 产物归档与追踪
一旦完成任一测试操作，所有进度和结果均在此目录下固化，方便团队协作与自动化收集：
- **`tmp/`**：实施阶段产生的实时序列快照 (`{request_id}_snapshot.json`)。
- **`logs/events/`**：全量事件流记录 (`{request_id}.jsonl`)，便于机器无损溯源。
- **`logs/`**：传统的纯文本执行日志。
- **`reports/`**：最终按 `{sku}_{request_id}_{timestamp}_{status}` 格式生成的完整报表（含纯文本及 JSON 版本）。

## 核心架构与概念

为了不侵入任何业务代码即实现配置调度与测试分离，请认准以下核心层级：

1. **Function (平台能效原子)**: 存放于 `functions/`。是开发者写的底层 Python 测试逻辑（如 `test_eth_ping.py`）。严禁主动读配置，接口能力及变量全部由平台经 `capability_registry` 派发。
2. **Case (测试用例组合)**: 存放于 `cases/` 下的 JSON。用于描述单个模块（例如 GPIO模块）该运行哪些 Function，需要怎样的重试机制与超时限制。
3. **Fixture (端到端大场景)**: 存放于 `fixtures/` 下的高阶 JSON。串联起若干个 Case，它代表着一次真正的验收、PCBA 冒烟、长期压测。
4. **Board Profile (跨板隔离化配置)**: 存放于 `config/boards/` 下。描述一块特定板卡到底具备哪些实体接口名（比如 I2C 叫具体的 /dev/i2c-2）。一套 Case 只要绑上不同的 Profile 即可实现“**换板不换执行逻辑**”。

### Platform Capability 结构

当前 platform capability 已按“公共 contract + 平台实现”方式组织：

- `framework/platform/capabilities/base.py`：定义 network、serial、gpio、i2c、rtc、system_info 的公共 contract。
- `framework/platform/capabilities/linux/`：当前可运行的 Linux capability 实现。
- `framework/platform/capabilities/zephyr/`：Zephyr MCU capability skeleton，目前仅定义类结构和方法入口，尚未接入 Zephyr adapter、串口 shell 或其他 transport。

这意味着 Function 层继续只依赖统一 capability 语义，后续接入 Zephyr 时主要增量会落在 adapter、capability 实现和 board profile，而不是复制一套 Function。

## 📂 工程结构

```text
hardware-test-platform/
├── cases/                  # -> [配置资产] 单模块的用例逻辑控制 (JSON)
├── fixtures/               # -> [配置资产] 跨模块的组合测试套件 (JSON)
├── functions/              # -> [功能资产] 硬件验证核心机制实现 (Python)
├── config/                 # 框架的基础规则与各个 Board Profile 清单
├── framework/              # 【系统核心引擎层】
│   ├── cli/                # 终端请求与命令行入口
│   ├── config/ & domain/   # Schema 解析和状态机的流转定义
│   ├── execution/          # 测试用例的 DAG 解析调度和容错机制分发
│   ├── platform/           # 系统底层设备能力及网关等屏蔽层隔离组件
│   │   ├── adapters/       # Linux / future Zephyr adapters
│   │   ├── capabilities/   # capability contracts + platform-specific implementations
│   │   └── registry.py     # 按 board profile.platform 装配 adapter/capability
│   └── observability/      # 全链路监控、执行日志、快照更新、TUI报表输出
├── framework/dashboard/    # 终端交互式展示面板渲染 (TUI)
├── reports/                # 归档生成的自动化出货与测试报表
├── logs/                   # CLI 控制台运行轨迹日志
├── tmp/                    # Dashboard 热更新断点与缓冲暂存区
├── doc/                    # 设计理念及各接口开发历史沿革
└── tests/                  # 测试平台自身的自动化自检测试单元
```

## 🛠️ 二次开发与扩展

### 添加新的底层测试能力 (Function)
1. 在 `functions/<模块名>/` 目录下新增你的 Python。
2. 保持统一且泛用的出入参拦截：必须返回标准字典（要求包含 `code`, `status`, `message`）：
    ```python
    from typing import Any

    def test_demo(
        capability_registry: dict[str, Any] | None = None,
        execution_context: Any | None = None,
    ) -> dict[str, Any]:
        # TODO: 从 capability_registry 抽平台底层
        return {"code": 0, "status": "passed", "message": "demo passed"}
    ```
3. 在 `cases/` 创建 json 后，把用例路径绑定进行。

### 接入一款全新设备的适配模板
当我们需要将测试平台移植给一个全新的硬件平台（例如 `rk3588`主板）:
1. 到 `config/boards/<新建板系>.json` 添加一个新的 Profile 配置表。
2. 将此目标板所有可用的 `interfaces`（如网口名称、GPIO总线等）与 `capabilities` 写全。无需改动前人的 Function 即可复用资产。
3. 如果是新平台族（例如 Zephyr MCU），在 `framework/platform/adapters/` 和 `framework/platform/capabilities/<platform>/` 下补齐实现，并在 `framework/platform/registry.py` 中完成装配。

### Zephyr 扩展现状

仓库当前已经预留 `framework/platform/capabilities/zephyr/` 目录，但它还是 skeleton 状态：

- 已有与 Linux 同名的 capability 类骨架，便于未来逐项填充实现。
- 目前尚未提供 Zephyr adapter，也还没有把串口 shell、BLE、Wi-Fi 等 transport 映射到 capability contract。
- 因此当前可以继续复用 Function/Case/Fixture 资产设计，但 Zephyr 真正执行链路仍待后续实现。

## 📚 更多设计细节参考

如果您涉及重构或深入平台架构修改，请参阅：
- [嵌入式测试通用软件框架需求分析](doc/%E5%B5%8C%E5%85%A5%E5%BC%8F%E6%B5%8B%E8%AF%95%E9%80%9A%E7%94%A8%E8%BD%AF%E4%BB%B6%E6%A1%86%E6%9E%B6%E9%9C%80%E6%B1%82.md)
- [软件架构设计文档](doc/%E8%BD%AF%E4%BB%B6%E8%AE%BE%E8%AE%A1%E6%96%87%E6%A1%A3.md)
- [被控端控制接口规范总结](doc/%E6%8E%A7%E5%88%B6%E6%8E%A5%E5%8F%A3%E6%80%BB%E7%BB%93.md)
- [首期实施验收方案](doc/%E9%A6%96%E6%9C%9F%E5%AE%9E%E7%8E%B0%E6%96%B9%E6%A1%88.md)