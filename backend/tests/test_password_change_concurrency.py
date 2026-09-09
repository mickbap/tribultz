"""Exercise the real password-change UPDATE against a newer committed credential."""
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy import Boolean, Column, DateTime, Integer, String, create_engine, select, update
from sqlalchemy.orm import Session, declarative_base
from starlette.requests import Request

from app.routers import auth

Base = declarative_base()


class Credential(Base):
    __tablename__ = "credentials"
    id = Column(Integer, primary_key=True)
    password_hash = Column(String)
    session_version = Column(Integer)
    password_reset_version = Column(Integer)
    is_active = Column(Boolean)
    deleted_at = Column(DateTime, nullable=True)


@pytest.mark.parametrize("intervening", [None, "reset", "revoke", "disable"])
def test_password_change_requires_unchanged_credential(tmp_path, intervening):
    engine = create_engine(f"sqlite:///{tmp_path / 'credentials.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(Credential(id=1, password_hash="old-password", session_version=0,
                          password_reset_version=0, is_active=True))
        db.commit()
    admitted_user = SimpleNamespace(id=1, password_hash="old-password", session_version=0)

    def hash_after_verification(password):
        # A second transaction commits after request admission/password verification.
        if intervening:
            values: dict[str, Any] = {"session_version": 1}
            if intervening == "reset":
                values.update(password_hash="recovered-password", password_reset_version=1)
            if intervening == "disable":
                values["is_active"] = False
            with Session(engine) as other:
                other.execute(update(Credential).where(Credential.id == 1).values(**values))
                other.commit()
        return password

    with (
        Session(engine) as db,
        patch.object(auth, "User", Credential),
        patch.object(auth._login_limiter, "check_or_raise"),
        patch.object(auth, "verify_password", side_effect=lambda password, hashed: password == hashed),
        patch.object(auth, "get_password_hash", side_effect=hash_after_verification),
    ):
        args: dict[str, Any] = dict(data=auth.ChangePasswordRequest(current_password="old-password", new_password="late-password"),
                    request=Request({"type": "http", "headers": [], "client": ("127.0.0.1", 1)}),
                    current_user=admitted_user, db=db)
        if intervening:
            with pytest.raises(HTTPException) as error:
                auth.change_password(**args)
            assert error.value.status_code == 409
        else:
            assert auth.change_password(**args)["status"] == "ok"
    with Session(engine) as db:
        stored = db.scalar(select(Credential))
        assert stored is not None
        assert cast(int, stored.session_version) == 1
        expected = "recovered-password" if intervening == "reset" else "old-password" if intervening else "late-password"
        assert cast(str, stored.password_hash) == expected
    engine.dispose()
