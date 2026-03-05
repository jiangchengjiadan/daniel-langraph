"""FastAPI 应用入口"""
import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 添加backend到路径
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

from backend.api.routes import router
from backend.logging.config import get_logger

logger = get_logger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="工业设备售后智能客服 RAG Agent",
    description="基于LangGraph的高级RAG智能客服系统",
    version="1.0.0",
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制为具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(router)


@app.on_event("startup")
async def startup_event():
    """启动事件"""
    logger.info("=" * 50)
    logger.info("工业设备售后智能客服系统启动")
    logger.info("=" * 50)


@app.on_event("shutdown")
async def shutdown_event():
    """关闭事件"""
    logger.info("系统关闭")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
