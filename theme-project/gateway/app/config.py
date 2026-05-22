import os

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL",     "http://omstu-auth:8000")
NEWS_SERVICE_URL = os.getenv("NEWS_SERVICE_URL",     "http://omstu-news:8000")
SCHEDULE_SERVICE_URL = os.getenv("SCHEDULE_SERVICE_URL", "http://omstu-schedule:8000")
LECTURE_SERVICE_URL = os.getenv("LECTURE_SERVICE_URL",  "http://omstu-lecture:8000")
AUTH_GRPC_URL = os.getenv("AUTH_GRPC_URL", "omstu-auth:50051")

# Маршруты требующие авторизации
PROTECTED_PREFIXES = [
    "/api/lectures",
]