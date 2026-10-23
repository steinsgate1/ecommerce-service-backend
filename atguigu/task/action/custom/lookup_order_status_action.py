
from __future__ import annotations  # 所有类型注解自动转为字符串
import asyncio
from typing import Any

from atguigu.clients import http
from atguigu.clients.http import init_http_client, close_http_client
from atguigu.conf.config import settings
from atguigu.domain.message import DialogueState
from atguigu.task.action.base import Action, ActionResult


class LookupOrderStatusAction(Action):
    name = "action_lookup_order_status"

    async def run(
        self,
        state: DialogueState,
        action_kwargs: dict[str, Any],
    ) -> ActionResult:
        order_number = state.task.active.slots.get("order_number")

        payload = {}
        if order_number:
            url = f"{settings.commerce_api_base_url}/orders/{order_number}"
            response = await http.http_client.get(url)
            body = response.json()
            # 防御：接口异常或订单不存在时没有 data 字段，降级处理避免 500
            if response.status_code < 400 and isinstance(body, dict):
                payload = body.get("data") or {}

        return ActionResult(slot_updates={
                "order_status": (
                        payload.get("status_desc")
                        or payload.get("status")
                        or "未知"
                ),
                "order_summary": (
                    f"订单金额 ¥{payload.get('amount', '未知')}。"
                ),
        })

if __name__ == '__main__':
    async def test():
        init_http_client()
        url = f"{settings.commerce_api_base_url}/orders/A20260410001"

        respnse = await http.http_client.get(url)
        payload = respnse.json()['data']

        print({
            "order_status": (
                    payload.get("status_desc")
                    or payload.get("status")
                    or "未知"
            ),
            "order_summary": (
                f"订单金额 ¥{payload['amount']}。"
            ),
        })
        await close_http_client()

    asyncio.run(test())