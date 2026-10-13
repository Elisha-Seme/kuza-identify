"""Dashboard chatbot API. Stateless: the caller (dashboard) keeps the
conversation history and resends it each turn, same pattern as any other
Claude chat UI — nothing here touches learner data or the identification
pipeline.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.core.auth import client_ip, rate_limit

from app.schemas.api import ChatRequest, ChatResponse
from app.services.chatbot import service as chatbot

router = APIRouter(prefix="/chatbot", tags=["chatbot"])


@router.get("/starters", response_model=list[str])
def starters() -> list[str]:
    """Suggested opening questions shown before the visitor has typed anything."""
    return chatbot.starter_suggestions()


@router.post("/message", response_model=ChatResponse)
def send_message(body: ChatRequest, request: Request) -> ChatResponse:
    # Public and backed by a paid model, so it's capped per visitor and per message.
    rate_limit(f"chat:{client_ip(request)}", limit=30, window_s=600)
    if len(body.message) > 1000:
        raise HTTPException(413, "Please keep questions under 1000 characters.")
    body.history = body.history[-12:]
    history = [chatbot.ChatTurn(role=t.role, content=t.content) for t in body.history]
    result = chatbot.ask(body.message, history)
    return ChatResponse(reply=result.reply, suggestions=result.suggestions, live=result.live)
