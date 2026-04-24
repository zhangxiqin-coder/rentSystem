from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import secrets
import os
from typing import Any, Dict

from app.api import auth, rooms, payments, utility_readings, utility_rates, users, statistics, reminders, export

app = FastAPI(
    title="Rent Management System API",
    description="租金管理系统后端 API",
    version="2.0.0"
)

# CSRF Protection Middleware
class CSRFMiddleware(BaseHTTPMiddleware):
    """CSRF Protection Middleware"""
    
    async def dispatch(self, request: Request, call_next):
        # Skip CSRF for GET, HEAD, OPTIONS, TRACE methods
        if request.method in ['GET', 'HEAD', 'OPTIONS', 'TRACE']:
            response = await call_next(request)
            return response
        
        # For state-changing methods (POST, PUT, DELETE, PATCH)
        # Check for CSRF token
        csrf_token_header = request.headers.get('X-CSRF-Token')
        
        # Skip CSRF check for login/register endpoints (they establish session)
        if request.url.path in ['/api/v1/auth/login', '/api/v1/auth/register']:
            response = await call_next(request)
            # Generate and return new CSRF token for authenticated users
            if hasattr(request.state, 'user') and request.state.user:
                new_csrf_token = secrets.token_urlsafe(32)
                response.headers['X-CSRF-Token'] = new_csrf_token
            return response
        
        # For CSRF token endpoint, generate and return token
        if request.url.path == '/api/v1/auth/csrf-token':
            response = await call_next(request)
            return response
        
        # Validate CSRF token for other state-changing requests
        if not csrf_token_header:
            return Response(
                content='{"detail": "CSRF token is missing"}',
                status_code=403,
                media_type='application/json'
            )
        
        # In a real implementation, you would validate the token against a session
        # For now, we'll check if it exists and has reasonable length
        if len(csrf_token_header) < 20:
            return Response(
                content='{"detail": "Invalid CSRF token"}',
                status_code=403,
                media_type='application/json'
            )
        
        response = await call_next(request)
        return response

# Add CSRF middleware FIRST (so it executes AFTER CORS)
app.add_middleware(CSRFMiddleware)

# Include routers
# API v1 routers
api_v1_prefix = "/api/v1"
app.include_router(auth.router, prefix=api_v1_prefix)
app.include_router(rooms.router, prefix=api_v1_prefix)
app.include_router(payments.router, prefix=api_v1_prefix)
app.include_router(utility_readings.router, prefix=api_v1_prefix)
app.include_router(utility_rates.router, prefix=api_v1_prefix)
app.include_router(users.router, prefix=api_v1_prefix)
app.include_router(statistics.router, prefix=api_v1_prefix)
app.include_router(reminders.router, prefix=api_v1_prefix)
app.include_router(export.router, prefix=api_v1_prefix)

# 配置 CORS - 固定配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://43.134.40.91:5173",
        "http://127.0.0.1:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-CSRF-Token"],
)

# 健康检查端点
@app.get("/")
async def health_check() -> Dict[str, Any]:
    """基础健康检查端点"""
    try:
        return {"status": "healthy", "message": "Rent Management System API is running"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"健康检查失败: {str(e)}")

# 基础路由
@app.get("/api/v1/health")
async def api_health_check() -> Dict[str, Any]:
    """API 健康检查端点"""
    try:
        return {"status": "ok", "version": "1.0.0"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"健康检查失败: {str(e)}")

# CSRF Token endpoint
@app.get("/api/v1/auth/csrf-token")
async def get_csrf_token() -> Dict[str, Any]:
    """获取 CSRF Token"""
    try:
        csrf_token = secrets.token_urlsafe(32)
        return {
            "status": "success",
            "data": {"csrf_token": csrf_token}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成 CSRF token 失败: {str(e)}")
