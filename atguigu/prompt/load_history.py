import json
from dataclasses import asdict

from atguigu.domain.message import UserMessage, MessageType, MessageObject, BotMessage, Turn, Session


class LoadHistory:
    """
    USER:我要退款
    BOT:好的，我们先处理退款申请
    BOT:请告诉我你的订单号。
    USER:10001
    BOT:请简单说一下退款原因。
    USER:尺码不合适
    BOT:好的，订单10001的退款申请已提交，原因是：尺码不合适。后续会尽快为你处理。
    """

    # 压缩策略：前 N 轮 + 中间摘要 + 后 N 轮
    FIRST_N = 3
    LAST_N = 2

    @staticmethod
    def load(session: Session) -> str:
        """渲染进入模型的对话历史。

        完整历史保存在 session.turns 中不进入模型；模型只看到前 FIRST_N 轮、
        中间轮次的摘要（session.summary）、后 LAST_N 轮。
        """
        turns = session.turns

        if len(turns) <= LoadHistory.FIRST_N + LoadHistory.LAST_N:
            return LoadHistory.render_turns(turns)

        parts: list[str] = [
            LoadHistory.render_turns(turns[:LoadHistory.FIRST_N]),
        ]
        if session.summary:
            parts.append(f"[历史摘要] {session.summary}")
        parts.append(LoadHistory.render_turns(turns[-LoadHistory.LAST_N:]))
        return "\n".join(parts)

    @staticmethod
    def render_turns(turns: list[Turn]) -> str:
        messages: list[str] = []
        for turn in turns:
            user_message = LoadHistory.render_user_message(turn.user_message)
            messages.append(f"USER:{user_message}")

            for bot_message in turn.bot_messages:
                bot_message_str = LoadHistory._render_bot_message(bot_message)
                messages.append(f"BOT:{bot_message_str}")

        return "\n".join(messages)

    @classmethod
    def render_user_message(cls, user_message: UserMessage):
        if user_message.type is MessageType.TEXT:
            return LoadHistory._render_text(user_message.text)
        return LoadHistory._render_obj(user_message.object)

    @classmethod
    def _render_bot_message(cls, bot_message: BotMessage):
        if bot_message.text:
            return LoadHistory._render_text(bot_message.text)
        return LoadHistory._render_obj(bot_message.object)

    @classmethod
    def _render_text(cls, text) -> str:
        return text.strip()

    @classmethod
    def _render_obj(cls, message_object: MessageObject):
        return json.dumps(asdict(message_object), ensure_ascii=False)
