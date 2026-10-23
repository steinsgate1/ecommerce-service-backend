import asyncio
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from atguigu.clients import http
from atguigu.conf.config import settings
from atguigu.domain.message import UserMessage, DialogueState


@dataclass
class KnowledgeChunk:
    content: str


class KnowledgeProvider(ABC):
    provider_id = ""

    @abstractmethod
    async def retrieve(
        self,
        state: DialogueState,
        user_message: UserMessage,
    ) -> list[KnowledgeChunk]:
        pass

class ProductAPIProvider(KnowledgeProvider):
    provider_id = "api.product"
    async def retrieve(self, state: DialogueState, user_message: UserMessage) -> list[KnowledgeChunk]:
        product_id: str = state.shared.focused_object.id
        data = await self._get_product_info_by_id(product_id)
        text = json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        )
        return [
            KnowledgeChunk(content=f"商品信息:\n{text}")
        ]

    async def _get_product_info_by_id(self, product_id):
        url = (
            f"{settings.commerce_api_base_url}"
            f"/products/{product_id}"
        )
        response = await http.http_client.get(url)
        payload = response.json()
        # 防御：接口异常/商品不存在时返回空字典，由知识应答层兜底
        if response.status_code >= 400 or not isinstance(payload, dict):
            return {}
        return payload.get("data", {})

class OrderAPIProvider(KnowledgeProvider):
    provider_id = "api.order"

    async def retrieve(self, state: DialogueState, user_message: UserMessage) -> list[KnowledgeChunk]:
        order_id: str = state.shared.focused_object.id

        order_payload, logistics_payload = (await asyncio.gather(
            self._fetch_order(order_id),
            self._fetch_logistics(order_id)
        ))

        text = json.dumps(
            {
                "order_number": order_id,
                "order": order_payload,
                "logistics": logistics_payload,
            },
            ensure_ascii=False,
            indent=2,
        )
        return [
            KnowledgeChunk(content=f"订单信息:\n{text}")
        ]

    async def _fetch_order(
        self,
        order_number: str,
    ) -> dict[str, Any]:
        url = (
            f"{settings.commerce_api_base_url}"
            f"/orders/{order_number}"
        )
        response = await http.http_client.get(url)
        payload = response.json()
        if response.status_code >= 400 or not isinstance(payload, dict):
            return {}
        return payload.get("data", {})

    async def _fetch_logistics(
        self,
        order_number: str,
    ) -> dict[str, Any]:
        url = (
            f"{settings.commerce_api_base_url}"
            f"/orders/{order_number}/logistics"
        )
        response = await http.http_client.get(url)
        return response.json().get("data", {})

class FAQProvider(KnowledgeProvider):
    provider_id = "faq.default"

    async def retrieve(
            self,
            state: DialogueState,
            user_message: UserMessage,
    ) -> list[KnowledgeChunk]:
        return [
            KnowledgeChunk(content="faq未检索到相关问题")
        ]

class RAGProvider(KnowledgeProvider):
    provider_id = "rag.default"

    async def retrieve(
            self,
            state: DialogueState,
            user_message: UserMessage,
    ) -> list[KnowledgeChunk]:
        return [
            KnowledgeChunk(content="rag未检索到相关问题")
        ]


