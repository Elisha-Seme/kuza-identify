"""Dashboard chatbot API. Stateless: the caller (dashboard) keeps the
conversation history and resends it each turn, same pattern as any other
Claude chat UI — nothing here touches learner data or the identification
pipeline.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.schemas.api import ChatRequest, ChatResponse
from app.services.chatbot import service as chatbot

router = APIRouter(prefix="/chatbot", tags=["chatbot"])


@router.get("/starters", response_model=list[str])
def starters() -> list[str]:
    """Suggested opening questions shown before the visitor has typed anything."""
    return chatbot.starter_suggestions()


@router.post("/message", response_model=ChatResponse)
def send_message(body: ChatRequest) -> ChatResponse:
    history = [chatbot.ChatTurn(role=t.role, content=t.content) for t in body.history]
    result = chatbot.ask(body.message, history)
    return ChatResponse(reply=result.reply, suggestions=result.suggestions, live=result.live)
