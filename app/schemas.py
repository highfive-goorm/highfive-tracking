from pydantic import BaseModel, Field, UUID4
from typing import Optional, Dict, Any, List # List 추가 (order_items 등)
from datetime import datetime, timezone, timedelta # timezone, timedelta 추가
import uuid

# --- KST 시간대 정의 ---
KST = timezone(timedelta(hours=9), name='KST')

# --- 이벤트 타입별 속성 예시 (이 부분은 이전과 동일하게 유지, 필요시 네이밍 컨벤션 적용) ---
# (SearchEventProperties, ProductViewEventProperties 등 이전 코드와 동일하게 유지 가능)
# 스키마 문서에서 제공된 대표 속성들은 event_properties 내에 키-값으로 들어간다고 가정합니다.
# 예를 들어, product_view 이벤트 시 event_properties에 "product_id", "price" 등이 포함됨.

# --- 공통 로그 스키마 (네이밍 컨벤션 및 타임스탬프 고려) ---
class EventLogBase(BaseModel):
    # event_id는 서버에서 생성
    anonymous_id: UUID4 = Field(..., description="익명 사용자 식별자 (프론트엔드 제공)")
    user_id: Optional[UUID4] = Field(None, description="사용자 식별자 (프론트엔드 제공, Nullable)")
    session_id: UUID4 = Field(..., description="세션 식별자 (프론트엔드 제공)")
    event_type: str = Field(..., min_length=1, description="이벤트 타입 (예: search, product_view)")
    referrer_url: Optional[str] = Field(None, description="유입 경로 URL (프론트엔드 제공, 이전 'referrer')") # 네이밍 변경
    utm_parameters: Optional[Dict[str, Any]] = Field(None, description="UTM 파라미터 (프론트엔드 제공, 이전 'utm_params')") # 네이밍 변경

    # event_timestamp: 프론트엔드에서 발생 시각을 datetime 객체 또는 ISO 문자열로 전달하면,
    # Pydantic이 datetime 객체로 변환. 저장 시 KST 문자열로 변환.
    event_timestamp: datetime = Field(..., description="이벤트 발생 시각 (프론트엔드 제공, ISO 형식 권장)")

    # event_properties: 이벤트 타입별 특정 속성들 (JSON 형태로 저장될 수 있음)
    # 네이밍: 단수형 컬럼명 + JSON 데이터는 복수형 -> event_properties는 그 자체로 복수형 의미를 내포.
    # 또는 event_specific_properties 등으로 명명 가능. 여기서는 event_properties 유지.
    event_properties: Optional[Dict[str, Any]] = Field(None, description="이벤트 타입별 특정 속성들")


class EventLogCreate(EventLogBase):
    # API 요청으로 받을 때의 스키마
    pass

class EventLogResponse(EventLogBase):
    event_id: UUID4 = Field(description="서버에서 생성된 이벤트 고유 식별자")
    # ingest_timestamp는 서버에서 생성 후 KST 문자열로 변환하여 응답
    ingest_timestamp_str: str = Field(description="로그 수집/저장 시각 (서버 기록, KST, YYYY-MM-DD HH:MM:SS)")
    event_timestamp_str: str = Field(description="이벤트 발생 시각 (KST, YYYY-MM-DD HH:MM:SS)")


    class Config:
        # orm_mode = True # Pydantic v1
        from_attributes = True # Pydantic v2
        json_encoders = {
            # datetime 객체를 응답으로 보낼 경우 ISO 포맷으로 (여기서는 문자열 필드로 대체)
            # datetime: lambda dt: dt.isoformat(),
            UUID4: lambda u: str(u)
        }
        # MongoDB _id를 다른 필드명으로 매핑할 필요 없음 (event_id 사용)