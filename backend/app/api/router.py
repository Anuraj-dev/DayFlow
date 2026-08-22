from fastapi import APIRouter

from app.api.routes import attendance, auth, dashboard, employees, health, payroll, time_off

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(dashboard.router)
api_router.include_router(employees.router)
api_router.include_router(attendance.router)
api_router.include_router(time_off.router)
api_router.include_router(payroll.router)
