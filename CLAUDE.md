# hot-creator — Claude Code 项目配置

## 允许的命令

以下命令可以自动执行，无需逐一确认：

```
allow: python scripts/*.py *
allow: python -m py_compile *
allow: pip install -r requirements.txt
allow: pip install -r requirements-cli.txt
allow: uv pip install *
allow: node scripts/cdp/*.mjs *
allow: bash setup.sh
allow: powershell setup.ps1
```

## 安装

核心依赖只有 5 个包（~5 MB），3 秒装完：

```bash
pip install -r requirements.txt
```

`litellm` 只在 CLI 独立模式才需要（~200 MB），作为 Skill 不需要装。

## 项目结构

这是一个 Agent Skill 项目，核心入口是 `SKILL.md`。
执行任何操作前先读取 `SKILL.md` 获取工具索引和编排策略。

## 执行约定

- 所有 Python 脚本在 `scripts/` 目录下，通过 JSON stdin/stdout 通信
- 采集类脚本（collect_*）用子智能体执行，避免大数据进主上下文
- 输出文件写入 `output/` 目录，该目录已在 `.gitignore` 中
- `config.yaml` 含配置信息，不要提交到 git
- 作为 Skill 运行时不需要 `AI_API_KEY`，Agent 自身就是 AI
- 中间 JSON 落盘传路径，不要在对话中打印文件内容
