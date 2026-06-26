"""
Step 30 - 智能客服多 Agent MVP

这个文件把「智能客服系统设计.md」压缩成一个能直接运行的学习版 MVP。

它刻意沿用 step29_integrated_pv3_mini.py 里你已经学过的写法：
- dataclass: 表示消息、文档、工具结果、工单等结构化数据
- TypedDict: 表示整条客服流程里不断流转的 AgentState
- invoke / run / execute / answer / review: 区分不同抽象层级的方法
- Supervisor: 像 graph 一样统一调度意图路由、知识检索、工单处理、合规审查
- Memory + Tools: 用进程内 mock 版本模拟短期记忆、长期知识库和 MCP 工具层

运行：
    python3 learn_agent/agent_csr_mvp/step30_csr_mvp.py
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Literal, TypedDict


Intent = Literal["knowledge_rag", "ticket_handler", "compliance", "fallback"]


@dataclass
class Settings:
    """MVP 级别配置：先把可调整项集中放在一起。"""

    short_memory_max_messages: int = 8
    knowledge_top_k: int = 2
    compliance_block_words: tuple[str, ...] = ("稳赚", "保证收益", "内部渠道")
    compliance_sensitive_patterns: tuple[str, ...] = (r"\d{17}[\dXx]", r"\b\d{11}\b")


@dataclass
class Message:
    role: Literal["user", "assistant", "system"]
    content: str


@dataclass
class KnowledgeDoc:
    doc_id: str
    title: str
    content: str
    tags: list[str] = field(default_factory=list)


@dataclass
class KnowledgeHit:
    doc: KnowledgeDoc
    score: int


@dataclass
class Ticket:
    ticket_id: str
    user_id: str
    category: str
    summary: str
    status: str = "open"


@dataclass
class ToolDescriptor:
    name: str
    description: str
    source: str = "local_mcp_mock"


@dataclass
class ToolCallResult:
    tool_name: str
    arguments: dict[str, Any]
    output: Any = None
    error: str | None = None


@dataclass
class IntentResult:
    intent: Intent
    confidence: float
    reason: str


@dataclass
class ComplianceResult:
    passed: bool
    issues: list[str]
    safe_text: str


@dataclass
class TraceSpan:
    name: str
    detail: str


class AgentState(TypedDict):
    messages: list[Message]
    user_id: str
    session_id: str
    user_text: str
    short_memory_context: str
    intent: str
    intent_confidence: float
    route_reason: str
    current_agent: str
    sub_results: dict[str, Any]
    tool_records: list[ToolCallResult]
    compliance_passed: bool
    compliance_issues: list[str]
    final_response: str
    retry_count: int
    human_handoff: bool
    trace: list[TraceSpan]


def last_user_text(messages: list[Message]) -> str:
    return next((m.content for m in reversed(messages) if m.role == "user"), "")


def extract_order_id(text: str) -> str | None:
    match = re.search(r"\b[A-Z]\d{4,8}\b", text.upper())
    return match.group(0) if match else None


class ShortTermMemoryStore:
    """短期记忆：MVP 里用 dict 模拟 Redis 最近 N 轮对话。"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.sessions: dict[str, list[Message]] = {}

    def load(self, session_id: str) -> list[Message]:
        return self.sessions.get(session_id, []).copy()

    def build_prompt_block(self, session_id: str) -> str:
        messages = self.load(session_id)
        if not messages:
            return "暂无历史对话。"
        lines = [f"- {m.role}: {m.content}" for m in messages[-self.settings.short_memory_max_messages :]]
        return "最近对话：\n" + "\n".join(lines)

    def append_turn(self, session_id: str, user_text: str, assistant_text: str) -> None:
        messages = self.sessions.setdefault(session_id, [])
        messages.extend([Message("user", user_text), Message("assistant", assistant_text)])
        keep = self.settings.short_memory_max_messages
        if len(messages) > keep:
            self.sessions[session_id] = messages[-keep:]


