from atguigu.chitchat.chitchat_reponder import ChitchatResponder
from atguigu.domain.message import DialogueState, UserMessage, BotMessage


class ChitchatHandler:
    def __init__(self,responder:ChitchatResponder):
        # 依赖注入
        self.responder = responder

    async def handle(self,state:DialogueState,user_message:UserMessage) -> list[BotMessage]:
        """ 1. 从 `state.shared.current_session()` 中取得当前 Session。
            2. 读取 Session 中已经完成的 `turns`。
            3. 将当前用户消息和历史 Turns 交给 `ChitchatResponder.respond()`。
            4. 返回 Responder 生成的 `BotMessage` 列表。"""
        session = state.shared.current_session

        return await self.responder.response(user_message,session)

