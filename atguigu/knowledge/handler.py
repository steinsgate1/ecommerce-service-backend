import asyncio

from atguigu.domain.message import DialogueState, UserMessage, BotMessage
from atguigu.knowledge.intents import KnowledgeIntent
from atguigu.knowledge.registry import KnowledgeProviderRegistry
from atguigu.knowledge.responder import KnowledgeResponder


class KnowledgeHandler:
    def __init__(
            self,
            knowledge_intents: dict[str, KnowledgeIntent],
            provider_registry: KnowledgeProviderRegistry,
            knowledge_responder: KnowledgeResponder,
    ) -> None:
        self.knowledge_intents = knowledge_intents
        self.provider_registry = provider_registry
        self.knowledge_responder = knowledge_responder

    async def handle(self,intents: list[str],
                    state: DialogueState,
                    user_message: UserMessage,) -> list[BotMessage]:
        provider_ids = self._get_provider_ids_by_intents(
            intents
        )

        retrieve_coroutines = [self.provider_registry.get(provider_id).retrieve(state,user_message) for provider_id in provider_ids]

        # 返回的形式是【【】，【】，【】】
        provider_chunks = await asyncio.gather(*retrieve_coroutines)

        # 解开嵌套
        chunks = [
            chunk
            for current_chunks in provider_chunks
            for chunk in current_chunks
        ]

        return await self.knowledge_responder.respond(user_message,state.shared.current_session,chunks)

    def _get_provider_ids_by_intents(self, intents):
        # 从注册的intent中寻找符合的intent，直接获取可能有幻觉
        # return [intent for intent in intents]
        provider_ids: list[str] = []
        for intent in intents:
            provider_ids.extend(self.knowledge_intents[intent].provider_ids)
        # 去重
        return list(set(provider_ids))

if __name__ == '__main__':
    """
    列表推导式	[chunk for current_chunks in provider_chunks for chunk in current_chunks]	✅ 是	稍高（会创建一个完整的临时列表）
    for + extend	for provider_chunk in provider_chunks: chunks.extend(provider_chunk)	❌ 否	更低（直接修改原列表，不创建中间列表）
"""
    provider_chunks = [[1,2,3],[4,5,6]]
    chunks = []

    for provider_chunk in provider_chunks:
        chunks.extend(provider_chunk)


    print(chunks)
