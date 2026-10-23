import time

from atguigu.chitchat.chichat_handler import ChitchatHandler
from atguigu.clarify.responder import ClarifyResponder
from atguigu.domain.message import ProcessResult, UserMessage, Turn, DialogueState, SharedState, Session, BotMessage, \
    FocusedObject, PendingIntents
from atguigu.knowledge.handler import KnowledgeHandler
from atguigu.knowledge.intents import KNOWLEDGE_INTENTS
from atguigu.plan.turn_plan import TurnPlanner
from atguigu.plan.models import ClarifyReason
from atguigu.plan.validator import TurnPlanValidator
from atguigu.memory.history_compressor import HistoryCompressor
from atguigu.task.command.models import Command, SetSlotsCommand
from atguigu.task.flow.model import FlowCatalog
from atguigu.task.flow.steps import CollectSlotStep
from atguigu.task.handler import TaskHandler


class DialogueEngine:
    def __init__(
            self,
            turn_planner: TurnPlanner,
            task_handler: TaskHandler,
            knowledge_handler: KnowledgeHandler,
            chitchat_handler: ChitchatHandler,
            clarify_responder: ClarifyResponder,
            turn_plan_validator: TurnPlanValidator,
            history_compressor: HistoryCompressor | None = None,
    ) -> None:
        self.turn_planner = turn_planner
        self.task_handler = task_handler
        self.knowledge_handler = knowledge_handler
        self.chitchat_handler = chitchat_handler
        self.clarify_responder = clarify_responder
        self.turn_plan_validator = turn_plan_validator
        self.history_compressor = history_compressor or HistoryCompressor()

    async def process_message(self, state:DialogueState, user_message:UserMessage)->ProcessResult:
        # 1.准备当前会话和本轮对话记录。
        # session
        self._prepare_session(state)

        turn = Turn.create_turn(user_message)

        if user_message.text is not None:
            messages = await self._handle_text_message(state,user_message)


        elif user_message.object is not None:
            messages = await self._handle_object_message(state,user_message)

        else:
            messages = []

        turn.bot_messages.extend(messages)
        state.shared.add_turn(turn)

        # 压缩中间历史：前3轮 + 摘要 + 后2轮，完整历史仍保存在 session.turns 中
        await self.history_compressor.compress(state.shared.current_session)

        return ProcessResult(
            sender_id=user_message.sender_id,
            message_id=user_message.message_id,
            messages=messages
        )

    async def _handle_text_message(self, state, user_message) -> list[BotMessage]:
        # TODO
        """ 1. 理解文本消息，形成当前轮次的处理计划。
            2. 检查处理计划是否明确、完整并且可以执行。
            3. 将消息交给任务、知识检索、闲聊或澄清模块。"""
        return await self._dispatch_by_plan(state, user_message)

    async def _dispatch_by_plan(self, state: DialogueState, user_message: UserMessage) -> list[BotMessage]:
        """规划 → 校验 → 分发到 task/knowledge/chitchat/clarify。"""
        turn_plan = await self.turn_planner.predict(state,user_message,self.task_handler.flow_catalog,KNOWLEDGE_INTENTS)

        validation = self.turn_plan_validator.validate(turn_plan,state,self.task_handler.flow_catalog,KNOWLEDGE_INTENTS)

        # 如果未通过校验，直接返回澄清回答
        if not validation.valid:
            # 因缺少咨询对象被澄清的知识意图：结构化暂存，
            # 等用户补发对象卡片后确定性消费（见 _handle_object_message）
            if (
                    validation.reason is ClarifyReason.MISSING_FOCUSED_OBJECT
                    and turn_plan.knowledge is not None
                    and turn_plan.knowledge.intents
            ):
                state.shared.pending_intents = PendingIntents(
                    intents=turn_plan.knowledge.intents,
                )
            return await self.clarify_responder.respond(
                state=state,
                user_message=user_message,
                reason=validation.reason,
            )

        # 本轮产生了可执行的新计划，旧的待补对象意图已被取代
        state.shared.pending_intents = None

        # 通过且有任务，执行任务流程
        if turn_plan.task is not None:
            return await self.task_handler.handle(
                command=turn_plan.task.commands,
                state=state,
                user_message=user_message,
            )

        # 通过有知识检索，执行知识检索
        elif turn_plan.knowledge is not None:
            if state.task.active:
                state.task.suspend_active()
            return await self.knowledge_handler.handle(
                state=state,
                user_message=user_message,
                intents=turn_plan.knowledge.intents,
            )

        # 如果当前有任务，暂停
        if state.task.active:
            state.task.suspend_active()
        # 都没有，执行闲聊
        return await self.chitchat_handler.handle(
            state=state,
            user_message=user_message,
        )

    async def _handle_object_message(self,
            state: DialogueState,
            user_message: UserMessage,

        ) -> list[BotMessage]:

        message_object = user_message.object
        object_type = message_object.type.strip().lower()
        if object_type in ("order", "product"):
            # 记为聚焦对象：知识咨询(requires_object)与 collect 自动补槽都依赖它
            state.shared.set_focused_object(
                FocusedObject(
                    type=object_type,
                    id=message_object.id,
                    title=message_object.title,
                    attributes=message_object.attributes,
                )
            )

        command = self._object_slot_command(
            message=user_message,
            state=state,
            flows=self.task_handler.flow_catalog,
        )

        if command is not None:
            return await self.task_handler.handle(
                command=[command],
                state=state,
                user_message=user_message,
            )

        # 上一轮知识意图因缺少对象被澄清：对象类型匹配时确定性执行，
        # 不再依赖 LLM 从历史重新推断意图
        pending = state.shared.pending_intents
        if pending is not None:
            matched = [
                intent_id
                for intent_id in pending.intents
                if (
                        KNOWLEDGE_INTENTS.get(intent_id) is not None
                        and (
                                KNOWLEDGE_INTENTS[intent_id].requires_object is None
                                or KNOWLEDGE_INTENTS[intent_id].requires_object == object_type
                        )
                )
            ]
            if matched:
                state.shared.pending_intents = None
                if state.task.active:
                    state.task.suspend_active()
                return await self.knowledge_handler.handle(
                    state=state,
                    user_message=user_message,
                    intents=matched,
                )

        # 没有正在收集的槽位：说明用户是在响应上一轮「请提供对象」的澄清，
        # 或主动提供对象。此时重新走规划流程，让规划器结合对话历史与已设置的
        # focused_object 决定执行知识检索/任务，而非遗忘上一轮意图直接追问。
        return await self._dispatch_by_plan(state, user_message)

    def _prepare_session(self, state:DialogueState) ->Session:
        session:Session = state.shared.current_session
        if session is None:
            session = SharedState.create_session()

        elif time.time() > session.last_activity_at + 60*60:
            state.shared.focused_object=None
            state.shared.pending_intents=None
            state.shared.close_session()
            state.task.active = None
            state.task.paused = []
            session = SharedState.create_session()

        state.shared.sessions.append(session)
        return session

    def _object_slot_command(self, message:UserMessage, state:DialogueState, flows:FlowCatalog) -> Command | None:
        message_object = message.object
        object_type = message_object.type.strip().lower()
        collect_slot_name = self._current_collect_slot_name(
            state=state,
            flows=flows,
        )

        if (
                object_type == "order"
                and collect_slot_name == "order_number"
        ):
            return SetSlotsCommand(
                command="set_slots",
                slots={"order_number": message_object.id},
            )

        if (
                object_type == "product"
                and collect_slot_name == "product_id"
        ):
            return SetSlotsCommand(
                command="set_slots",
                slots={"product_id": message_object.id},
            )

        return None

    def _current_collect_slot_name(self,
        state: DialogueState,
        flows: FlowCatalog,
        ) -> str | None:
        active_task = state.task.active
        if active_task is None:
            return None
        current_flow = flows.get_flow(active_task.flow_id)
        current_step = current_flow.get_step(
            active_task.step_id
        )
        if not isinstance(current_step, CollectSlotStep):
            return None
        return current_step.slot_name
