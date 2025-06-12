from pydantic import BaseModel, Field, UUID4
from typing import Optional, Dict, Any, List # List 추가 (order_items 등)
from datetime import datetime # timezone, timedelta 제거
import uuid

# --- 이벤트 타입별 속성 예시 (이 부분은 이전과 동일하게 유지, 필요시 네이밍 컨벤션 적용) ---
# (SearchEventProperties, ProductViewEventProperties 등 이전 코드와 동일하게 유지 가능)
# 스키마 문서에서 제공된 대표 속성들은 event_properties 내에 키-값으로 들어간다고 가정합니다.
# 예를 들어, product_view 이벤트 시 event_properties에 "product_id", "price" 등이 포함됨.

# --- 공통 로그 스키마 (네이밍 컨벤션 및 타임스탬프 고려) ---
class EventLogBase(BaseModel):
    event_id: UUID4 = Field(..., description="이벤트 고유 식별자 (프론트엔드 생성)")
    anonymous_id: UUID4 = Field(..., description="익명 사용자 식별자 (프론트엔드 제공)")
    user_id: Optional[UUID4] = Field(None, description="사용자 식별자 (프론트엔드 제공, Nullable)")
    session_id: UUID4 = Field(..., description="세션 식별자 (프론트엔드 제공)")
    event_type: str = Field(..., min_length=1, description="이벤트 타입 (예: search, product_view)")
    utm_parameters: Optional[Dict[str, Any]] = Field(None, description="UTM 파라미터 (프론트엔드 제공)")
    page_url: str = Field(..., description="이벤트 발생 현재 페이지 전체 URL")
    page_view: Optional[str] = Field(None, description="페이지 제목 (프론트엔드 제공)") # 스키마 테이블의 'page_view' 사용
    page_referrer: Optional[str] = Field(None, description="사이트 내 이전 페이지 URL (내부 이동 경로)")
    landing_url: Optional[str] = Field(None, description="세션 내 사용자 최초 도달 페이지 URL")

    # event_timestamp: 프론트엔드에서 발생 시각을 datetime 객체 또는 ISO 문자열로 전달하면,
    # Pydantic이 datetime 객체로 변환. 저장 시 KST 문자열로 변환.
    event_timestamp: datetime = Field(..., description="이벤트 발생 시각 (프론트엔드 제공, ISO 형식 권장)")

    # event_properties: 이벤트 타입별 특정 속성들 (JSON 형태로 저장될 수 있음)
    event_properties: Optional[Dict[str, Any]] = Field(None, description="이벤트 타입별 특정 속성들")


class EventLogCreate(EventLogBase):
    # API 요청으로 받을 때의 스키마
    pass

class EventLogResponse(EventLogBase):
    # event_id는 EventLogBase로부터 상속받음
    # event_timestamp_str 필드 제거, EventLogBase의 event_timestamp (datetime)이 ISO 형식으로 직렬화됨


    class Config:
        # orm_mode = True # Pydantic v1
        from_attributes = True # Pydantic v2
        json_encoders = {
            # datetime 객체를 응답으로 보낼 경우 ISO 포맷으로 (여기서는 문자열 필드로 대체)
            # datetime: lambda dt: dt.isoformat(),
            UUID4: lambda u: str(u)
        }
        # MongoDB _id를 다른 필드명으로 매핑할 필요 없음 (event_id 사용)