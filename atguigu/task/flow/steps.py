from dataclasses import dataclass, field

from atguigu.task.flow.links import FlowStepLink, StaticLink, ConditionalLink, FallbackLink
from atguigu.task.response.model import ResponseTemplate

from enum import Enum, StrEnum
from typing import Any


@dataclass
class FlowStep:
    id: str
    type: "FlowStepType"
    next: list[FlowStepLink] = field(default_factory=list)
    description: str = ""

    @staticmethod
    def base_fields(
            step_data: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "id": step_data["id"],
            "type": FlowStepType(step_data["type"]),
            "description": step_data.get("description", ""),
            "next": FlowStep.build_links(step_data["next"]),
        }

    @staticmethod
    def build_links(next) -> list[FlowStepLink]:
        # 三种情况
        # 1 直接链接 staticLink
        if isinstance(next, str):
            return [StaticLink(target=next)]

        links: list[FlowStepLink] = []
        for link in next:
            # 2 条件链接 conditionLink if then
            if "if" in link:
                links.append(ConditionalLink(target=link["then"],condition=link["if"]))
            # 3 兜底链接 fallbackLink else
            else:
                links.append(FallbackLink(target=link["else"]))

        return links

class FlowStepType(StrEnum):
    START = "start"
    ACTION = "action"
    RESPONSE = "response"
    COLLECT = "collect"
    END = "end"

@dataclass
class StartFlowStep(FlowStep):

    @classmethod
    def from_dict(
            cls,
            step_data: dict[str, Any],
    ) -> "StartFlowStep":
        return cls(**FlowStep.base_fields(step_data))

@dataclass
class ActionFlowStep(FlowStep):
    action: str = ""
    args: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, step_data):
        return cls(**FlowStep.base_fields(step_data),action=step_data.get("action",""),args=step_data.get("args",""))


@dataclass
class ResponseFlowStep(FlowStep):
    template: ResponseTemplate = field(default_factory=ResponseTemplate)

    @classmethod
    def from_dict(
            cls,
            step_data: dict[str, Any],
    ) -> "ResponseFlowStep":
        return cls(
            **FlowStep.base_fields(step_data),
            template=ResponseTemplate.from_dict(
                step_data.get("template", {})
            )
        )


@dataclass
class CollectSlotStep(FlowStep):
    slot_name: str = ""
    template: ResponseTemplate = field(default_factory=ResponseTemplate)
    validation: "SlotValidation | None" = None

    @classmethod
    def from_dict(cls, step_data):
        validation = None
        if step_data.get("validation",""):
            validation_data = step_data["validation"]
            validation = SlotValidation(condition=validation_data["condition"],failure_template=ResponseTemplate.from_dict(validation_data["failure_template"]))
        return cls(**FlowStep.base_fields(step_data),
                   slot_name=step_data["slot_name"],
                   template=ResponseTemplate.from_dict(step_data["template"]),
                   validation=validation)

@dataclass
class EndFlowStep(FlowStep):
    @classmethod
    def from_dict(cls, step_data):
        return cls(**FlowStep.base_fields(step_data))

@dataclass
class SlotValidation:
    condition: str
    failure_template: ResponseTemplate