# Hardware Test Platform - Installation Scripts

## 一键安装

### 首次安装

```bash
curl -sSL https://raw.githubusercontent.com/StarSphere-1024/hardware-test-platform/master/scripts/install.sh | bash
```

### 自定义安装目录

```bash
curl -sSL https://raw.githubusercontent.com/StarSphere-1024/hardware-test-platform/master/scripts/install.sh | bash -s -- --install-dir /opt/htp
```

### 更新现有安装

```bash
curl -sSL https://raw.githubusercontent.com/StarSphere-1024/hardware-test-platform/master/scripts/install.sh | bash -s -- --update-only
```

### 强制重新安装

```bash
curl -sSL https://raw.githubusercontent.com/StarSphere-1024/hardware-test-platform/master/scripts/install.sh | bash -s -- --force
```

### 预演模式（不实际执行）

```bash
curl -sSL https://raw.githubusercontent.com/StarSphere-1024/hardware-test-platform/master/scripts/install.sh | bash -s -- --dry-run
```

## 命令行选项

| 选项 | 说明 | 默认值 |
|------|------|--------|
| `--install-dir <path>` | 安装目录 | `~/hardware-test-platform` |
| `--branch <name>` | Git 分支 | `master` |
| `--repo-owner <owner>` | GitHub 组织名 | `StarSphere-1024` |
| `--repo-name <name>` | 仓库名 | `hardware-test-platform` |
| `--update-only` | 仅更新，不克隆 | - |
| `--force` | 强制覆盖现有安装 | - |
| `--no-bashrc` | 不添加 alias 到 ~/.bashrc | - |
| `--dry-run` | 预演模式，不实际执行 | - |
| `--verbose` | 详细输出模式 | - |

## 快速入门

安装完成后：

```bash
# 使用 alias（如果添加了）
htp

# 或手动激活
cd ~/hardware-test-platform
source venv/bin/activate

# 运行测试
python -m pytest

# 运行 fixture
python -m framework.cli.run_fixture --config fixtures/linux_host.json
```

## 卸载

```bash
# 删除安装目录
rm -rf ~/hardware-test-platform

# 如果添加了 alias，从 ~/.bashrc 中移除相关行
```

## 故障排除

### Python 版本过低

安装脚本要求 Python 3.8+。检查版本：

```bash
python3 --version
```

### 缺少 git 或 curl

安装必要工具：

```bash
# Ubuntu/Debian
sudo apt-get install git curl

# CentOS/RHEL
sudo yum install git curl

# macOS
brew install git curl
```

### 网络问题

如果下载失败，检查网络连接：

```bash
curl -I https://raw.githubusercontent.com/
```

### 权限问题

如果安装到系统目录需要 root 权限：

```bash
curl -sSL https://raw.githubusercontent.com/StarSphere-1024/hardware-test-platform/master/scripts/install.sh | sudo bash -s -- --install-dir /opt/htp
```

## 本地开发

从本地 scripts 目录运行安装脚本：

```bash
# 预演模式测试
bash scripts/install.sh --dry-run

# 本地安装到测试目录
bash scripts/install.sh --install-dir /tmp/htp-test --no-bashrc
```

## 脚本结构

```
scripts/
├── install.sh              # Bash 引导脚本（curl | bash 入口）
├── _install_installer.py   # Python 安装器主逻辑
├── _install_common.py      # 共享工具函数
└── README.md               # 本文档
```

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `REPO_OWNER` | GitHub 组织名 | `StarSphere-1024` |
| `REPO_NAME` | 仓库名 | `hardware-test-platform` |
| `BRANCH` | Git 分支 | `master` |

## 更新日志

- **v1.0.0** (2026-03-20)
  - 初始版本
  - 支持一键安装
  - 支持智能增量更新
  - 支持自定义安装目录
