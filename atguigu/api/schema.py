# atguigu/api/schemas.py

from pydantic import BaseModel

"""
严格按照接口文档定义：
必填：是。 不需要默认值，初始化时一定要传值，否则报错
必填：否。 给定一个默认值，例如 None，{} 等
"""

class ChatObject(BaseModel):
    """对象消息"""
    type: str
    id: str
    title: str | None = None
    attributes: dict = {}

class ChatRequest(BaseModel):
    """聊天请求对象"""
    sender_id: str # 发送者ID
    text: str | None = None # 文本消息
    object: ChatObject | None = None # 对象消息
    message_id: str | None = None # 消息ID

class ChatMessage(BaseModel):
    """聊天响应消息对象"""
    text: str | None = None # 文本消息
    object: ChatObject | None = None # 对象消息

class ChatResponse(BaseModel):
    """聊天响应对象"""
    sender_id: str # 发送者ID
    message_id: str # 消息ID
    messages: list[ChatMessage] # 聊天历史消息列表


class HistoryMessage(BaseModel):
    """聊天历史消息对象"""
    role: str
    text: str | None = None
    object: ChatObject | None = None


class HistoryResponse(BaseModel):
    """聊天历史响应对象"""
    sender_id: str
    messages: list[HistoryMessage]