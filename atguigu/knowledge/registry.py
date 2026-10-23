from atguigu.knowledge.providers import KnowledgeProvider


class KnowledgeProviderRegistry:
    def __init__(self,provides:list[KnowledgeProvider]):
        self._knoledge_providers_dict = {provide.provider_id : provide for provide in provides}

    def get(self,provider_id)-> KnowledgeProvider:
        return self._knoledge_providers_dict.get(provider_id,None)
