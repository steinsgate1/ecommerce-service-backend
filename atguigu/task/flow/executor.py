from atguigu.domain.message import DialogueState, UserMessage, BotMessage
from atguigu.task.action.runner import ActionRunner, ActionCall
from atguigu.task.flow.model import FlowCatalog
from atguigu.task.flow.steps import *
from atguigu.task.response.render import ResponseRender


class FlowExecutor:
    def __init__(self,
                 response_render: ResponseRender,
                 action_runner: ActionRunner,
                 max_steps_per_turn: int = 100) -> None:
        self.response_renderer = response_render
        self.action_runner = action_runner
        self.max_steps_per_turn = max_steps_per_turn


    async def run_task(self,state:DialogueState,flows:FlowCatalog,user_message:UserMessage)->list[BotMessage]:
        messages: list[BotMessage] = []

        for _ in range(self.max_steps_per_turn):
            task = state.task.active
            if task is None:
                return messages

            flow = flows.get_flow(task.flow_id)
            step:FlowStep = flow.get_step(task.step_id)

            if isinstance(step, StartFlowStep):
                self._advance(step, state)
                continue

            if isinstance(step, ResponseFlowStep):
                message = await self.response_renderer.render(
                    step.template,
                    state,
                    user_message=user_message,
                )
                messages.append(message)
                self._advance(step, state)
                continue

            if isinstance(step, CollectSlotStep):
                should_wait = await self._run_collect_step(
                    step,
                    state,
                    messages,
                    user_message
                )
                if should_wait:
                    return messages

                self._advance(step, state)
                continue

            if isinstance(step, ActionFlowStep):
                result = await self.action_runner.run(action_call=ActionCall(step.action,step.args),state=state)
                state.task.set_slots(result.slot_updates)
                self._advance(step, state)
                continue

            if isinstance(step, EndFlowStep):
                state.task.complete_active()
                return messages

    def _advance(self, step:FlowStep, state:DialogueState) -> None:
        for link in step.next:
            if isinstance(link,StaticLink):
                state.task.active.step_id = link.target
                return
            if isinstance(link,ConditionalLink) and bool(eval(link.condition,{"builtins":{}},{"slots":state.task.active.slots},)):
                state.task.active.step_id = link.target
                return
            if isinstance(link,FallbackLink):
                state.task.active.step_id = link.target
                return

    async def _run_collect_step(
            self, step:CollectSlotStep,
            state:DialogueState,
            messages:list[BotMessage],
            user_message:UserMessage) -> bool:
        # 尝试从聚焦对象补充槽位
        self._try_fill_slot_from_focused_object(step,state)
        task = state.task.active
        value= task.slots.get(step.slot_name)

        # 槽位未补充
        if value is None or value == "":
            messages.append(await self.response_renderer.render(
                step.template,
                state,
                user_message
            ))
            return True

        # 槽位已补充但是校验不通过
        if step.validation and not bool(eval(step.validation.condition,{"__builtins__":None},{"slots":state.task.active.slots})):
            state.task.remove_slot(step.slot_name)
            messages.append(
                await self.response_renderer.render(
                    step.validation.failure_template,
                    state,
                    user_message=user_message,
                )
            )
            return True

        return False

    def _try_fill_slot_from_focused_object(self, step:CollectSlotStep, state):
        focused_object = state.shared.focused_object
        if focused_object is None:
            return

        if (step.slot_name == "order_number" and focused_object.type == "order"):
            state.task.set_slots({
                step.slot_name: focused_object.id
            })
        elif(step.slot_name == "product_id" and focused_object.type == "product"):
            state.task.set_slots({step.slot_name:focused_object.id})

