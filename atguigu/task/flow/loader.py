from pathlib import Path

import yaml

from atguigu.task.flow.model import FlowCatalog, FlowSlot, Flow
from atguigu.task.flow.steps import StartFlowStep, CollectSlotStep, ActionFlowStep, ResponseFlowStep, EndFlowStep, \
    FlowStepType


class FlowLoder:
    def load(self,path:Path) -> FlowCatalog:
        with open(path,'r',encoding="utf-8") as f:
            data = yaml.safe_load(f)

            slots = self._load_slots(data.get("slots",{}))
            flows = self._load_flows(flows_data=data.get("flows",{}),slots=slots)

        return FlowCatalog(flows,slots)

    def _load_flow(self,flow_id, flow_data, slots: dict[str, FlowSlot]) -> Flow:
        steps = flow_data.get("steps", {})
        steps_result = []
        slots_result = []
        for step in steps:
            flow_type = FlowStepType(step.get("type"))
            flow_cls = STEP_TYPE_TO_CLASS.get(flow_type)
            steps_result.append(flow_cls.from_dict(step))

            # 获取slot列表
            if step.get("slot_name") in slots:
                slots_result.append(slots.get(step.get("slot_name")))

        return Flow(id=flow_id,
                    name=flow_data.get("name"),
                    description=flow_data.get("description", ""),
                    steps=steps_result,
                    slots=slots_result)

    def _load_slots(self, slots: dict):
        return {k: FlowSlot(**v, name=k) for k, v in slots.items()}

    def _load_flows(self, flows_data: dict[str, dict], slots: dict[str, FlowSlot], ) -> dict[str, Flow]:
        flows: dict[str, Flow] = {}
        for flow_id, flow_data in flows_data.items():
            flows[flow_id] = self._load_flow(
                flow_id,
                flow_data,
                slots,
            )
        return flows

STEP_TYPE_TO_CLASS = {
    "start": StartFlowStep,
    "collect": CollectSlotStep,
    "action": ActionFlowStep,
    "response": ResponseFlowStep,
    "end": EndFlowStep,
}

if __name__ == '__main__':
    loader = FlowLoder()
    flow_catalog = loader.load(Path(__file__).parents[3] / "user_flows.yml")
    print(flow_catalog)
