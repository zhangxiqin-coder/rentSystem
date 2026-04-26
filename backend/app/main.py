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
        if request.url.path in ['/api/auth/login', '/api/auth/register', '/api/v1/auth/login', '/api/v1/auth/register']:
            response = await call_next(request)
            # Generate and return new CSRF token for authenticated users
            if hasattr(request.state, 'user') and request.state.user:
                new_csrf_token = secrets.token_urlsafe(32)
                response.headers['X-CSRF-Token'] = new_csrf_token
            return response
        
        # For CSRF token endpoint, generate and return token
        if request.url.path in ['/api/auth/csrf-token', '/api/v1/auth/csrf-token']:
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

# 添加中间件 - 注意：FastAPI中间件执行顺序是LIFO（后进先出）
# 所以最后添加的中间件最先执行
# CORSMiddleware必须在最后添加，这样它会最先执行（处理OPTIONS预检请求）
app.add_middleware(CSRFMiddleware)

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

# 全局异常处理器
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """捕获所有未处理的异常"""
    import traceback
    logger = logging.getLogger(__name__)
    logger.error(f"Unhandled exception: {type(exc).__name__}: {str(exc)}")
    logger.error(f"Request: {request.method} {request.url.path}")
    logger.error(f"Traceback:\n{traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"}
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """捕获请求验证错误"""
    logger = logging.getLogger(__name__)
    logger.error(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"detail": "Validation error", "errors": exc.errors()}
    )

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
async def get_csrf_token(response: Response) -> Dict[str, Any]:
    """获取 CSRF Token"""
    try:
        csrf_token = secrets.token_urlsafe(32)
        # 将CSRF token添加到响应头中（供前端获取）
        response.headers["x-csrf-token"] = csrf_token
        return {
            "status": "success",
            "data": {"csrf_token": csrf_token}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成 CSRF token 失败: {str(e)}")
