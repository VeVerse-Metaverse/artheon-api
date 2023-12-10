# Dependency
from app.database import SessionLocal


# def get_db():
#     db = None
#     try:
#         db = SessionLocal()
#         yield db
#     finally:
#         if db is not None:
#             db.close()


def session():
    db = None
    try:
        db = SessionLocal()
        yield db
    finally:
        if db is not None:
            db.close()
