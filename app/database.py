import os
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
from dotenv import load_dotenv, find_dotenv # find_dotenv 추가

# .env 파일에서 환경 변수 로드
# tracking_service 디렉토리 내에서 실행될 때 해당 디렉토리의 .env를 찾음
load_dotenv(find_dotenv(usecwd=True))

# 기존 MongoDB URI 구성 방식 유지
MONGO_URI = (
    f"mongodb://{os.getenv('DB_USER')}:{os.getenv('MONGO_PASSWORD')}"
    f"@{os.getenv('MONGO_URL')}:{os.getenv('MONGO_PORT')}"
    f"/{os.getenv('MONGO_DB')}?authSource=admin"
)

# 사용할 데이터베이스 이름 (기존 'MONGO_DB' 환경 변수 사용)
# 이 값은 'product'가 될 것입니다.
DB_NAME_FROM_ENV = os.getenv('MONGO_DB')

# 로그를 저장할 컬렉션 이름
LOG_COLLECTION_NAME = "user_events" # 요청하신 컬렉션 이름

client: AsyncIOMotorClient = None
db: AsyncIOMotorDatabase = None # 'product' 데이터베이스 객체
user_events_collection: AsyncIOMotorCollection = None # 'user_events' 컬렉션 객체

async def connect_to_mongo():
    global client, db, user_events_collection
    if client and db and user_events_collection: # 이미 연결 및 설정 완료 시
        print("MongoDB connection already established for Tracking Service (using existing DB, 'user_events' collection).")
        return

    if not DB_NAME_FROM_ENV:
        # MONGO_DB 환경 변수가 설정되지 않은 경우에 대한 처리
        print("Error: MONGO_DB environment variable is not set. Cannot determine database name.")
        raise ValueError("MONGO_DB environment variable is required to connect to the database.")

    print(f"Connecting to Tracking MongoDB using existing URI for DB: '{DB_NAME_FROM_ENV}'...")
    client = AsyncIOMotorClient(MONGO_URI)
    # MONGO_URI에 이미 DB 이름이 포함되어 있으므로, client[DB_NAME_FROM_ENV]는 사실상 그 DB를 다시 선택하는 것과 같음
    # 또는 client.get_database()를 사용하여 명시적으로 가져올 수도 있습니다.
    # 여기서는 MONGO_URI가 올바르게 DB를 지정한다고 가정하고, 해당 DB 객체를 가져옵니다.
    db = client[DB_NAME_FROM_ENV] # 'product' 데이터베이스 사용
    user_events_collection = db[LOG_COLLECTION_NAME] # 'user_events' 컬렉션 사용

    try:
        await client.admin.command('ping') # 서버 연결 확인
        print(f"Successfully connected to MongoDB. Using database: '{DB_NAME_FROM_ENV}', collection: '{LOG_COLLECTION_NAME}'.")

        # 'user_events' 컬렉션에 필요한 인덱스 생성
        await user_events_collection.create_index([("event_timestamp", -1)], name="idx_event_time_user_events")
        await user_events_collection.create_index([("user_id", 1)], name="idx_user_id_user_events", sparse=True)
        await user_events_collection.create_index([("event_type", 1)], name="idx_event_type_user_events")
        await user_events_collection.create_index([("event_id", 1)], name="idx_event_id_user_events", unique=True)

    except Exception as e:
        print(f"Failed to connect to Tracking MongoDB or create indexes: {e}")
        # 연결 실패 시 전역 변수 초기화
        client = None
        db = None
        user_events_collection = None
        raise # 애플리케이션 시작 중단 또는 다른 오류 처리

async def close_mongo_connection():
    global client
    if client:
        client.close()
        # 전역 변수 초기화
        client = None
        db = None
        user_events_collection = None
        print("Tracking MongoDB connection closed.")

# 'user_events' 컬렉션 객체를 직접 반환하는 함수
def get_user_events_collection() -> AsyncIOMotorCollection:
    if user_events_collection is None:
        raise RuntimeError(
            "User events collection not initialized. "
            "Ensure connect_to_mongo is called successfully at application startup in Tracking Service."
        )
    return user_events_collection