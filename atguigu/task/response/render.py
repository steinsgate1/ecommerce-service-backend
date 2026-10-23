from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from atguigu.clients.llm_client import get_llm
from atguigu.domain.message import UserMessage, DialogueState, BotMessage
from atguigu.prompt.load_history import LoadHistory
from atguigu.task.response.model import ResponseTemplate, ResponseMode
from jinja2 import Template


class ResponseRender:
    async def render(
            self,
            template:ResponseTemplate,
            state:DialogueState,
            user_message:UserMessage) -> BotMessage|None:
        if template.mode is ResponseMode.STATIC:
            rendered_text = Template(template.text).render(slots=state.task.active.slots)
            return BotMessage(text=rendered_text)

        if template.mode is ResponseMode.REPHRASE:
            rendered_text = Template(template.text).render(slots=state.task.active.slots)
            text = await self._call_llm(template.prompt,state,
                user_message,
                current_response=rendered_text,)
            return BotMessage(text=text)

        if template.mode is ResponseMode.GENERATE:
            text = await self._call_llm(
                template.prompt,
                state,
                user_message,
            )
            return BotMessage(text=text)

    async def _call_llm(self, prompt:str,
                        state:DialogueState,
                        user_message:UserMessage,
                        current_response=""):
        prompt = PromptTemplate.from_template(
            prompt,
            template_format="jinja2",
        )
        chain = prompt | get_llm() |StrOutputParser()
        session = state.shared.current_session
        return await chain.ainvoke({
            "history":LoadHistory.load(session),
            "user_message":LoadHistory.render_user_message(user_message),
            "current_response":current_response,
        })
