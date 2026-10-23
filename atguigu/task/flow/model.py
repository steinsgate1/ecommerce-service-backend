from dataclasses import dataclass, field

from atguigu.task.flow.steps import FlowStep, FlowStepType


@dataclass
class FlowCatalog:
    flows: dict[str, "Flow"] = field(default_factory=dict)
    slots: dict[str, "FlowSlot"] = field(default_factory=dict)

    def get_flow(self, flow_id:str) -> "Flow":
        return self.flows.get(flow_id)

@dataclass
class FlowSlot:
    name: str
    type: str = "any"
    label: str = ""
    description: str = ""

@dataclass
class Flow:
    id: str
    description: str = ""
    steps: list[FlowStep] = field(default_factory=list)
    slots: list[FlowSlot] = field(default_factory=list)
    name: str | None = None

    def get_start_step(self) -> FlowStep|None:
        for step in self.steps:
            if step.type is FlowStepType.START:
                return step

    def get_step(self, step_id)-> FlowStep|None:
        for step in self.steps:
            if step.id == step_id:
                return step
