"""Access control, consent and v2 question-bank behaviour.

Needs the same migrated Postgres as test_end_to_end.py.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.db import SessionLocal
from app.core.enums import ConsentScope, Language, LearnerSource, StaffRole
from app.main import app
from app.models import ConsentRecord, DomainScore, ItemResponse, Learner, School
from app.services.adaptive_item_engine import engine as items
from tests.test_end_to_end import _staff_headers

client = TestClient(app)


@pytest.fixture()
def db():
    s = SessionLocal()
    yield s
    s.close()


def _consented_learner(db) -> tuple[School, Learner]:
    school = School(name="Access School", tier="low_resource", network="pilot")
    db.add(school)
    db.flush()
    learner = Learner(school_id=school.id, source=LearnerSource.active_screening)
    db.add(learner)
    db.flush()
    db.add(ConsentRecord(learner_id=learner.id, guardian_identifier="g", scope=ConsentScope.screening))
    db.commit()
    return school, learner


# ------------------------------------------------------------------ access
@pytest.mark.parametrize("method,path", [
    ("get", "/panel/flagged"),
    ("get", "/panel/metrics"),
    ("get", "/panel/audit-log"),
    ("get", "/admin/users"),
    ("post", "/admin/demo-screening"),
    ("post", "/screening/webhook/bind"),
    ("post", "/screening/webhook/sms/bind"),
    ("post", "/screening/webhook/ussd/bind"),
])
def test_staff_routes_need_sign_in(method, path):
    assert getattr(client, method)(path).status_code == 401


def test_roles_see_only_their_part(db):
    reviewer = _staff_headers(db, StaffRole.reviewer)
    auditor = _staff_headers(db, StaffRole.auditor)
    admin = _staff_headers(db, StaffRole.programme_admin)

    assert client.get("/panel/flagged", headers=reviewer).status_code == 200
    assert client.get("/admin/users", headers=reviewer).status_code == 403
    assert client.get("/panel/flagged", headers=auditor).status_code == 403  # no individual profiles
    assert client.get("/panel/metrics", headers=auditor).status_code == 200
    assert client.get("/panel/audit-log", headers=auditor).status_code == 200
    assert client.get("/admin/users", headers=admin).status_code == 200
    # admins manage, they don't decide
    r = client.post(f"/panel/sessions/{uuid.uuid4()}/decision", json={"decision": "advance"}, headers=admin)
    assert r.status_code == 403


def test_wrong_password_and_deactivation(db):
    admin = _staff_headers(db, StaffRole.programme_admin)
    email = f"rev-{uuid.uuid4().hex[:6]}@test.kuza"
    r = client.post("/admin/users", headers=admin, json={
        "email": email, "display_name": "Rev", "role": "reviewer", "password": "long-enough-pw"})
    assert r.status_code == 200
    uid = r.json()["id"]
    assert client.post("/auth/login", json={"email": email, "password": "nope"}).status_code == 401
    tok = client.post("/auth/login", json={"email": email, "password": "long-enough-pw"}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    assert client.get("/auth/me", headers=h).json()["role"] == "reviewer"
    client.post(f"/admin/users/{uid}/deactivate", headers=admin)
    assert client.get("/auth/me", headers=h).status_code == 401  # takes effect immediately


def test_tampered_token_rejected(db):
    h = _staff_headers(db, StaffRole.reviewer)
    body, sig = h["Authorization"].split(" ")[1].split(".")
    forged = {"Authorization": f"Bearer {body}x.{sig}"}
    assert client.get("/panel/flagged", headers=forged).status_code == 401


def test_school_staff_scoped_to_own_school(db):
    _, learner = _consented_learner(db)
    other = School(name="Other", tier="low_resource", network="pilot")
    db.add(other)
    db.commit()
    h = _staff_headers(db, StaffRole.school_staff, other.id)
    r = client.post("/screening/sessions", headers=h,
                    json={"learner_id": str(learner.id), "channel": "whatsapp", "language": "en"})
    assert r.status_code == 403


def test_reset_disabled_by_default():
    assert client.post("/admin/reset", headers={"X-Admin-Token": "x"}).status_code in (403,)
    # GET variants with the token in the URL are gone entirely
    assert client.get("/admin/init?token=x").status_code == 405


# ------------------------------------------------------------------ consent
def test_teacher_nomination_is_not_guardian_consent(db):
    school = School(name="Nom School", tier="low_resource", network="pilot")
    db.add(school)
    db.commit()
    r = client.post("/nomination", json={
        "school_id": str(school.id), "nominator_role": "teacher",
        "checklist_responses": {"quick_grasp": True}, "guardian_identifier": "web-teacher-consent"})
    assert r.status_code == 200
    lid = uuid.UUID(r.json()["learner_id"])
    assert db.query(ConsentRecord).filter_by(learner_id=lid).count() == 0

    r = client.post("/nomination", json={
        "school_id": str(school.id), "nominator_role": "parent",
        "checklist_responses": {"quick_grasp": True}, "guardian_identifier": "guardian-1"})
    lid = uuid.UUID(r.json()["learner_id"])
    assert db.query(ConsentRecord).filter_by(learner_id=lid).count() == 1


# ------------------------------------------------------------------ question bank
def test_public_items_hide_answers_and_guidance():
    for path in ("/screening/items", "/screening/items/bonus"):
        for it in client.get(path).json():
            assert "answer" not in it and "expected_reasoning" not in it
    bank = client.get("/screening/items/all").json()
    assert len(bank["items"]) >= 30
    assert all("answer" not in it for it in bank["items"])
    assert any(it.get("image") for it in bank["items"])


def test_core_set_is_one_item_per_domain():
    core = items.all_items()
    assert len(core) == 5
    assert len({i.domain for i in core}) == 5
    for i in core:
        assert i.fallback(Language.en) and i.fallback(Language.sw), i.id  # SMS/USSD wording exists


def test_every_image_file_exists():
    from pathlib import Path

    public = Path(__file__).resolve().parents[2] / "dashboard" / "public" / "items"
    for it in items.every_item():
        for k in ("image", "image_png", "image_after", "image_after_png"):
            if it.raw.get(k):
                assert (public / it.raw[k]).exists(), it.raw[k]


def test_choice_parsing():
    assert items.parse_choice_indices("2", 4) == [1]
    assert items.parse_choice_indices("b", 4) == [1]
    assert items.parse_choice_indices("BDAC", 4) == [1, 3, 0, 2]
    assert items.parse_choice_indices("b, d, a, c", 4) == [1, 3, 0, 2]
    assert items.parse_choice_indices("9", 4) == []


def test_skip_is_not_scored_and_hints_are_recorded(db):
    school, learner = _consented_learner(db)
    staff = _staff_headers(db, StaffRole.school_staff, school.id)
    start = client.post("/screening/sessions", headers=staff,
                        json={"learner_id": str(learner.id), "channel": "sms", "language": "en"}).json()
    sid = start["session_id"]
    def say(text):
        return client.post("/screening/responses", json={"session_id": sid, "raw_response": text}).json()

    # First core item is the memory item: step 1 is "remember", with no options.
    assert "Remember:" in start["next_prompt"] and "2) Cup" not in start["next_prompt"]
    step2 = say("OK")["next_prompt"]
    # Step 2 asks the question, without repeating what had to be remembered.
    assert "2) Cup" in step2 and "key" not in step2.lower()
    r = say("repeat")
    assert r["status"] == "in_progress" and r["next_prompt"] == step2
    say("skip")  # skip the memory item
    for _ in range(4):
        say("hint")
        say("I worked it out step by step and I think the answer is B")
    rows = db.query(ItemResponse).filter_by(session_id=uuid.UUID(sid)).all()
    assert len(rows) == 5
    skipped = [r for r in rows if r.skipped]
    assert len(skipped) == 1 and skipped[0].raw_response == ""
    assert any(r.hints_used > 0 for r in rows if not r.skipped)
    scores = db.query(DomainScore).filter_by(session_id=uuid.UUID(sid)).all()
    assert len(scores) == 4  # the skipped domain has no score at all, not a zero
    assert skipped[0].item_id not in {s.domain for s in scores}


def test_bindings_survive_restart(db):
    """The phone->session link is in the DB, not process memory."""
    from app.models import ChannelBinding

    school, learner = _consented_learner(db)
    staff = _staff_headers(db, StaffRole.school_staff, school.id)
    sid = client.post("/screening/sessions", headers=staff,
                      json={"learner_id": str(learner.id), "channel": "whatsapp", "language": "en"}).json()["session_id"]
    digits = "2547" + str(uuid.uuid4().int)[:8]  # unique per run
    r = client.post("/screening/webhook/bind", json={"phone": f"+{digits}", "session_id": sid}, headers=staff)
    assert r.status_code == 200, r.text
    rows = db.query(ChannelBinding).all()
    assert any(str(r.session_id) == sid for r in rows)
    assert all(digits not in r.phone_hash for r in rows)  # stored hashed
    r = client.post("/screening/webhook/whatsapp", json={"from": digits, "text": "B"})
    assert r.status_code == 200


# ------------------------------------------------------------------ review fixes
def _sms_session(db):
    school, learner = _consented_learner(db)
    staff = _staff_headers(db, StaffRole.school_staff, school.id)
    sid = client.post("/screening/sessions", headers=staff,
                      json={"learner_id": str(learner.id), "channel": "sms", "language": "en"}).json()["session_id"]

    def say(text, **kw):
        return client.post("/screening/responses", json={"session_id": sid, "raw_response": text, **kw})
    return sid, say, staff, school


def test_pause_then_resume_is_not_an_answer(db):
    sid, say, *_ = _sms_session(db)
    say("OK")  # memory step 1 -> question
    assert "saved" in say("pause").json()["next_prompt"]
    resumed = say("hi, I'm back").json()["next_prompt"]
    assert "2) Cup" in resumed  # the same question again
    assert db.query(ItemResponse).filter_by(session_id=uuid.UUID(sid)).count() == 0


def test_ordinary_words_are_answers_not_commands(db):
    sid, say, *_ = _sms_session(db)
    say("OK")
    say("next")  # used to be a skip command; now it's just an answer
    row = db.query(ItemResponse).filter_by(session_id=uuid.UUID(sid)).one()
    assert row.raw_response == "next" and not row.skipped


def test_repeat_on_memory_step_one_shows_the_list_again(db):
    sid, say, *_ = _sms_session(db)
    r = say("repeat").json()["next_prompt"]
    assert "Remember:" in r and "2) Cup" not in r


def test_wrong_item_is_rejected_not_misfiled(db):
    sid, say, *_ = _sms_session(db)
    say("OK")
    assert say("B", item_id="num-p2").status_code == 409  # num-p2 isn't waiting yet
    assert say("B", item_id="wmm-p1").status_code == 200
    assert say("B", item_id="wmm-p1").status_code == 409  # double-tap doesn't hit the next item


def test_school_staff_cannot_hijack_another_schools_phone(db):
    sid_a, _, staff_a, _ = _sms_session(db)
    sid_b, _, staff_b, _ = _sms_session(db)  # a different school
    phone = "+2547" + str(uuid.uuid4().int)[:8]
    assert client.post("/screening/webhook/sms/bind", json={"phone": phone, "session_id": sid_a}, headers=staff_a).status_code == 200
    r = client.post("/screening/webhook/sms/bind", json={"phone": phone, "session_id": sid_b}, headers=staff_b)
    assert r.status_code == 409


def test_session_state_includes_channel(db):
    sid, *_ = _sms_session(db)
    j = client.get(f"/screening/sessions/{sid}").json()
    assert j["channel"] == "sms" and j["item_id"] == "wmm-p1"


def test_fails_closed_on_vercel_without_secret(monkeypatch):
    from app.core import auth

    monkeypatch.setenv("VERCEL", "1")
    assert not auth.is_local_dev()
    import fastapi

    with pytest.raises(fastapi.HTTPException) as e:
        auth.issue_token(uuid.uuid4(), StaffRole.reviewer, None)
    assert e.value.status_code == 503


# ------------------------------------------------------------------ codex review fixes
def test_phone_formats_are_canonical():
    from app.api.screening import canonical_phone

    for n in ("0712 345 678", "+254712345678", "whatsapp:+254712345678", "254-712-345-678", "712345678", "00254712345678"):
        assert canonical_phone(n) == "254712345678", n


def test_bind_sends_first_question_and_matches_provider_format(db):
    from app.providers.whatsapp import get_provider

    school, learner = _consented_learner(db)
    staff = _staff_headers(db, StaffRole.school_staff, school.id)
    sid = client.post("/screening/sessions", headers=staff,
                      json={"learner_id": str(learner.id), "channel": "whatsapp", "language": "en"}).json()["session_id"]
    local = "07" + str(uuid.uuid4().int)[:8]  # staff type the national form
    assert client.post("/screening/webhook/bind", json={"phone": local, "session_id": sid}, headers=staff).status_code == 200
    first = get_provider().last_message_to("+254" + local[1:])  # sent in E.164
    assert first and "Look carefully" in first  # the learner actually got the first question
    # The provider delivers +254…: it must reach the same session.
    intl = "+254" + local[1:]
    r = client.post("/screening/webhook/whatsapp", json={"from": intl, "text": "OK"})
    assert r.status_code == 200 and "2) Cup" in r.json()["delivered"]


def test_session_state_reports_language(db):
    school, learner = _consented_learner(db)
    staff = _staff_headers(db, StaffRole.school_staff, school.id)
    sid = client.post("/screening/sessions", headers=staff,
                      json={"learner_id": str(learner.id), "channel": "web", "language": "sw"}).json()["session_id"]
    assert client.get(f"/screening/sessions/{sid}").json()["language"] == "sw"
