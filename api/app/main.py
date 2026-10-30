from __future__ import annotations

import os
import sqlite3
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.middleware.cors import CORSMiddleware

from app.data_protection import DocumentProtector
from app.onboarding_repositories import AccountRepository, EventRepository, OnboardingStore, SessionRepository
from app.onboarding_routes import router as onboarding_router
from app.onboarding_routes import validation_error_response
from app.onboarding_service import OnboardingService
from app.repositories import TaskRepository
from app.routes import router
from app.two_factor import OtpChannel, TestCodeChannel
from app.wallet_provider import WalletProvider

ONBOARDING_PATH_PREFIX = "/api/onboarding"


def create_app(
    db_path: str | None = None,
    upload_dir: str | None = None,
    wallet_provider: WalletProvider | None = None,
    otp_channel: OtpChannel | None = None,
    protector: DocumentProtector | None = None,
    clock: Callable[[], datetime] | None = None,
) -> FastAPI:
    selected_db = db_path or os.getenv("WORKSHOP_DB_PATH", "./data/workshop.db")
    selected_uploads = upload_dir or os.getenv("WORKSHOP_UPLOAD_DIR", "./uploads")
    Path(selected_db).parent.mkdir(parents=True, exist_ok=True)
    Path(selected_uploads).mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(selected_db, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, description TEXT NOT NULL, status TEXT NOT NULL, owner TEXT NOT NULL, priority TEXT NOT NULL, created_at TEXT NOT NULL)")
    count = connection.execute("SELECT COUNT(*) AS total FROM tasks").fetchone()["total"]
    if count == 0:
        connection.execute("INSERT INTO tasks(title,description,status,owner,priority,created_at) VALUES ('Refactor login','Separar responsabilidades en frontend','TODO','student','HIGH',datetime('now'))")
        connection.execute("INSERT INTO tasks(title,description,status,owner,priority,created_at) VALUES ('Review API','Revisar seguridad de endpoints','IN_PROGRESS','student','MEDIUM',datetime('now'))")
        connection.execute("INSERT INTO tasks(title,description,status,owner,priority,created_at) VALUES ('Trainer notes','Preparar retrospectiva','TODO','trainer','LOW',datetime('now'))")
        connection.commit()

    app = FastAPI(title="Workshop Requirements API", version="0.1.0")
    app.state.connection = connection
    app.state.upload_dir = selected_uploads
    app.state.task_repository = TaskRepository(connection)
    store = OnboardingStore(connection)
    app.state.onboarding_events = EventRepository(store)
    app.state.onboarding_service = OnboardingService(
        SessionRepository(store),
        AccountRepository(store),
        app.state.onboarding_events,
        wallet_provider or WalletProvider(),
        protector or DocumentProtector.from_environment(Path(selected_db).parent),
        otp_channel or TestCodeChannel(),
        clock,
    )
    app.include_router(router)
    app.include_router(onboarding_router)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, error: RequestValidationError):
        if request.url.path.startswith(ONBOARDING_PATH_PREFIX):
            return validation_error_response(list(error.errors()))
        return await request_validation_exception_handler(request, error)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("shutdown")
    def close_connection() -> None:
        connection.close()

    return app


app = create_app()
