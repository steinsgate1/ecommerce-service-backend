from pydantic import TypeAdapter
from sqlalchemy import select, update
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from atguigu.domain.message import DialogueState
from atguigu.models.dialogue_state import DialogueStateRecord

# 声明pydantic适配器，再利用适配器工具进行序列化操作
DIALOGUE_STATE_ADAPTER = TypeAdapter(DialogueState)

class DialogueStateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def load_state(self, sender_id) -> DialogueState:
        sql = select(DialogueStateRecord).where(DialogueStateRecord.sender_id == sender_id)

        result = await self.session.execute(sql)
        record = result.scalar_one_or_none()

        if record is None:
            return DialogueState(sender_id=sender_id)

        # 利用适配器序列化结果
        return DIALOGUE_STATE_ADAPTER.validate_json(record.state_json)

    async def save_state(self, state: DialogueState):
        """ 1. 使用 `TypeAdapter` 将 `DialogueState` 转换成 JSON 字符串。
            2. 使用 `sender_id` 和 `state_json` 构造 INSERT 语句。
            3. 如果 `sender_id` 已经存在，则更新原记录的 `state_json`。
            4. 执行 SQL 并提交事务。"""
        state_json = DIALOGUE_STATE_ADAPTER.dump_json(state).decode("utf-8")
        sql = (insert(DialogueStateRecord).values(
            sender_id = state.sender_id,
            state_json = state_json))
        sql = sql.on_duplicate_key_update(state_json = sql.inserted.state_json)
        await self.session.execute(sql)
        await self.session.commit()
