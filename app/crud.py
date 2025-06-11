from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorCollection
import uuid
from uuid import UUID as UUID_TYPE

from .schemas import EventLogCreate, KST # KST timezone import
from .database import get_user_events_collection

# --- 타임스탬프 포맷팅 함수 ---
def format_datetime_to_kst_str(dt: datetime) -> str:
    """ datetime 객체를 KST로 변환하고 'YYYY-MM-DD HH:MM:SS' 형식의 문자열로 반환합니다. """
    if dt.tzinfo is None: # naive datetime이면 UTC로 간주하고 KST로 변환
        dt_kst = dt.replace(tzinfo=timezone.utc).astimezone(KST)
    else: # timezone 정보가 있으면 해당 timezone에서 KST로 변환
        dt_kst = dt.astimezone(KST)
    return dt_kst.strftime("%Y-%m-%d %H:%M:%S")

async def save_event_log(log_data: EventLogCreate) -> dict:
    collection: AsyncIOMotorCollection = get_user_events_collection()

    log_document = log_data.model_dump(exclude_unset=True)

    # 서버에서 채울 필드 추가 및 기존 타임스탬프 변환
    log_document["event_id"] = uuid.uuid4() # 고유 이벤트 ID (UUID 객체)

    # ingest_timestamp: 현재 시간을 KST로 변환 후 문자열 포맷팅
    ingest_time_utc = datetime.now(timezone.utc)
    log_document["ingest_timestamp"] = format_datetime_to_kst_str(ingest_time_utc)

    # event_timestamp: 프론트에서 받은 datetime 객체를 KST로 변환 후 문자열 포맷팅
    # Pydantic이 event_timestamp 필드를 이미 datetime 객체로 변환해줌
    log_document["event_timestamp"] = format_datetime_to_kst_str(log_data.event_timestamp)
    
    # --- UUID 필드를 문자열로 변환 ---
    if "event_id" in log_document and isinstance(log_document["event_id"], UUID_TYPE):
        log_document["event_id"] = str(log_document["event_id"])
    
    if "anonymous_id" in log_document and isinstance(log_document["anonymous_id"], UUID_TYPE):
        log_document["anonymous_id"] = str(log_document["anonymous_id"])

    if "user_id" in log_document and log_document["user_id"] is not None and isinstance(log_document["user_id"], UUID_TYPE):
        log_document["user_id"] = str(log_document["user_id"])

    if "session_id" in log_document and isinstance(log_document["session_id"], UUID_TYPE):
        log_document["session_id"] = str(log_document["session_id"])
    # ---------------------------------

    # snake_case 필드명 사용 (Pydantic 모델 정의 시 이미 snake_case 사용)
    # 예: referrer_url, utm_parameters
    # 만약 Pydantic 모델 필드명과 DB 저장 필드명이 다르다면 여기서 변환 필요.
    # 현재는 Pydantic 모델 필드명을 그대로 사용한다고 가정.

    result = await collection.insert_one(log_document)
    created_log_doc = await collection.find_one({"_id": result.inserted_id})

    if created_log_doc:
        if "_id" in created_log_doc: # _id는 보통 ObjectId이므로 문자열 변환 불필요 (event_id 사용)
            created_log_doc.pop("_id", None) # _id 필드를 응답에서 제외할 수 있음
            pass
        # event_id는 이미 UUID 객체이므로 문자열 변환은 response 스키마에서 처리
    return created_log_doc if created_log_doc else {}