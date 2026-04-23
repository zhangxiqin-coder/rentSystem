from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Rent Management System API",
    description="租金管理系统后端 API",
    version="1.0.0"
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 健康检查端点
@app.get("/")
async def health_check():
    return {"status": "healthy", "message": "Rent Management System API is running"}

# 基础路由
@app.get("/api/v1/health")
async def api_health_check():
    return {"status": "ok", "version": "1.0.0"}
