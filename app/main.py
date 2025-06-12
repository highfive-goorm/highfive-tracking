# tracking_service/app/main.py

from fastapi import FastAPI, HTTPException, Body, status, Request
import logging
import os
from uuid import UUID
from datetime import datetime, timezone # timezone 추가
import json

# from .database import connect_to_mongo, close_mongo_connection # 더 이상 사용하지 않으므로 제거
from .schemas import EventLogCreate, EventLogResponse
# from . import crud # crud 모듈 사용하지 않으므로 제거

# --- 로거 설정 ---
LOG_DIR_MAIN = os.path.join(os.getcwd(), "logs")
os.makedirs(LOG_DIR_MAIN, exist_ok=True) # 로그 디렉토리 생성
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
event_file_handler = logging.FileHandler(LOG_FILE_PATH, encoding='utf-8')
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
    # await connect_to_mongo() # DB 연결 제거
    # logger.info("MongoDB connection established for Tracking Service.") # DB 연결 제거

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Tracking Service is shutting down...") # 일반 운영 로그
    # await close_mongo_connection() # DB 연결 제거
    # logger.info("MongoDB connection closed for Tracking Service.") # DB 연결 제거
    

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
            f"Received event processing request: event_id='{event_data.event_id}', "
            f"type='{event_data.event_type}', anonymous_id='{event_data.anonymous_id}'"
        )

        # 1. 타임스탬프 준비
        # event_timestamp를 UTC로 변환
        original_event_timestamp = event_data.event_timestamp
        if original_event_timestamp.tzinfo is None:
            # Naive datetime이면 UTC로 가정
            utc_event_timestamp = original_event_timestamp.replace(tzinfo=timezone.utc)
        else:
            # Timezone-aware datetime이면 UTC로 변환
            utc_event_timestamp = original_event_timestamp.astimezone(timezone.utc)

        # 2. 파일 로깅을 위한 데이터 준비 (모든 UUID는 문자열로, 타임스탬프는 KST 문자열로)
        log_to_file_dict = event_data.model_dump()
        
        # UUID 필드들을 문자열로 변환
        for key, value in log_to_file_dict.items():
            if isinstance(value, UUID):
                log_to_file_dict[key] = str(value)
        
        log_to_file_dict['event_timestamp'] = utc_event_timestamp.strftime('%Y-%m-%dT%H:%M:%SZ') # UTC 'Zulu' 형식으로 파일에 저장
        
        # structured_event_logger를 사용하여 별도 파일에 JSON 형태로 기록
        structured_event_logger.info(json.dumps(log_to_file_dict, ensure_ascii=False)) # ensure_ascii=False로 한글 유지

        # 3. API 응답 데이터 구성
        # EventLogResponse는 UUID 필드를 UUID 타입으로 받고, Config에서 JSON 직렬화 시 문자열로 변환합니다.
        api_response_data = EventLogResponse(
            event_id=event_data.event_id, # 요청에서 받은 UUID
            anonymous_id=event_data.anonymous_id, # 요청에서 받은 UUID
            user_id=event_data.user_id, # 요청에서 받은 UUID 또는 None
            session_id=event_data.session_id, # 요청에서 받은 UUID
            event_type=event_data.event_type,
            utm_parameters=event_data.utm_parameters,
            page_url=event_data.page_url,
            page_view=event_data.page_view,
            page_referrer=event_data.page_referrer,
            landing_url=event_data.landing_url,
            event_timestamp=utc_event_timestamp, # UTC datetime 객체 전달 (Pydantic이 ISO 문자열로 직렬화)
            event_properties=event_data.event_properties
        )

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
    # DB 연결을 사용하지 않으므로 DB 상태 확인 제거
    logger.info("Health check performed for Tracking Service.")
    return {"status": "healthy", "service": "Tracking Service"}