# 课程任务与笔记智能体

一个可离线运行、具备“自然语言对话 + 工具调用”能力的 Python 智能体示例。

## 功能

- 自然语言添加课程任务
- 查看待办任务
- 按编号完成任务
- 保存学习笔记
- 查询城市天气并给出建议
- 安全执行四则运算
- 导出任务清单为文本文件

## 运行环境

- Python 3.10+
- 无第三方依赖

## 运行方式

```bash
python3 office_agent.py --demo
```

单轮对话：

```bash
python3 office_agent.py --say "帮我记下来 周五18:00前交软件工程作业"
```

交互式对话：

```bash
python3 office_agent.py
```

输入 `退出` 结束。

## 项目结构

```text
study-agent/
├── office_agent.py      # 智能体主程序
├── README.md            # 运行说明
├── blog_post.md         # 博客园 Markdown 文稿
├── demo_output.txt      # 演示输出
└── data/                # 本地 JSON 数据目录
```

## 智能体工作流

```text
用户自然语言输入
→ 意图识别
→ 实体提取
→ 选择并调用工具
→ 工具读写本地文件或计算
→ 观察执行结果
→ 生成自然语言回复
```

## 可扩展方向

当前版本为了便于课堂演示，使用规则识别自然语言。后续可以将 `understand()` 替换为 OpenAI/Claude 等大模型的 Function Calling，并把 `TaskStore`、天气查询、计算器等工具注册为 MCP Tool，从而升级为真正的大模型驱动智能体。
