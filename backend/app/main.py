from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI(
    title="Rent Management System API",
    description="租金管理系统后端 API",
    version="1.0.0"
)

# 配置 CORS - 使用环境变量
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 健康检查端点
@app.get("/")
async def health_check():
    """基础健康检查端点"""
    try:
        return {"status": "healthy", "message": "Rent Management System API is running"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"健康检查失败: {str(e)}")

# 基础路由
@app.get("/api/v1/health")
async def api_health_check():
    """API 健康检查端点"""
    try:
        return {"status": "ok", "version": "1.0.0"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"健康检查失败: {str(e)}")
