# django-ai-service/apps/legal_guidance/services/ollama_service.py

import json
import requests
from django.conf import settings


class OllamaService:
    def chat(
        self,
        question: str,
        context: str,
        parent_context: dict | None = None,
    ) -> str:
        parent_context = parent_context or {}

        system_prompt = """
You are AmoraCare AI Legal Guidance, a warm and professional adoption information assistant.

You help prospective adoptive parents understand:
- adoption requirements
- document checklists
- application status terms
- general NACC / RACCO / DSWD procedures
- their own application progress, if parent-specific context is provided

You receive two kinds of context:
1. Legal/procedural context from official documents.
2. Parent-specific application context from the AmoraCare system.

Use the parent-specific context only for that parent's own application status, document progress, and parent-visible updates.

Very important privacy and safety rules:
- Do not reveal child profiles.
- Do not reveal confidential case notes.
- Do not reveal donor data.
- Do not reveal private uploaded file contents.
- Do not provide child matching recommendations.
- Do not claim adoption is approved, guaranteed, or final.
- Do not provide legal advice.
- Do not invent requirements.
- If information is missing, say what the parent should confirm with AmoraCare staff, RACCO, NACC, DSWD, or a qualified professional.

Response style:
- Be warm, clear, and practical.
- Do not sound like you copied raw document text.
- If the user asks about their application, use the parent-specific context.
- If the user asks about general adoption rules, use the legal/procedural context.
- Use headings and short bullets.
"""

        parent_context_text = json.dumps(
            parent_context,
            indent=2,
            ensure_ascii=False,
        )

        user_prompt = f"""
Legal/procedural context:
{context}

Parent-specific application context:
{parent_context_text}

User question:
{question}

Write the answer using this structure when helpful:

Brief answer:
[Give a clear answer in 1-2 sentences.]

Application-specific guidance:
[If the parent context is relevant, explain their current status, document progress, or next step.]

General guidance:
[If legal/procedural context is relevant, explain the general rule or process in plain language.]

What you can do next:
[Give 1-3 practical next steps.]

Important reminder:
This is for informational guidance only. For official confirmation, contact authorized AmoraCare staff, RACCO, NACC, DSWD, or a qualified legal professional.

Do not mention internal JSON.
Do not mention source chunk numbers.
"""

        response = requests.post(
            f"{settings.OLLAMA_BASE_URL}/api/chat",
            json={
                "model": settings.OLLAMA_CHAT_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": user_prompt,
                    },
                ],
                "stream": False,
                "keep_alive": "15m",
                "options": {
                    "temperature": 0.25,
                    "num_ctx": 4096,
                    "num_predict": 450,
                    "top_p": 0.9,
                    "repeat_penalty": 1.08,
                },
            },
            timeout=240,
        )

        response.raise_for_status()

        data = response.json()

        return data.get("message", {}).get("content", "No response received.")