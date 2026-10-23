import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from atguigu.task.command.lifecycle import TaskRef, TaskStarted, TaskEvent, TaskSwitched, TaskCanceled, TaskResumed


@dataclass
class UserMessage:
    sender_id: str
    message_id: str
    type: "MessageType"
    text: str | None = None
    object: "MessageObject | None" = None

class MessageType(Enum):
    TEXT = "text"
    OBJECT = "object"

@dataclass
class MessageObject:
    type: str
    id : str
    title :str
    attributes: dict[str,Any] = field(default_factory=dict)

@dataclass
class ProcessResult:
    sender_id: str
    message_id: str
    messages: list["BotMessage"]

@dataclass
class BotMessage:
    text: str | None = None
    object: MessageObject | None = None

@dataclass
class Turn:
    turn_id: str
    user_message: UserMessage
    bot_messages: list[BotMessage] = field(default_factory=list)

    @classmethod
    def create_turn(cls, user_message) -> "Turn":
        return cls(turn_id=str(uuid.uuid4()),
                   user_message=user_message)




@dataclass
class Session:
    session_id: str
    started_at: float
    last_activity_at: float
    closed_at: float | None = None
    turns: list[Turn] = field(default_factory=list)
    # 中间轮次的压缩摘要；完整历史仍保存在 turns 中，不进入模型
    summary: str = ""

    @classmethod
    def create(cls) -> "Session":
        now = time.time()
        return Session(session_id=str(uuid.uuid4()),
                       started_at=now,
                       last_activity_at=now,)


    def close(self):
        self.last_activity_at = time.time()

    def add_turn(self, turn:Turn):
        self.turns.append(turn)
        self.last_activity_at = time.time()


@dataclass
class FocusedObject:
    type: str
    id: str
    title: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)

@dataclass
class PendingIntents:
    """因缺少咨询对象而被澄清的知识意图暂存。

    知识意图不是任务，不进 TaskState.paused；等用户补发对象卡片后
    由引擎确定性消费，不再依赖 LLM 从历史重新推断。
    """
    intents: list[str] = field(default_factory=list)

@dataclass
class SharedState:
    focused_object: FocusedObject | None = None
    pending_intents: PendingIntents | None = None
    sessions: list[Session] = field(default_factory=list)

    def set_focused_object(
            self,
            focused_object: FocusedObject,
    ) -> None:
        self.focused_object = focused_object

    # @property把方法变成属性，可以直接.方法名获取返回值
    @property
    def current_session(self) -> Session|None:
        if not self.sessions:
            return None
        return self.sessions[-1]


    def close_session(self):
        session = self.current_session
        session.close()

    @classmethod
    def create_session(cls):
        session = Session.create()
        return session

    def add_turn(self,turn:Turn):
        session = self.current_session
        session.add_turn(turn)



@dataclass
class TaskInstance:
    flow_id: str
    step_id: str | None = None
    slots: dict[str, Any] = field(default_factory=dict)
    task_id: str = field(
        default_factory=lambda: str(uuid.uuid4())
    )

    def to_ref(self) -> TaskRef:
        return TaskRef(
            task_id=self.task_id,
            flow_id=self.flow_id,
        )



@dataclass
class TaskState:
    active: TaskInstance | None = None
    paused: list[TaskInstance] = field(default_factory=list)

    def start(self, task) -> TaskEvent:
        # 两种情况，1当前无活动
        if self.active is None:
            self.active = task
            return TaskStarted(task.to_ref())

        # 2 当前有活动
        previous = self.active
        self.paused.append(previous)
        self.active = task
        return TaskSwitched(previous=previous.to_ref(),current=task.to_ref())

    def set_slots(self,slots :dict) ->None:
        # 字典update方法，在原有的基础上新增
        self.active.slots.update(slots)

    def cancel(self, task_id):
        if self.active is not None and self.active.task_id == task_id:
            cancel = self.active
            self.active = None
            return TaskCanceled(cancel.to_ref())

        # 如果是在暂停列表内
        cancel = next(task for task in self.paused if task.task_id == task_id)
        self.paused.remove(cancel)
        return TaskCanceled(cancel.to_ref())

    def resume(self, task_id):
        previous = self.active
        task = next(task for task in self.paused if task.task_id == task_id)
        self.active = task
        self.paused.remove(task)

        if self.active is not None:
            self.paused.append(previous)
            return TaskSwitched(
                previous=previous.to_ref(),
                current=task.to_ref(),
            )

        return TaskResumed(task=task.to_ref())

    def remove_slot(self, slot_name: str) -> None:
        self.active.slots.pop(slot_name, None)

    def complete_active(self):
        self.active = None


@dataclass
class DialogueState:
    sender_id: str
    shared: SharedState = field(default_factory=lambda : SharedState())
    task: TaskState = field(default_factory=lambda : TaskState())

