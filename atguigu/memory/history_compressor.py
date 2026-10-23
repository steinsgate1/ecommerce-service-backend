"""多轮对话历史压缩。

策略：保留前 N 轮 + 中间轮次摘要 + 后 N 轮，完整历史仍保存在 session.turns 中，
不进入模型。压缩后的摘要写回 session.summary，供 LoadHistory 渲染时使用。
"""

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from atguigu.clients.llm_client import get_llm
from atguigu.domain.message import Session
from atguigu.prompt.load_history import LoadHistory

DEFAULT_FIRST_N = 3
DEFAULT_LAST_N = 2


class HistoryCompressor:
    def __init__(
        self,
        first_n: int = DEFAULT_FIRST_N,
        last_n: int = DEFAULT_LAST_N,
    ) -> None:
        self.first_n = first_n
        self.last_n = last_n

    async def compress(self, session: Session) -> None:
        """根据当前 session.turns 重新生成中间轮次摘要，写入 session.summary。"""
        turns = session.turns

        # 未超过保留窗口，无需压缩
        if len(turns) <= self.first_n + self.last_n:
            session.summary = ""
            return

        middle_turns = turns[self.first_n:-self.last_n]
        middle_text = LoadHistory.render_turns(middle_turns)
        session.summary = await self._summarize(middle_text)

    async def _summarize(self, text: str) -> str:
        prompt = PromptTemplate.from_template(
            "请将以下客服对话历史压缩成一段简洁摘要（不超过200字）。"
            "必须保留：用户核心诉求、已确认的订单号/商品、已执行的操作与结果、关键决策与约定。"
            "不要输出额外解释。\n\n{text}\n\n摘要："
        )
        chain = prompt | get_llm() | StrOutputParser()
        return await chain.ainvoke({"text": text})
