

from atguigu.domain.message import DialogueState, TaskInstance
from atguigu.task.command.lifecycle import TaskEvent
from atguigu.task.command.models import (
    CancelTaskCommand,
    Command,
    ResumeTaskCommand,
    SetSlotsCommand,
    StartFlowCommand,
)
from atguigu.task.flow.model import FlowCatalog


class CommandProcessor:
    def run(
        self,
        commands: list[Command],
        state: DialogueState,
        flows: FlowCatalog,
    ) -> list[TaskEvent]:
        events: list[TaskEvent] = []
        for command in commands:
            event = self._apply(command, state, flows)
            if event is not None:
                events.append(event)
        return events

    def _apply(
        self,
        command: Command,
        state: DialogueState,
        flows: FlowCatalog,
    ) -> TaskEvent | None:
        if isinstance(command, StartFlowCommand):
            flow = flows.get_flow(command.flow)
            task = TaskInstance(
                flow_id=flow.id,
                step_id=flow.get_start_step().id,
            )
            return state.task.start(task)


        if isinstance(command, SetSlotsCommand):
            # 更新状态state
            state.task.set_slots(command.slots)
            return None


        if isinstance(command, CancelTaskCommand):
            return state.task.cancel(command.task_id)

        if isinstance(command, ResumeTaskCommand):
            return state.task.resume(command.task_id)