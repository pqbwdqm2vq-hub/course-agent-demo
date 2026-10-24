#!/usr/bin/env python3
"""课程任务与笔记智能体。

特点：
1. 能说：接收自然语言，并用自然语言回复。
2. 会做：根据意图调用工具，完成任务增删查、笔记保存、天气查询、安全计算和文件导出。
3. 离线可运行：不依赖第三方包，数据保存在本地 JSON 文件。
"""

from __future__ import annotations

import argparse
import ast
import json
import operator
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
TASK_FILE = DATA_DIR / "tasks.json"
NOTE_FILE = DATA_DIR / "notes.json"

WEATHER_INFO = {
    "广州": ("多云，26~33℃", "午后有分散阵雨，出门建议带折叠伞。"),
    "北京": ("晴，15~24℃", "早晚温差较大，建议穿薄外套。"),
    "上海": ("小雨，18~25℃", "路面湿滑，通勤预留10分钟。"),
    "深圳": ("雷阵雨，27~32℃", "雷雨时段尽量避免户外作业。"),
}

BINARY_OPERATORS: dict[type, Callable[[Any, Any], Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

UNARY_OPERATORS: dict[type, Callable[[Any], Any]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


@dataclass
class Task:
    task_id: int
    title: str
    due: str
    priority: str
    done: bool = False


class TaskStore:
    """本地文件存储，代替真实数据库。"""

    def __init__(self, task_file: Path = TASK_FILE, note_file: Path = NOTE_FILE):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.task_file = task_file
        self.note_file = note_file

    def load_tasks(self) -> list[Task]:
        if not self.task_file.exists():
            return []
        raw = json.loads(self.task_file.read_text(encoding="utf-8"))
        return [Task(**item) for item in raw]

    def save_tasks(self, tasks: list[Task]) -> None:
        payload = [asdict(task) for task in tasks]
        self.task_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load_notes(self) -> list[str]:
        if not self.note_file.exists():
            return []
        return json.loads(self.note_file.read_text(encoding="utf-8"))

    def save_notes(self, notes: list[str]) -> None:
        self.note_file.write_text(
            json.dumps(notes, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


class OfficeAgent:
    """智能体主循环：理解 -> 调用工具 -> 观察 -> 生成回复。"""

    def __init__(self, store: TaskStore | None = None):
        self.store = store or TaskStore()

    # ---------- 工具实现 ----------
    def add_task(self, title: str, due: str = "未设置", priority: str = "普通") -> str:
        tasks = self.store.load_tasks()
        next_id = max((task.task_id for task in tasks), default=0) + 1
        tasks.append(Task(next_id, title, due, priority, False))
        self.store.save_tasks(tasks)
        return f"已记下任务：{title}，截止时间：{due}，优先级：{priority}。"

    def list_tasks(self, only_pending: bool = True) -> str:
        tasks = self.store.load_tasks()
        if only_pending:
            tasks = [task for task in tasks if not task.done]
        if not tasks:
            return "当前没有待办任务。"
        lines = []
        for index, task in enumerate(tasks, start=1):
            status = "已完成" if task.done else "待完成"
            lines.append(f"{index}. [{status}] {task.title}（截止：{task.due}，优先级：{task.priority}）")
        return "当前任务清单：\n" + "\n".join(lines)

    def finish_task(self, serial_number: int) -> str:
        tasks = self.store.load_tasks()
        pending = [task for task in tasks if not task.done]
        if not pending:
            return "现在没有可以标记完成的任务。"
        if serial_number < 1 or serial_number > len(pending):
            return f"任务编号无效，当前只有 {len(pending)} 条待办任务。"
        target = pending[serial_number - 1]
        target.done = True
        self.store.save_tasks(tasks)
        return f"已完成：{target.title}。"

    def save_note(self, content: str) -> str:
        notes = self.store.load_notes()
        notes.append(content)
        self.store.save_notes(notes)
        return f"已保存第 {len(notes)} 条笔记：{content}"

    def query_weather(self, city: str) -> str:
        weather, advice = WEATHER_INFO.get(city, ("暂未收录该城市天气", "请使用已知城市：广州、北京、上海、深圳。"))
        return f"{city}当前{weather}。建议：{advice}"

    def calculate(self, expression: str) -> str:
        value = self._safe_eval(expression.strip())
        return f"计算结果：{expression.strip()} = {value}"

    def export_tasks(self) -> str:
        text = self.list_tasks(only_pending=False)
        output = BASE_DIR / "tasks_export.txt"
        output.write_text(text + "\n", encoding="utf-8")
        return f"任务清单已导出到：{output.name}"

    @staticmethod
    def _safe_eval(expression: str) -> float:
        def visit(node: ast.AST) -> Any:
            if isinstance(node, ast.Expression):
                return visit(node.body)
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                return node.value
            if isinstance(node, ast.BinOp) and type(node.op) in BINARY_OPERATORS:
                return BINARY_OPERATORS[type(node.op)](visit(node.left), visit(node.right))
            if isinstance(node, ast.UnaryOp) and type(node.op) in UNARY_OPERATORS:
                return UNARY_OPERATORS[type(node.op)](visit(node.operand))
            raise ValueError("只允许进行四则运算。")

        return visit(ast.parse(expression, mode="eval"))

    # ---------- 自然语言理解 ----------
    def understand(self, user_text: str) -> tuple[str, dict[str, Any]]:
        text = user_text.strip()

        if match := re.search(r"(完成|做完|搞定|结束)(第)?\s*(\d+)\s*(个|项|任务)?", text):
            return "finish_task", {"serial_number": int(match.group(3))}

        if any(word in text for word in ["待办", "任务列表", "有哪些任务", "安排"]):
            return "list_tasks", {}

        if "导出" in text and "任务" in text:
            return "export_tasks", {}

        if "天气" in text:
            city = re.sub(r"帮我查一下|查一下|天气怎么样|天气如何|现在|请问|我想知道|的|天气", "", text)
            city = city.strip("，。！! ")
            return "query_weather", {"city": city or "广州"}

        if match := re.search(r"计算(.+)", text):
            return "calculate", {"expression": match.group(1)}

        task_words = ["作业", "实验", "报告", "会议", "考试", "复习", "提交", "项目", "答辩"]
        if any(word in text for word in task_words) or any(word in text for word in ["帮我记下来", "提醒我", "待办"]):
            due = self._extract_due(text)
            title = re.sub(r"^(帮我|请)?(记下来|记一下|提醒我|要|需要|想|计划|准备|创建?)", "", text)
            if due:
                title = title.replace(due, "").replace("前", "")
            title = title.strip("，。！! ")
            return "add_task", {"title": title or text, "due": due, "priority": "普通"}

        if re.search(r"记一下[：:]", text) or "笔记" in text:
            content = re.sub(r"^(记一下|笔记|帮我记一下|备注)[：:，,]?", "", text).strip()
            return "save_note", {"content": content or text}

        return "reply", {"text": "我可以帮你添加任务、查看待办、完成任务、保存笔记、查询天气、做四则运算和导出任务清单。"}

    @staticmethod
    def _extract_due(text: str) -> str:
        due_patterns = [
            r"周[一二三四五六日天](上午|下午|晚上|早上|[0-9点:：]*)",
            r"[0-9]{1,2}月[0-9]{1,2}[日号]?(上午|下午|晚上|早上|[0-9点:：]*)",
            r"今天(上午|下午|晚上|早上|[0-9点:：]*)",
            r"明天(上午|下午|晚上|早上|[0-9点:：]*)",
        ]
        for pattern in due_patterns:
            if match := re.search(pattern, text):
                return match.group(0)
        return "未设置"

    # ---------- 执行与回复 ----------
    def run(self, user_text: str) -> str:
        intent, arguments = self.understand(user_text)
        if intent == "reply":
            return arguments["text"]
        handlers = {
            "add_task": self.add_task,
            "list_tasks": self.list_tasks,
            "finish_task": self.finish_task,
            "save_note": self.save_note,
            "query_weather": self.query_weather,
            "calculate": self.calculate,
            "export_tasks": self.export_tasks,
        }
        return handlers[intent](**arguments)


def interactive() -> None:
    agent = OfficeAgent()
    print("课程任务智能体已启动。输入“退出”结束对话。")
    while True:
        try:
            user_text = input("你：").strip()
        except EOFError:
            break
        if user_text in {"退出", "exit", "quit"}:
            print("智能体：再见，祝你任务顺利。")
            break
        if not user_text:
            continue
        print("智能体：" + agent.run(user_text))


def demo() -> None:
    agent = OfficeAgent()
    samples = [
        "帮我记下来 周五18:00前交软件工程作业",
        "帮我记一下 明天上午复习智能体课件",
        "我有哪些任务",
        "完成第1个任务",
        "广州天气怎么样",
        "计算 (12 + 8) * 3 / 2",
        "记一下：Agent循环是理解、工具调用、观察、回复",
        "导出任务",
    ]
    for text in samples:
        print(f"你：{text}")
        print(f"智能体：{agent.run(text)}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="课程任务与笔记智能体")
    parser.add_argument("--say", help="单轮执行一句自然语言指令")
    parser.add_argument("--demo", action="store_true", help="运行内置演示对话")
    args = parser.parse_args()

    if args.demo:
        demo()
    elif args.say:
        print(OfficeAgent().run(args.say))
    else:
        interactive()


if __name__ == "__main__":
    main()
