from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class CaptchaSession:
    session_id: str
    challenge: str
    gt: str
    gt_user_id: str
    account_label: str
    context: str
    created_at: float = field(default_factory=time.time)
    done: asyncio.Event = field(default_factory=asyncio.Event)
    validate: Optional[str] = None
    cancelled: bool = False

    def complete(self, validate: str) -> None:
        self.validate = validate
        self.done.set()

    def cancel(self) -> None:
        self.cancelled = True
        self.done.set()


_active_session: Optional[CaptchaSession] = None
_sessions: Dict[str, CaptchaSession] = {}


def create_session(
    challenge: str,
    gt: str,
    gt_user_id: str,
    account_label: str,
    context: str = "",
) -> CaptchaSession:
    global _active_session
    if _active_session and not _active_session.done.is_set():
        _active_session.cancel()
    session = CaptchaSession(
        session_id=uuid.uuid4().hex[:12],
        challenge=challenge,
        gt=gt,
        gt_user_id=gt_user_id,
        account_label=account_label,
        context=context,
    )
    _active_session = session
    _sessions[session.session_id] = session
    return session


def get_active_session() -> Optional[CaptchaSession]:
    return _active_session


def cancel_active_session() -> Optional[CaptchaSession]:
    global _active_session
    if _active_session and not _active_session.done.is_set():
        _active_session.cancel()
        return _active_session
    return None


def submit_validate(validate: str) -> bool:
    session = _active_session
    if not session or session.done.is_set():
        return False
    session.complete(validate.strip())
    return True
