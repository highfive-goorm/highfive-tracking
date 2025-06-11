# tracking_service/app/main.py

from fastapi import FastAPI, HTTPException, Body, status, Request
import logging
from logging import FileHandler
import os
from uuid import UUID
from datetime import datetime
import json # JSON 직렬화를 위해 추가

from .database import connect_to_mongo, close_mongo_connection
from .schemas import EventLogCreate, EventLogResponse, KST
from . import crud

# --- 로거 설정 ---
LOG_DIR_MAIN = os.path.join(os.getcwd(), "logs")
os.makedirs(LOG_DIR_MAIN, exist_ok=True)
LOG_FILE_PATH = os.path.join(LOG_DIR_MAIN, "tracking_service_user_events_structured.log") # 파일 이름 변경 (선택적)

logger = logging.getLogger("tracking_service") # 서비스 로거
logger.setLevel(logging.INFO)

# 일반 운영 로그용 포맷터 (콘솔 및 일반 파일 로그용)
operation_formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s "
    "(%(filename)s:%(lineno)d)"
)

# 콘솔 핸들러 (운영 로그용)
console_handler = logging.StreamHandler()
console_handler.setFormatter(operation_formatter)
if not logger.handlers: # 핸들러 중복 추가 방지
    logger.addHandler(console_handler)

# --- 구조화된 이벤트 로그를 위한 별도 로거 및 핸들러 (선택적이지만 권장) ---
# 이렇게 하면 일반 운영 로그와 실제 이벤트 데이터 로그를 다른 파일이나 포맷으로 관리 가능
structured_event_logger = logging.getLogger("tracking_service.events") # 이벤트 데이터 전용 로거
structured_event_logger.setLevel(logging.INFO)
structured_event_logger.propagate = False # 루트 로거로 이벤트 전파 방지

# 이벤트 데이터 로그 파일 핸들러 (JSON 라인 형식)
# 포맷터 없이 메시지 자체를 JSON 문자열로 기록
event_file_handler = FileHandler(LOG_FILE_PATH, encoding='utf-8')
# event_file_handler.setFormatter(None) # 메시지 그대로 기록 (아래에서 직접 JSON 문자열 만듦)
structured_event_logger.addHandler(event_file_handler)


# --- FastAPI 애플리케이션 ---
app = FastAPI(
    title="User Action Tracking Service API",
    description="Collects user interaction events from the frontend and logs them.",
    version="0.1.0"
)

# --- Event Handlers (logger 사용) ---
@app.on_event("startup")
async def startup_event():
    logger.info("Tracking Service is starting up...") # 일반 운영 로그
    await connect_to_mongo()
    logger.info("MongoDB connection established for Tracking Service.")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Tracking Service is shutting down...") # 일반 운영 로그
    await close_mongo_connection()
    logger.info("MongoDB connection closed for Tracking Service.")


@app.post(
    "/log/event",
    response_model=EventLogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="사용자 행동 이벤트 로그 수집 (DB 저장 및 JSON 파일 로깅)"
)
async def collect_event_log(
    event_data: EventLogCreate = Body(...)
):
    try:
        # 일반 운영 로그: 이벤트 수신 시작
        logger.info(
            f"Received event processing request: type='{event_data.event_type}', "
            f"anonymous_id='{event_data.anonymous_id}'"
        )

        # 1. MongoDB에 구조화된 데이터 저장 (crud.py에서 KST 문자열로 변환됨)
        #    saved_log_doc_from_db는 event_id, ingest_timestamp (KST 문자열), event_timestamp (KST 문자열) 포함
        saved_log_doc_from_db = await crud.save_event_log(event_data)

        if not saved_log_doc_from_db:
            logger.error(
                f"Failed to save event log to MongoDB. Data: {event_data.model_dump_json()}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="로그 저장에 실패했습니다. (DB 오류)"
            )

        # 2. EventLogResponse 모델에 맞게 데이터 구성 (API 응답용)
        #    이 객체가 DB에 저장된 내용과 거의 동일 (타입 변환 등만 다름)
        response_payload = {
            "event_id": saved_log_doc_from_db["event_id"], # crud에서 생성한 UUID 객체 (또는 문자열)
            "anonymous_id": saved_log_doc_from_db["anonymous_id"], # UUID 객체 (또는 문자열)
            "user_id": saved_log_doc_from_db.get("user_id"), # UUID 객체 또는 None (또는 문자열)
            "session_id": saved_log_doc_from_db["session_id"], # UUID 객체 (또는 문자열)
            "event_type": saved_log_doc_from_db["event_type"],
            "referrer_url": saved_log_doc_from_db.get("referrer_url"),
            "utm_parameters": saved_log_doc_from_db.get("utm_parameters"),
            "event_timestamp": event_data.event_timestamp, # 원본 datetime (Pydantic이 파싱) - 응답용
            "event_timestamp_str": saved_log_doc_from_db["event_timestamp"], # DB 저장된 KST 문자열 - 응답용
            "ingest_timestamp_str": saved_log_doc_from_db["ingest_timestamp"], # DB 저장된 KST 문자열 - 응답용
            "event_properties": saved_log_doc_from_db.get("event_properties")
        }
        api_response_data = EventLogResponse.model_validate(response_payload)

        # 3. 파일에 DB 저장 내용과 동일한 정보 (JSON 문자열) 기록
        #    MongoDB에 저장된 형태(KST 문자열 타임스탬프, UUID 문자열 등)와 유사하게 만듦
        #    crud.py에서 반환된 saved_log_doc_from_db를 그대로 사용하거나,
        #    API 응답용 api_response_data를 JSON으로 변환하여 기록
        
        # saved_log_doc_from_db는 이미 MongoDB 저장 형식에 가깝지만, UUID 객체가 포함될 수 있음.
        # 파일 로그에는 모든 UUID를 문자열로 변환하여 기록하는 것이 좋음.
        log_to_file_dict = saved_log_doc_from_db.copy() # 복사본 사용
        log_to_file_dict.pop("_id", None)

        for key, value in log_to_file_dict.items():
            if isinstance(value, UUID):
                log_to_file_dict[key] = str(value)
        
        # structured_event_logger를 사용하여 별도 파일에 JSON 형태로 기록
        structured_event_logger.info(json.dumps(log_to_file_dict, ensure_ascii=False)) # ensure_ascii=False로 한글 유지

        logger.info(
            f"Successfully processed and logged event. Event ID: {api_response_data.event_id}"
        )
        return api_response_data

    except HTTPException as http_exc:
        logger.warning(
            f"HTTPException during event processing: Status={http_exc.status_code}, Detail={http_exc.detail}"
        )
        raise http_exc
    except Exception as e:
        logger.error(
            f"Unexpected error while processing event log: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"로그 처리 중 예기치 않은 오류 발생: {str(e)}"
        )

# Health Check (logger 사용)
@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    # ... (logger 사용) ...
    db_status = "unknown"
    from .database import client as mongo_client_global
    if mongo_client_global:
        try:
            await mongo_client_global.admin.command('ping')
            db_status = "connected"
        except Exception:
            db_status = "disconnected"
    logger.info(f"Health check performed. DB status: {db_status}")
    return {"status": "healthy", "db_status": db_status, "service": "Tracking Service"}