from atguigu.domain.message import DialogueState, UserMessage, BotMessage
from atguigu.task.command.models import Command
from atguigu.task.command.processor import CommandProcessor
from atguigu.task.flow.executor import FlowExecutor
from atguigu.task.flow.model import FlowCatalog
from atguigu.task.lifecycle.responder import TaskLifecycleResponder


class TaskHandler:
    def __init__(
            self,command_processor:CommandProcessor,
            flow_catalog:FlowCatalog,
            flow_executor:FlowExecutor,
            lifecycle_responder:TaskLifecycleResponder,
    ):
        self.command_processor = command_processor
        self.flow_catalog = flow_catalog
        self.flow_executor = flow_executor
        self.lifecycle_responder = lifecycle_responder

    async def handle(self,command:list[Command],state:DialogueState,user_message:UserMessage)->list[BotMessage]:
        # 任务执行器，生成命令保存到state，返回event标识以便生成转换回复
        events = self.command_processor.run(command,state,self.flow_catalog)
        # 生成转换回复
        messages = self.lifecycle_responder.respond(events)
        # 生成对应回答
        messages.extend(await self.flow_executor.run_task(state,self.flow_catalog,user_message))
        return messages

