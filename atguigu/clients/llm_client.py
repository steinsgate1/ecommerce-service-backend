# llm_client.py
from langchain.chat_models import init_chat_model
from atguigu.conf.config import settings

_llm = None

def get_llm():
    """获取 LLM 实例（单例）"""
    global _llm
    if _llm is None:
        _llm = init_chat_model(
            model=settings.llm_model,
            model_provider='openai',
            api_key=settings.llm_api_key,
            temperature=0,
            base_url=settings.llm_base_url,
            # 关闭 qwen 思维链，避免每条消息多消耗数十秒的推理 token
            extra_body={"enable_thinking": False},
        )
    return _llm

def reset_llm():
    """重置 LLM 实例（用于测试）"""
    global _llm
    _llm = None

if __name__ == '__main__':
    llm = get_llm()
    res = llm.invoke("who are you")
    print(res.content)