class KnowledgeBase:
    """长期记忆的一部分：用本地文档模拟企业知识库 / 向量库。"""

    def __init__(self) -> None:
        self.docs = [
            KnowledgeDoc(
                "refund_policy",
                "退款政策",
                "已发货订单如需退款，请先申请售后。未发货订单通常可直接取消；已签收订单需要上传问题照片，客服会在 24 小时内处理。",
                ["退款", "退钱", "售后"],
            ),
            KnowledgeDoc(
                "invoice_policy",
                "发票说明",
                "电子发票一般会在付款后 1 个工作日内开具。企业抬头需要填写税号，提交后如需修改请创建工单。",
                ["发票", "税号", "企业"],
            ),
            KnowledgeDoc(
                "delivery_policy",
                "物流说明",
                "普通订单发货后 24 小时内会更新物流。超过 48 小时没有物流轨迹时，建议创建催办工单。",
                ["物流", "快递", "配送", "催"],
            ),
            KnowledgeDoc(
                "account_security",
                "账号安全",
                "客服不会索要密码、短信验证码或完整身份证号。涉及账号异常时，只能通过官方入口验证。",
                ["账号", "验证码", "身份证", "安全"],
            ),
        ]

    def search(self, query: str, *, top_k: int = 2) -> list[KnowledgeHit]:
        query_chars = set(query)
        hits: list[KnowledgeHit] = []
        for doc in self.docs:
            text = doc.title + doc.content + "".join(doc.tags)
            score = sum(1 for ch in query_chars if ch in text)
            if any(tag in query for tag in doc.tags):
                score += 8
            if score > 0:
                hits.append(KnowledgeHit(doc, score))
        return sorted(hits, key=lambda h: h.score, reverse=True)[:top_k]


class TicketStore:
    """长期记忆的另一部分：保存历史工单。"""

    def __init__(self) -> None:
        self._next_id = 1001
        self.tickets: dict[str, Ticket] = {}

    def create(self, *, user_id: str, category: str, summary: str) -> Ticket:
        ticket_id = f"TK{self._next_id}"
        self._next_id += 1
        ticket = Ticket(ticket_id=ticket_id, user_id=user_id, category=category, summary=summary)
        self.tickets[ticket_id] = ticket
        return ticket


class LocalMcpToolRegistry:
    """MCP 工具协议的学习版：保留 tools/list 和 tools/call 的形状。"""

    def __init__(self) -> None:
        self.orders = {
            "A1001": {"status": "已发货", "carrier": "顺丰", "eta": "明天 18:00 前"},
            "A1002": {"status": "待售后审核", "carrier": "-", "eta": "-"},
            "B2001": {"status": "已签收", "carrier": "京东物流", "eta": "已完成"},
        }
        self.tools: dict[str, tuple[str, Callable[[dict[str, Any]], Any]]] = {
            "order_query": ("查询订单状态", self._order_query),
            "risk_check": ("检查回复里是否包含明显风险词", self._risk_check),
        }

    def list_tools(self) -> list[ToolDescriptor]:
        return [ToolDescriptor(name, desc) for name, (desc, _) in self.tools.items()]

    def call(self, name: str, arguments: dict[str, Any]) -> ToolCallResult:
        if name not in self.tools:
            return ToolCallResult(name, arguments, error=f"未知工具：{name}")
        try:
            _, func = self.tools[name]
            return ToolCallResult(name, arguments, output=func(arguments))
        except Exception as exc:
            return ToolCallResult(name, arguments, error=f"{type(exc).__name__}: {exc}")

    def _order_query(self, arguments: dict[str, Any]) -> dict[str, Any]:
        order_id = str(arguments.get("order_id") or "").upper()
        if not order_id:
            raise ValueError("order_id 不能为空")
        return self.orders.get(order_id, {"status": "未找到", "carrier": "-", "eta": "-"})

    def _risk_check(self, arguments: dict[str, Any]) -> dict[str, Any]:
        text = str(arguments.get("text") or "")
        risk_words = [word for word in ("稳赚", "保证收益", "内部渠道") if word in text]
        return {"passed": not risk_words, "risk_words": risk_words}


class IntentRouterAgent:
    """意图路由 Agent：只负责判断下一步该交给谁。"""

    def route(self, user_text: str) -> IntentResult:
        if any(word in user_text for word in ("稳赚", "保证收益", "身份证号", "验证码")):
            return IntentResult("compliance", 0.92, "用户问题涉及敏感承诺或隐私安全")
        if any(word in user_text for word in ("投诉", "工单", "人工", "催一下", "坏了", "没收到")):
            return IntentResult("ticket_handler", 0.88, "用户需要人工跟进或工单处理")
        if extract_order_id(user_text) or any(word in user_text for word in ("订单", "物流", "快递", "售后")):
            return IntentResult("ticket_handler", 0.8, "用户在询问订单/物流/售后状态")
        if any(word in user_text for word in ("退款", "退钱", "发票", "怎么", "规则", "政策", "账号")):
            return IntentResult("knowledge_rag", 0.84, "用户在询问知识库可回答的问题")
        return IntentResult("fallback", 0.55, "没有命中明确意图，走兜底回答")


