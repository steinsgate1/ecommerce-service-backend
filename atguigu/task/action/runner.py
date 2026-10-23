from dataclasses import dataclass, field
from typing import Any

from atguigu.domain.message import DialogueState
from atguigu.task.action.base import ActionResult
from atguigu.task.action.registry import ActionRegistry


@dataclass
class ActionCall:
    action_name: str
    action_kwargs: dict[str, Any] = field(
        default_factory=dict
    )

class ActionRunner:
    def __init__(self, registry: ActionRegistry) -> None:
        self.registry = registry

    async def run(
        self,
        action_call: ActionCall,
        state: DialogueState,
    ) -> ActionResult:
        action = self.registry.get(action_call.action_name)
        return await action.run(
            state,
            action_call.action_kwargs,
        )