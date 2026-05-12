from __future__ import annotations

from collections.abc import Generator

from sqlalchemy.orm import Session

from nyc_pulse.db import get_session


def get_db_session() -> Generator[Session, None, None]:
    session = get_session()
    try:
        yield session
    finally:
        session.close()