class KnowledgeRagAgent:
    """知识检索 Agent：MVP 里用关键词打分模拟 RAG。"""

    def __init__(self, kb: KnowledgeBase, settings: Settings):
        self.kb = kb
        self.settings = settings

    def answer(self, *, user_text: str, memory_context: str) -> dict[str, Any]:
        hits = self.kb.search(user_text, top_k=self.settings.knowledge_top_k)
        if not hits:
            return {
                "answer": "我暂时没有在知识库里找到对应规则，建议帮你创建工单让人工客服确认。",
                "sources": [],
            }

        bullet_lines = [f"- {hit.doc.title}: {hit.doc.content}" for hit in hits]
        sources = [hit.doc.doc_id for hit in hits]
        answer = "我查到的规则是：\n" + "\n".join(bullet_lines)
        if "暂无历史对话" not in memory_context:
            answer += "\n\n我也参考了本轮会话的最近上下文。"
        return {"answer": answer, "sources": sources}


class TicketAgent:
    """工单处理 Agent：负责查订单、创建工单，并返回可执行的处理结果。"""

    def __init__(self, ticket_store: TicketStore, tools: LocalMcpToolRegistry):
        self.ticket_store = ticket_store
        self.tools = tools

    def handle(self, *, user_id: str, user_text: str) -> dict[str, Any]:
        tool_records: list[ToolCallResult] = []
        order_id = extract_order_id(user_text)
        order_text = ""

        if order_id:
            record = self.tools.call("order_query", {"order_id": order_id})
            tool_records.append(record)
            if record.error:
                order_text = f"订单 {order_id} 查询失败：{record.error}"
            else:
                output = record.output
                order_text = (
                    f"订单 {order_id} 当前状态：{output['status']}；"
                    f"承运方：{output['carrier']}；预计时间：{output['eta']}。"
                )

        needs_ticket = any(word in user_text for word in ("投诉", "工单", "人工", "催一下", "坏了", "没收到"))
        ticket: Ticket | None = None
        if needs_ticket:
            ticket = self.ticket_store.create(
                user_id=user_id,
                category="customer_support",
                summary=user_text[:80],
            )

        if ticket and order_text:
            answer = f"{order_text}\n我已经帮你创建工单 {ticket.ticket_id}，状态为 {ticket.status}，客服会继续跟进。"
        elif ticket:
            answer = f"我已经帮你创建工单 {ticket.ticket_id}，状态为 {ticket.status}，客服会继续跟进。"
        elif order_text:
            answer = order_text
        else:
            answer = "这个问题可能需要更多订单信息。你可以补充订单号，或让我帮你创建工单。"

        return {"answer": answer, "ticket": ticket, "tool_records": tool_records}


class ComplianceAgent:
    """合规审查 Agent：所有对用户的回复都要经过这里。"""

    def __init__(self, settings: Settings, tools: LocalMcpToolRegistry):
        self.settings = settings
        self.tools = tools

    def review(self, text: str) -> ComplianceResult:
        issues: list[str] = []

        risk_record = self.tools.call("risk_check", {"text": text})
        if not risk_record.error and risk_record.output and not risk_record.output["passed"]:
            issues.extend([f"风险词：{word}" for word in risk_record.output["risk_words"]])

        for word in self.settings.compliance_block_words:
            if word in text and f"风险词：{word}" not in issues:
                issues.append(f"风险词：{word}")

        for pattern in self.settings.compliance_sensitive_patterns:
            if re.search(pattern, text):
                issues.append(f"疑似敏感信息：{pattern}")

        if issues:
            safe_text = "这个回复需要人工客服复核后再发送。我已经为你转人工处理。"
            return ComplianceResult(False, issues, safe_text)
        return ComplianceResult(True, [], text)


