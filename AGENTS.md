# AGENTS.md - 项目开发规范
本项目使用 **uv** 作为 Python 依赖管理与虚拟环境工具，所有依赖、脚本、环境操作必须遵循 uv 规范。

## 1. 项目基础信息
- Python 版本：>=3.10 <3.13（根据 pyproject.toml 填写）
- 依赖管理工具：uv（必须使用，禁止使用 pip/conda 直接安装）
- 配置文件：pyproject.toml

## 2. 环境初始化（已经完成，不需要重复）

## 3. 依赖管理规则（仅允许使用 uv）
### 添加生产依赖
```bash
uv add <包名>
```

### 添加开发依赖
```bash
uv add --dev <包名>
```

### 移除依赖
```bash
uv remove <包名>
```

### 更新所有依赖
```bash
uv sync --upgrade
```

## 4. 运行项目
### 直接运行 Python 文件
```bash
uv run python main.py
```

### 运行自定义脚本（定义在 pyproject.toml [project.scripts]）
```bash
uv run start
# 或
uv run dev
```

## 5. 代码规范
- 代码格式化：使用 ruff
- 代码检查：使用 ruff
- 格式化命令：
```bash
uv run ruff format .
```
- 检查命令：
```bash
uv run ruff check .
```

## 6. 测试（如有）
```bash
uv run pytest
```

## 7. 禁止行为
1. 禁止直接使用 `pip install`
2. 禁止提交 `requirements.txt`（使用 uv 自动生成即可）
3. 禁止手动修改 .venv 目录
4. 禁止不激活虚拟环境直接运行代码

## 8. AI 助手规则
- 所有依赖操作必须生成 uv 命令
- 必须使用 `uv run` 执行项目代码
- 必须基于 pyproject.toml 理解依赖
- 环境问题优先使用 `uv sync` 修复
