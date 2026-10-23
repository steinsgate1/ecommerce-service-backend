from jinja2 import Template
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from atguigu.clients.llm_client import get_llm
from atguigu.domain.message import UserMessage, Session, BotMessage
from atguigu.prompt.load_history import LoadHistory
from atguigu.prompt.load_prompt import load_prompt


class ChitchatResponder:
    async def response(self, user_message: UserMessage,
                 session: Session) -> list[BotMessage]:
        # jinja加载渲染模板提示词
        history = LoadHistory.load(session)
        template = load_prompt("chitchat")

        prompt = PromptTemplate(template=template,template_format="jinja2")

        chain = prompt | get_llm() | StrOutputParser()

        response = await chain.ainvoke({'history':history,'user_message':user_message})

        return [BotMessage(text=response)]



