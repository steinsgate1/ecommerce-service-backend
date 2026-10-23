from atguigu.domain.message import DialogueState
from atguigu.knowledge.intents import KnowledgeIntent
from atguigu.plan.models import TurnPlan, TurnPlanValidationResult, ClarifyReason
from atguigu.task.command.models import StartFlowCommand, ResumeTaskCommand, CancelTaskCommand, SetSlotsCommand
from atguigu.task.flow.model import FlowCatalog


class TurnPlanValidator:
    def validate(self, turn_plan: TurnPlan,
        state: DialogueState,
        flows: FlowCatalog,
        knowledge_intents: dict[str, KnowledgeIntent],) ->TurnPlanValidationResult:
        active_tracks = self._active_task(turn_plan)
        # 不存在
        if not active_tracks:
            return self._reject(
                ClarifyReason.MISSING_TRACK
            )
        # 超过两个任务，返回澄清回复
        if len(active_tracks) > 1:
            return self._reject(
                ClarifyReason.MULTIPLE_TRACKS
            )

        track = active_tracks[0]

        if track == "task":
            return self._validate_task(
                turn_plan,
                state,
                flows,
            )
        if track == "knowledge":
            return self._validate_knowledge(
                turn_plan,
                state,
                knowledge_intents,
            )
        return TurnPlanValidationResult(valid=True)

    def _active_task(self, turn_plan:TurnPlan) -> list[str]:
        return [name
        for name,value in (
            ("task",turn_plan.task),
            ("knowledge",turn_plan.knowledge),
            ("chitchat",turn_plan.chitchat)
        ) if value]

    @staticmethod
    def _reject(reason: ClarifyReason,) -> TurnPlanValidationResult:
        return TurnPlanValidationResult(valid=False,reason=reason)

    def _validate_task(self,
        turn_plan: TurnPlan,
        state: DialogueState,
        flows: FlowCatalog,) -> TurnPlanValidationResult:

        task_plan = turn_plan.task
        if task_plan is None or not task_plan.commands:
            return self._reject(
                ClarifyReason.MISSING_TASK_COMMANDS
            )

        active_task_id = (state.task.active.task_id if state.task.active is not None else None)
        paused_task_ids = {task.task_id for task in state.task.paused}
        new_task_index = 0

        for command in task_plan.commands:
            if isinstance(command, StartFlowCommand):
                if command.flow not in flows.flows:
                    return self._reject(
                        ClarifyReason.INVALID_TASK_COMMAND
                    )
                if active_task_id is not None:
                    paused_task_ids.add(active_task_id)
                new_task_index += 1
                active_task_id = (
                    f"<new-task-{new_task_index}>"
                )
            elif isinstance(command, ResumeTaskCommand):
                if command.task_id not in paused_task_ids:
                    return self._reject(
                        ClarifyReason.INVALID_TASK_COMMAND
                    )
                paused_task_ids.remove(command.task_id)
                if active_task_id is not None:
                    paused_task_ids.add(active_task_id)
                active_task_id = command.task_id
            elif isinstance(command, CancelTaskCommand):
                if command.task_id == active_task_id:
                    active_task_id = None
                elif command.task_id in paused_task_ids:
                    paused_task_ids.remove(command.task_id)
                else:
                    return self._reject(
                        ClarifyReason.INVALID_TASK_COMMAND
                    )
            elif isinstance(command,SetSlotsCommand):
                if active_task_id is None:
                    return self._reject(
                        ClarifyReason.INVALID_TASK_COMMAND
                    )
            else:
                return self._reject(
                    ClarifyReason.INVALID_TASK_COMMAND
                )

        return TurnPlanValidationResult(valid=True)


    def _validate_knowledge(self,
            turn_plan: TurnPlan,
            state: DialogueState,
            knowledge_intents: dict[str, KnowledgeIntent],
        ) -> TurnPlanValidationResult:
        knowledge_plan = turn_plan.knowledge
        if knowledge_plan is None or not knowledge_plan.intents:
            return self._reject(
                ClarifyReason.MISSING_KNOWLEDGE_INTENT
            )

        for intent_id in knowledge_plan.intents:
            intent = knowledge_intents.get(intent_id)
            if intent is None:
                return self._reject(
                    ClarifyReason.UNKNOWN_KNOWLEDGE_INTENT
                )
            required_object = intent.requires_object
            focused_object = state.shared.focused_object
            if required_object is not None and (
                    focused_object is None
                    or focused_object.type != required_object
            ):
                return self._reject(
                    ClarifyReason.MISSING_FOCUSED_OBJECT
                )
        return TurnPlanValidationResult(valid=True)



