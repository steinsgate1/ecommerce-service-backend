"""应答有言 · 智能客服 Streamlit 前端。

通过 HTTP 调用客服 Agent（FastAPI），与后端解耦，可独立部署：
- 本地默认连 http://127.0.0.1:18082
- 线上部署时通过环境变量 BACKEND_URL 或 .streamlit/secrets.toml
  的 BACKEND_URL 指向公网后端地址
"""

import os
import uuid

import requests
import streamlit as st

TYPE_LABELS = {"product": "商品", "order": "订单"}
ATTR_LABELS = {"price": "价格", "amount": "金额", "status": "状态", "stock": "库存"}

DEMO_PRODUCTS = [
    {"type": "product", "id": "SKU10001", "title": "iPhone 15 Pro 256G 远峰蓝",
     "attributes": {"price": 8999.0, "stock": "有货"}},
    {"type": "product", "id": "SKU10002", "title": "Apple Watch Series 9 GPS 45mm",
     "attributes": {"price": 2999.0, "stock": "有货"}},
]
DEMO_ORDERS = [
    {"type": "order", "id": "A20260407004", "title": "Apple Watch Series 9 GPS 45mm",
     "attributes": {"status": "待揽收", "amount": 2999.0}},
    {"type": "order", "id": "A20260410001", "title": "iPhone 15 Pro 256G 远峰蓝",
     "attributes": {"status": "待发货", "amount": 8999.0}},
]

GREETING = "您好，我是应答有言智能客服，请问有什么可以帮您？"


def backend_url() -> str:
    """后端地址：st.secrets > 环境变量 > 本地默认。"""
    try:
        if "BACKEND_URL" in st.secrets:
            return str(st.secrets["BACKEND_URL"]).rstrip("/")
    except FileNotFoundError:
        pass
    return os.environ.get("BACKEND_URL", "http://127.0.0.1:18082").rstrip("/")


st.set_page_config(page_title="应答有言 · 智能客服", page_icon="💬", layout="centered")

if "sender_id" not in st.session_state:
    st.session_state.sender_id = f"streamlit-{uuid.uuid4().hex[:8]}"
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "text": GREETING}]


def send(text: str | None = None, obj: dict | None = None) -> None:
    payload: dict = {"sender_id": st.session_state.sender_id}
    if text is not None:
        payload["text"] = text
    if obj is not None:
        payload["object"] = obj
    try:
        resp = requests.post(f"{backend_url()}/api/chat", json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException:
        st.session_state.messages.append({
            "role": "assistant",
            "text": "抱歉，客服服务暂时不可用，请稍后再试。",
        })
        return
    for m in data.get("messages", []):
        if m.get("text"):
            st.session_state.messages.append({"role": "assistant", "text": m["text"]})
        elif m.get("object"):
            st.session_state.messages.append({"role": "assistant", "object": m["object"]})


def render_object(obj: dict) -> None:
    label = TYPE_LABELS.get(obj.get("type"), "对象")
    lines = [f"**{obj.get('title') or obj.get('id')}**", f"{label}号：`{obj.get('id')}`"]
    for key, value in (obj.get("attributes") or {}).items():
        lines.append(f"{ATTR_LABELS.get(key, key)}：{value}")
    st.markdown("\n\n".join(lines))


# ---------- 侧栏 ----------
with st.sidebar:
    st.markdown("## 应答有言")
    st.caption(f"会话 ID：{st.session_state.sender_id}")

    st.markdown("### 商品")
    for p in DEMO_PRODUCTS:
        label = f"{p['title']}（¥{p['attributes']['price']:.0f}）"
        if st.button(label, key=p["id"], use_container_width=True):
            st.session_state.messages.append({"role": "user", "object": p})
            send(obj=p)
            st.rerun()

    st.markdown("### 订单")
    for o in DEMO_ORDERS:
        label = f"{o['title']}（{o['attributes']['status']}）"
        if st.button(label, key=o["id"], use_container_width=True):
            st.session_state.messages.append({"role": "user", "object": o})
            send(obj=o)
            st.rerun()

    st.divider()
    if st.button("清空会话", use_container_width=True):
        st.session_state.sender_id = f"streamlit-{uuid.uuid4().hex[:8]}"
        st.session_state.messages = [{"role": "assistant", "text": GREETING}]
        st.rerun()

# ---------- 主聊天区 ----------
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg.get("text"):
            st.markdown(msg["text"])
        elif msg.get("object"):
            render_object(msg["object"])

if user_text := st.chat_input("请输入您的问题…"):
    st.session_state.messages.append({"role": "user", "text": user_text})
    with st.chat_message("user"):
        st.markdown(user_text)
    with st.chat_message("assistant"):
        with st.spinner("思考中…"):
            send(text=user_text)
        last = st.session_state.messages[-1]
        if last.get("text"):
            st.markdown(last["text"])
        elif last.get("object"):
            render_object(last["object"])
