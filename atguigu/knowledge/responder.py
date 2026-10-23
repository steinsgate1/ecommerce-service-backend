from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from atguigu.clients.llm_client import get_llm
from atguigu.domain.message import UserMessage, Session, BotMessage
from atguigu.knowledge.providers import KnowledgeChunk
from atguigu.prompt.load_history import LoadHistory
from atguigu.prompt.load_prompt import load_prompt


class KnowledgeResponder:
    async def respond(self, user_message: UserMessage,
        session: Session,
        chunks: list[KnowledgeChunk]):
        user_message = LoadHistory.render_user_message(
            user_message
        )
        history = LoadHistory.load(session)
        knowledge_content = "\n\n".join(
            chunk.content for chunk in chunks
        )
        prompt_text = load_prompt("knowledge_respond")
        prompt = PromptTemplate.from_template(
            prompt_text,
            template_format="jinja2",
        )
        chain = prompt | get_llm() | StrOutputParser()

        response = await chain.ainvoke({
            "user_message": user_message,
            "history": history,
            "knowledge_content": knowledge_content,
        })

        return [BotMessage(text=response)]
