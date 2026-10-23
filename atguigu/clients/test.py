import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from app.models import User
from atguigu.conf.config import settings


# 假设你的模型 User 已经定义
async def test_query():
    # 1. 配置异步引擎
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        # 2. 在异步上下文中执行
        async with async_session() as session:
            # 3. 使用异步查询方法，注意 await
            result = await session.execute(select(User).where(User.id == 1))
            user = result.scalar_one_or_none()
            print(user.user_id)
            print(user.nickname)
    finally:
        # 4. 显式关闭异步引擎，释放连接资源
        await engine.dispose()

# 4. 运行异步函数
asyncio.run(test_query())