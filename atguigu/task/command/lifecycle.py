from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeAlias

if TYPE_CHECKING:
    # 仅用于类型注解；运行时导入会与 atguigu.domain.message 形成循环导入
    from atguigu.domain.message import TaskInstance


@dataclass
class TaskRef:
    task_id: str
    flow_id: str

    def to_ref(self,task:TaskInstance):
        self.task_id = task.task_id
        self.flow_id = task.flow_id


@dataclass
class TaskStarted:
    task: TaskRef


@dataclass
class TaskSwitched:
    previous: TaskRef
    current: TaskRef


@dataclass
class TaskResumed:
    task: TaskRef


@dataclass
class TaskCanceled:
    task: TaskRef

# TypeAlias 作用是类型校验，声明TaskEvent的返回值只能是声明里的类
TaskEvent: TypeAlias = (
        TaskStarted
        | TaskSwitched
        | TaskResumed
        | TaskCanceled
)