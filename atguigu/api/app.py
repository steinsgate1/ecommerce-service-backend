# main.py
import uvicorn
from fastapi import FastAPI ,Request
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse

from atguigu.api.chat_router import chat_router, lifespan
from atguigu.conf.config import settings

# 创建 app 实例，必须命名为 'app'
app = FastAPI(title="app",lifespan=lifespan)
app.include_router(chat_router)

def mian():
    uvicorn.run(
        'atguigu.api.app:app',
        host=settings.app_host,
        port=settings.app_port,
        reload=True
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """打印详细的请求验证错误"""
    body = await request.body()
    print("=" * 60)
    print("🔴 请求验证失败")
    print(f"📝 请求体: {body.decode() if body else '空'}")
    print(f"📋 错误详情: {exc.errors()}")
    print("=" * 60)
    return JSONResponse(
        status_code=422,
        content={
            "detail": exc.errors(),
            "body": body.decode() if body else None
        }
    )

app.include_router(chat_router)

if __name__ == '__main__':
    mian()