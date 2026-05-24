from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date, datetime, timedelta
import requests

from app.database import get_db
from app.models.schedule import ScheduleCache
from app.config import settings

router = APIRouter(prefix="/schedule", tags=["schedule"])

OMGTU_API = "https://rasp.omgtu.ru/api/schedule"

REQUIRED_FIELDS = [
    "discipline",
    "kindOfWorkOid",
    "lecturer_title",
    "auditorium",
    "building",
    "beginLesson",
    "endLesson",
    "dayOfWeek",
    "date",
    "group",
    "subGroup",
    "stream",
    "lessonNumberStart",
]

def filter_lessons(lesson: dict) -> dict:
    return {field : lesson.get(field) for field in REQUIRED_FIELDS}

def fetch_from_omgtu(entity_type: str, entity_id: str, date_from: date, date_to: date) -> list:
    endpoint_map = {
        "group": "group",
        "teacher": "person",
        "auditory": "auditorium",
    }

    url = f"{OMGTU_API}/{endpoint_map[entity_type]}/{entity_id}"
    params = {
        "start": date_from.strftime("%Y.%m.%d"),
        "finish": date_to.strftime("%Y.%m.%d"),
        "lng": 1,
    }

    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, list) else []
    except Exception as e:
        print(f"Ошибка {e}")
        return []


def get_schedule(entity_type: str, entity_id: str, date_from: date, date_to: date, db: Session) -> list:
    result = []
    current_date = date_from

    while current_date <= date_to:
        cached = db.query(ScheduleCache).filter_by(
            entity_id=entity_id,
            entity_type=entity_type,
            date=current_date
        ).first()


        if current_date < date.today():
            if cached:
                result.extend(cached.data)
                current_date += timedelta(days=1)
                continue

        if cached:
            age = datetime.now() - cached.fetched_at
            if age.total_seconds() <  settings.SCHEDULE_TTL * 3600:
                result.extend(cached.data)
                current_date += timedelta(days=1)
                continue

        lessons = fetch_from_omgtu(entity_type, entity_id, current_date, date_to)

        by_date: dict[str, list] = {}

        for lesson in lessons:
            raw_date = lesson.get("date")
            if not raw_date:
                continue
            try:
                parsed = datetime.strptime(raw_date, "%Y.%m.%d").date()
                key = parsed.isoformat()
            except ValueError:
                continue
            if key not in by_date:
                by_date[key] = []
            by_date[key].append(filter_lessons(lesson))
        
        current = current_date
        while current <= date_to:
            key = current.isoformat()
            if key not in by_date:
                by_date[key] = []
            current += timedelta(days=1)

        for schedule_date, day_lessons in by_date.items():
            parsed_date = date.fromisoformat(schedule_date)
            existing = db.query(ScheduleCache).filter_by(
                entity_id=entity_id,
                entity_type=entity_type,
                date=parsed_date
            ).first()

            if existing:
                existing.data = day_lessons
                existing.fetched_at = datetime.now()
            else:
                db.add(ScheduleCache(
                    entity_id=str(entity_id),
                    entity_type=entity_type,
                    date=parsed_date,
                    data=day_lessons,
                ))
        db.commit()

        for lesson in lessons:
            result.append(filter_lessons(lesson))
        break

    return result

@router.get("/group/{group_id}")
def get_group_schedule(group_id: str, date_from: date, date_to: date, db: Session = Depends(get_db)):
    return get_schedule("group", group_id, date_from, date_to, db)

@router.get("/teacher/{teacher_id}")
def get_teacher_schedule(teacher_id: str, date_from: date, date_to: date, db: Session = Depends(get_db)):
    return get_schedule("teacher", teacher_id, date_from, date_to, db)

@router.get("/auditorium/{auditorium_id}")
def get_auditorium_schedule(auditorium_id: str, date_from: date, date_to: date, db: Session = Depends(get_db)):
    return get_schedule("auditory", auditorium_id, date_from, date_to, db)
