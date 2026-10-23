import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, AsyncGenerator

from fastapi import APIRouter, FastAPI
from fastapi.params import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from atguigu.api.schema import ChatMessage, ChatRequest, ChatResponse, HistoryResponse, HistoryMessage, ChatObject
from atguigu.chitchat.chichat_handler import ChitchatHandler
from atguigu.chitchat.chitchat_reponder import ChitchatResponder
from atguigu.clarify.responder import ClarifyResponder
from atguigu.clients import database

from atguigu.clients.database import init_db_engine, close_db_engine, session_factory
from atguigu.clients.http import init_http_client, close_http_client
from atguigu.clients.llm_client import get_llm
from atguigu.domain.message import UserMessage, MessageType, MessageObject, ProcessResult, DialogueState
from atguigu.engine.dialogue_engine import DialogueEngine
from atguigu.knowledge.handler import KnowledgeHandler
from atguigu.knowledge.intents import KNOWLEDGE_INTENTS
from atguigu.knowledge.providers import ProductAPIProvider, OrderAPIProvider, FAQProvider, RAGProvider
from atguigu.knowledge.registry import KnowledgeProviderRegistry
from atguigu.knowledge.responder import KnowledgeResponder
from atguigu.memory.history_compressor import HistoryCompressor
from atguigu.plan.turn_plan import TurnPlanner
from atguigu.plan.validator import TurnPlanValidator
from atguigu.repository.dialogue_state_repository import DialogueStateRepository
from atguigu.service.dialogue_service import DialogueService
from atguigu.task.action.builder import build_action_runner
from atguigu.task.action.runner import ActionRunner
from atguigu.task.command.processor import CommandProcessor
from atguigu.task.flow.executor import FlowExecutor
from atguigu.task.flow.loader import FlowLoder
from atguigu.task.handler import TaskHandler
from atguigu.task.lifecycle.responder import TaskLifecycleResponder
from atguigu.task.response.render import ResponseRender

# 使用全局单例，避免重复加载
_dialogue_engine: Optional[DialogueEngine] = None

chat_router = APIRouter()

# 利用生命周期函数初始化数据连接
def _build_dialogue_engine() -> DialogueEngine:
    loader = FlowLoder()
    flow_catalog = loader.load(Path(__file__).parents[2] / "user_flows.yml")
    return DialogueEngine(
        turn_planner=TurnPlanner(),
        task_handler=TaskHandler(CommandProcessor(), flow_catalog, FlowExecutor(ResponseRender(), build_action_runner()),TaskLifecycleResponder(flow_catalog)),
        chitchat_handler=ChitchatHandler(ChitchatResponder()),
        clarify_responder=ClarifyResponder(),
        knowledge_handler=KnowledgeHandler(KNOWLEDGE_INTENTS,KnowledgeProviderRegistry([
                    ProductAPIProvider(),
                    OrderAPIProvider(),
                    FAQProvider(),
                    RAGProvider(),
                ]),KnowledgeResponder()),
        turn_plan_validator=TurnPlanValidator(),
        history_compressor=HistoryCompressor(),
    )


def init_dialogue_engine():
    global _dialogue_engine
    if _dialogue_engine is None:
        _dialogue_engine = _build_dialogue_engine()
    return _dialogue_engine


@asynccontextmanager
async def lifespan(app:FastAPI):
    init_db_engine()
    init_http_client()
    init_dialogue_engine()
    # 预热 LLM：首次调用的连接/模型冷启动开销较大，放在启动阶段完成
    try:
        await get_llm().ainvoke("hi")
    except Exception:
        pass
    # TODO 关闭dialogue_engine
    yield
    await close_db_engine()
    await close_http_client()

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """获取会话（作为依赖注入使用）"""
    async with database.session_factory() as session:
        yield session  # ✅ 使用 yield，会话在请求结束后关闭

async def get_dialogue_repository(session:AsyncSession = Depends(get_session)):
    return DialogueStateRepository(session)

async def get_dialogue_service(dialogue_state_repository:DialogueStateRepository = Depends(get_dialogue_repository)):
    return DialogueService(dialogue_state_repository,_dialogue_engine)


def _build_user_message(chat_request):
    return UserMessage(chat_request.sender_id,
                       message_id=(chat_request.message_id or str(uuid.uuid4())),
                       text=chat_request.text,
                       type=(MessageType.TEXT if chat_request.text is not None else MessageType.OBJECT),
                       object=(MessageObject(
                                type=chat_request.object.type,
                                id=chat_request.object.id,
                                title=chat_request.object.title,
                                attributes=dict(chat_request.object.attributes))if chat_request.object is not None else None)
                       )


def _build_chat_object(message_object)-> ChatObject | None:
    if message_object is None:
        return None

    return ChatObject(
        type=message_object.type,
        id=message_object.id,
        title=message_object.title,
        attributes=dict(message_object.attributes),
    )


def _build_chat_response(process_result:ProcessResult) ->ChatResponse:
    return ChatResponse(
        sender_id=process_result.sender_id,
        message_id=process_result.message_id,
        messages=[
            ChatMessage(
                text=message.text,
                object=_build_chat_object(message.object),
            )
            for message in process_result.messages
        ],
    )


@chat_router.post("/api/chat")
async def chat(chat_request: ChatRequest,dialogue_service:DialogueService = Depends(get_dialogue_service)) -> ChatResponse:
    user_message = _build_user_message(chat_request)

    process_result:ProcessResult = await dialogue_service.process_message(user_message)

    return _build_chat_response(process_result)


def _build_history_message(state:DialogueState)->list[HistoryMessage]:
    history_messages = []
    session = state.shared.current_session

    if not session:
        return history_messages

    for turn in session.turns:
        if turn.user_message:
            history_messages.append(HistoryMessage(role='user',
            text=turn.user_message.text))
        if turn.bot_messages:
            for message in turn.bot_messages:
                history_messages.append(HistoryMessage(role='bot',text=message.text))

    return history_messages


@chat_router.get("/api/chat/history")
async def history(sender_id:str,dialogue_state_repository:DialogueStateRepository = Depends(get_dialogue_repository)) -> HistoryResponse:
    state = await dialogue_state_repository.load_state(sender_id)

    history_messages = _build_history_message(state)

    return HistoryResponse(
        sender_id=sender_id,
        messages=history_messages
    )

if __name__ == '__main__':
    print((Path(__file__).parents[0] / "user_flows.yml"))