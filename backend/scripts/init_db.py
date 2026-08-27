"""Run once to create all tables: `python -m scripts.init_db` from backend/."""
from app.db import models  # noqa: F401 — registers models with Base.metadata
from app.db.base import Base
from app.db.session import engine


def main():
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Done.")


if __name__ == "__main__":
    main()