class SupervisorAgent:
    """Supervisor 编排 Agent：客服系统的大脑，只做调度和汇总。"""

    def __init__(
        self,
        router: IntentRouterAgent,
        rag: KnowledgeRagAgent,
        ticket_agent: TicketAgent,
        compliance: ComplianceAgent,
        ticket_store: TicketStore,
    ) -> None:
        self.router = router
        self.rag = rag
        self.ticket_agent = ticket_agent
        self.compliance = compliance
        self.ticket_store = ticket_store

    def invoke(self, state: AgentState) -> AgentState:
        state["trace"].append(TraceSpan("supervisor.start", "接收用户请求"))

        state["current_agent"] = "intent_router"
        route = self.router.route(state["user_text"])
        state["intent"] = route.intent
        state["intent_confidence"] = route.confidence
        state["route_reason"] = route.reason
        state["trace"].append(TraceSpan("intent_router.route", f"{route.intent}: {route.reason}"))

        draft_response = ""
        if route.intent == "knowledge_rag":
            state["current_agent"] = "knowledge_rag"
            result = self.rag.answer(
                user_text=state["user_text"],
                memory_context=state["short_memory_context"],
            )
            state["sub_results"]["knowledge_rag"] = result
            draft_response = result["answer"]
            state["trace"].append(TraceSpan("knowledge_rag.answer", f"sources={result['sources']}"))

        elif route.intent == "ticket_handler":
            state["current_agent"] = "ticket_handler"
            result = self.ticket_agent.handle(user_id=state["user_id"], user_text=state["user_text"])
            state["sub_results"]["ticket_handler"] = result
            state["tool_records"].extend(result["tool_records"])
            draft_response = result["answer"]
            state["trace"].append(TraceSpan("ticket_handler.handle", "订单查询/工单处理完成"))

        elif route.intent == "compliance":
            draft_response = (
                "为了保护你的账号和隐私，我不能处理敏感身份信息，也不能做超出规则的承诺。"
                "建议通过官方入口提交资料，必要时我可以帮你转人工。"
            )
            state["sub_results"]["compliance_intent"] = {"answer": draft_response}
            state["trace"].append(TraceSpan("compliance.intent", "用户问题先进入安全回复"))

        else:
            draft_response = "我可以帮你查询退款、发票、物流、订单状态，也可以帮你创建客服工单。"
            state["sub_results"]["fallback"] = {"answer": draft_response}
            state["trace"].append(TraceSpan("fallback.answer", "返回能力范围提示"))

        state["current_agent"] = "compliance_review"
        review = self.compliance.review(draft_response)
        state["compliance_passed"] = review.passed
        state["compliance_issues"] = review.issues
        state["final_response"] = review.safe_text
        state["trace"].append(TraceSpan("compliance.review", "通过" if review.passed else ",".join(review.issues)))

        if not review.passed:
            ticket = self.ticket_store.create(
                user_id=state["user_id"],
                category="compliance_review",
                summary=state["user_text"][:80],
            )
            state["human_handoff"] = True
            state["sub_results"]["handoff_ticket"] = ticket
            state["final_response"] += f" 工单号：{ticket.ticket_id}。"
            state["trace"].append(TraceSpan("human_handoff.create_ticket", ticket.ticket_id))

        state["current_agent"] = "supervisor"
        state["trace"].append(TraceSpan("supervisor.end", "返回最终回复"))
        return state


class CustomerServiceGraph:
    """Graph 层：负责准备 state，并把 state 交给 Supervisor。"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.short_memory = ShortTermMemoryStore(settings)
        self.kb = KnowledgeBase()
        self.ticket_store = TicketStore()
        self.tools = LocalMcpToolRegistry()
        self.supervisor = SupervisorAgent(
            router=IntentRouterAgent(),
            rag=KnowledgeRagAgent(self.kb, settings),
            ticket_agent=TicketAgent(self.ticket_store, self.tools),
            compliance=ComplianceAgent(settings, self.tools),
            ticket_store=self.ticket_store,
        )

    def invoke(self, state: AgentState) -> AgentState:
        state["short_memory_context"] = self.short_memory.build_prompt_block(state["session_id"])
        return self.supervisor.invoke(state)


class Chatbot:
    """对外入口：把用户一句话包装成 state，再把最终回复存回短期记忆。"""

    def __init__(self, *, user_id: str = "u_001", session_id: str = "s_001") -> None:
        self.settings = Settings()
        self.user_id = user_id
        self.session_id = session_id
        self.graph = CustomerServiceGraph(self.settings)

    def chat(self, user_text: str) -> AgentState:
        previous_messages = self.graph.short_memory.load(self.session_id)
        messages = [*previous_messages, Message("user", user_text)]
        state: AgentState = {
            "messages": messages,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "user_text": last_user_text(messages),
            "short_memory_context": "",
            "intent": "",
            "intent_confidence": 0.0,
            "route_reason": "",
            "current_agent": "",
            "sub_results": {},
            "tool_records": [],
            "compliance_passed": False,
            "compliance_issues": [],
            "final_response": "",
            "retry_count": 0,
            "human_handoff": False,
            "trace": [],
        }

        out = self.graph.invoke(state)
        self.graph.short_memory.append_turn(self.session_id, user_text, out["final_response"])
        return out


def print_state_summary(state: AgentState) -> None:
    print("intent:", state["intent"], "| confidence:", state["intent_confidence"])
    print("reason:", state["route_reason"])
    if state["tool_records"]:
        for record in state["tool_records"]:
            print("tool:", record.tool_name, "| args:", record.arguments, "| error:", record.error)
    print("compliance_passed:", state["compliance_passed"])
    print("assistant:", state["final_response"])
    print("trace:", " -> ".join(span.name for span in state["trace"]))


def main() -> None:
    bot = Chatbot()
    demo_questions = [
        "我想退钱，退款流程是怎样的？",
        "帮我查一下订单 A1001 的物流",
        "订单 A1002 一直没处理，帮我催一下并创建工单",
        "客服会不会要我的身份证号和验证码？",
    ]

    for question in demo_questions:
        print("\n用户：", question)
        state = bot.chat(question)
        print_state_summary(state)


if __name__ == "__main__":
    main()
