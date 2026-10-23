import json
from dataclasses import asdict

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate

from atguigu.clients.llm_client import get_llm
from atguigu.domain.message import DialogueState, UserMessage
from atguigu.knowledge.intents import KnowledgeIntent
from atguigu.plan.models import TurnPlan
from atguigu.prompt.load_history import LoadHistory
from atguigu.prompt.load_prompt import load_prompt
from atguigu.task.flow.model import FlowCatalog, Flow


class TurnPlanner:
    async def predict(
            self,
            state:DialogueState,
            user_message:UserMessage,
            flows:FlowCatalog,
            knowledge_intents:dict[str,KnowledgeIntent]
    ) -> TurnPlan:
        # 构建所需提示词参数
        prompt_inputs = self._build_prompt_inputs(
            state,
            user_message,
            flows,
            knowledge_intents,
        )

        # 渲染并生成计划
        return await self._predict_from_prompt_inputs(prompt_inputs)

    def _build_prompt_inputs(self, state:DialogueState, user_message:UserMessage, flows:FlowCatalog, knowledge_intents:dict[str,KnowledgeIntent]):
        render_user_message = LoadHistory.render_user_message(user_message)
        history = LoadHistory.load(state.shared.current_session)
        active_task = state.task.active
        focused_object = state.shared.focused_object
        available_flows: list[Flow] = list(flows.flows.values())
        return {
            "current_conversation":history,
            "user_message":render_user_message,
            "available_flows_json":json.dumps(
                [{k:v
                  for k,v in asdict(flow).items()
                  if k != "steps"
                  } for flow in available_flows],
                ensure_ascii=False
            ),
            "active_task_json":json.dumps(
                [asdict(active_task) if active_task is not None else ""],ensure_ascii=False
            ),
            "interrupted_tasks_json":json.dumps(
                [asdict(task) for task in state.task.paused],ensure_ascii=False
            ),
            "focused_object_json":json.dumps(asdict(focused_object) if focused_object is not None else None,ensure_ascii=False),
            "knowledge_intents_json":json.dumps([{"id":knowledge_intent.id,"description":knowledge_intent.description} for knowledge_intent in knowledge_intents.values()],ensure_ascii=False)
        }

    async def _predict_from_prompt_inputs(self, prompt_inputs)->TurnPlan:
        prompt_text = load_prompt("turn_plan")
        prompt = PromptTemplate.from_template(prompt_text,template_format="jinja2")
        chain = prompt | get_llm() | JsonOutputParser()
        result = await chain.ainvoke(prompt_inputs)
        return TurnPlan.from_dict(result)
