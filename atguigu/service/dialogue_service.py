from atguigu.domain.message import UserMessage, ProcessResult
from atguigu.engine.dialogue_engine import DialogueEngine
from atguigu.repository.dialogue_state_repository import DialogueStateRepository


class DialogueService:

    def __init__(self,
                 dialogue_state_repository:DialogueStateRepository,
                 dialogue_engine:DialogueEngine)->None:
        self.dialogue_state_repository = dialogue_state_repository
        self.dialogue_engine = dialogue_engine


    async def process_message(self,user_message:UserMessage) -> ProcessResult:
        # TODO 消息处理
        state = await self.dialogue_state_repository.load_state(user_message.sender_id)

        process_result = await self.dialogue_engine.process_message(state,user_message)

        # 保存消息记录
        await self.dialogue_state_repository.save_state(state)

        return process_result

if __name__ == '__main__':
    print()