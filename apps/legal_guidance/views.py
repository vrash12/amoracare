# django-ai-service/apps/legal_guidance/views.py

from __future__ import annotations

import logging
import secrets
from datetime import date
from typing import Any

from django.conf import settings
from openai import APIConnectionError, APITimeoutError, OpenAIError
from requests.exceptions import RequestException as RequestsException
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import LegalGuidanceRequestSerializer
from .services.legal_vector_store import LegalVectorStore
from .services.openai_service import OpenAIService
from .services.parent_context_service import ParentContextService
from .services.tavily_service import TavilyService


logger = logging.getLogger(__name__)

DISCLAIMER = (
    "This AI guidance is for informational purposes only and does not replace advice "
    "from DSWD, NACC, RACCO, licensed social workers, courts, or qualified legal professionals."
)

PARENT_SOURCE = {
    "title": "Your AmoraCare application record",
    "type": "parent_context",
}

RESTRICTED_KEYWORDS = (
    "show child",
    "show children",
    "browse child",
    "browse children",
    "child profile",
    "child profiles",
    "available children",
    "recommend a child",
    "match me",
    "matching recommendation",
    "rank children",
    "rank child",
    "choose a child",
    "which child",
    "who should i adopt",
    "best child for me",
    "matching rankings",
    "matching score",
    "donor record",
    "donor records",
    "confidential note",
    "confidential notes",
)

# Questions that ask for an explanation of a restriction are allowed.
# They must not be treated the same as requests to reveal restricted data.
RESTRICTED_EXPLANATION_KEYWORDS = (
    "why can i not",
    "why can't i",
    "why am i not allowed",
    "why are child profiles",
    "why is child information",
    "why are matching rankings",
    "why is matching restricted",
    "explain child profile privacy",
    "explain matching privacy",
    "what can parents view",
    "who handles matching decisions",
    "how does matching work",
    "are child profiles restricted",
    "are matching rankings restricted",
)

PARENT_IDENTITY_KEYWORDS = (
    "who am i",
    "what is my name",
    "what's my name",
    "my name",
    "my information",
    "my info",
    "my details",
    "my profile",
    "my parent profile",
    "my account",
    "my email",
    "my phone",
    "my preferences",
    "my preference",
    "my home study",
    "my scores",
)

ADOPTION_KEYWORDS = (
    "adoption",
    "adopt",
    "domestic adoption",
    "inter-country adoption",
    "requirements",
    "requirement",
    "documents",
    "document",
    "documentary",
    "home study",
    "home study report",
    "pre-adoption",
    "pre adoption",
    "forum",
    "nacc",
    "racco",
    "dswd",
    "social worker",
    "case study",
    "matching",
    "placement",
    "court",
    "petition",
    "certificate",
    "clearance",
    "eligibility",
    "applicant",
    "prospective parent",
    "application",
    "case",
    "status",
    "progress",
    "submit",
    "submitted",
    "missing",
    "next step",
    "next steps",
    "legal",
    "law",
)

APPLICATION_KEYWORDS = (
    "submit",
    "submitted",
    "still need",
    "need to submit",
    "missing",
    "requirements",
    "requirement",
    "progress",
    "status",
    "application",
    "my case",
    "my documents",
    "what do i need",
    "what do i still need",
    "next step",
    "next steps",
    "where am i",
    "what stage",
)

CURRENT_INFORMATION_KEYWORDS = (
    "latest",
    "current",
    "updated",
    "new rule",
    "new rules",
    "recent",
    "today",
    "this year",
    "nacc update",
    "racco update",
    "dswd update",
    "memorandum",
    "circular",
    "guidelines",
    "amendment",
    "amended",
    "effective date",
)

GREETING_MESSAGES = {
    "hi",
    "hello",
    "hey",
    "good morning",
    "good afternoon",
    "good evening",
    "how are you",
    "kamusta",
    "kumusta",
}

THANK_YOU_MESSAGES = {
    "thanks",
    "thank you",
    "salamat",
}


class LegalGuidanceAskView(APIView):
    """
    Legal-guidance endpoint used by the Laravel parent portal.

    Processing order:
    1. Validate the request.
    2. Handle greetings, restrictions, and deterministic parent-record answers.
    3. Search the local legal vector store.
    4. Use Tavily only when current information or a retrieval fallback is needed.
    5. Send separated legal, parent, and conversation contexts to OpenAI.
    """

    authentication_classes: list = []
    permission_classes = [AllowAny]

    LOCAL_RESULT_LIMIT = 4
    WEB_RESULT_LIMIT = 3
    MIN_LOCAL_SIMILARITY = 0.35
    MAX_LOCAL_CHUNK_CHARACTERS = 5000
    MAX_WEB_RESULT_CHARACTERS = 3500
    MAX_CONTEXT_CHARACTERS = 28000

    def get(self, request) -> Response:
        if not self._is_internal_request_authorized(request):
            return self._error_response(
                message="Unauthorized request.",
                http_status=status.HTTP_401_UNAUTHORIZED,
            )

        return Response(
            {
                "success": True,
                "service": "AmoraCare AI Legal Guidance",
                "message": "The legal-guidance endpoint is running. Use POST to ask a question.",
                "features": {
                    "local_legal_search": True,
                    "tavily_web_fallback": bool(
                        getattr(settings, "TAVILY_ENABLED", False)
                    ),
                    "parent_context": True,
                    "conversation_history": True,
                },
                "example_body": {
                    "question": "What documents do I still need to submit?",
                    "parent_context": {
                        "has_application": True,
                        "parent": {
                            "name": "Sample Parent",
                            "email": "sample@example.com",
                        },
                    },
                    "conversation_history": [],
                },
                "disclaimer": DISCLAIMER,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request) -> Response:
        if not self._is_internal_request_authorized(request):
            return self._error_response(
                message="Unauthorized request.",
                http_status=status.HTTP_401_UNAUTHORIZED,
            )

        serializer = LegalGuidanceRequestSerializer(data=request.data)

        if not serializer.is_valid():
            return self._error_response(
                message="Invalid request.",
                http_status=status.HTTP_400_BAD_REQUEST,
                errors=serializer.errors,
            )

        question = self._clean_text(serializer.validated_data["question"])
        parent_context = serializer.validated_data.get("parent_context") or {}
        conversation_history = (
            serializer.validated_data.get("conversation_history") or []
        )

        predefined_response = self._get_predefined_response(
            question=question,
            parent_context=parent_context,
        )

        if predefined_response:
            return self._success_response(
                question=question,
                answer=predefined_response,
                sources=[],
            )

        parent_context_answer = self._answer_from_parent_context(
            question=question,
            parent_context=parent_context,
        )

        if parent_context_answer:
            return self._success_response(
                question=question,
                answer=parent_context_answer,
                sources=[PARENT_SOURCE],
            )

        local_chunks, local_error = self._retrieve_local_chunks(question)

        web_results: list[dict[str, Any]] = []
        web_error: Exception | None = None

        if self._should_search_web(question, local_chunks):
            web_results, web_error = self._retrieve_web_results(question)

        if not local_chunks and not web_results:
            logger.warning(
                "No legal guidance sources found. local_error=%s web_error=%s",
                local_error,
                web_error,
            )

            return self._success_response(
                question=question,
                answer=(
                    "I could not find sufficiently reliable adoption guidance in the current "
                    "local legal knowledge base or approved official web sources. Please ask a "
                    "more specific question or contact authorized AmoraCare staff, RACCO, NACC, "
                    "DSWD, or a qualified legal professional for official guidance."
                ),
                sources=[],
                retrieval={
                    "local_results": 0,
                    "web_results": 0,
                    "web_search_attempted": self._should_search_web(
                        question,
                        local_chunks,
                    ),
                },
            )

        legal_context = self._format_legal_context(
            local_chunks=local_chunks,
            web_results=web_results,
        )

        parent_context_text = ParentContextService().build_context_text(
            parent_context
        )

        try:
            answer = OpenAIService().chat(
                question=question,
                legal_context=legal_context,
                parent_context_text=parent_context_text,
                conversation_history=conversation_history,
            )
        except (APIConnectionError, APITimeoutError, RequestsException) as exc:
            logger.exception("Unable to connect to the AI service.")

            return self._error_response(
                message=(
                    "Unable to connect to the AI service. Check your OpenAI API key, "
                    "network connection, and configured model."
                ),
                http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
                exception=exc,
            )
        except OpenAIError as exc:
            logger.exception("OpenAI returned an error while generating guidance.")

            return self._error_response(
                message="The AI provider could not generate an answer.",
                http_status=status.HTTP_502_BAD_GATEWAY,
                exception=exc,
            )
        except Exception as exc:
            logger.exception("Unexpected legal-guidance generation error.")

            return self._error_response(
                message="The AI service could not generate an answer.",
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                exception=exc,
            )

        sources = self._format_sources(
            local_chunks=local_chunks,
            web_results=web_results,
            include_parent_context=bool(parent_context),
        )

        return self._success_response(
            question=question,
            answer=answer,
            sources=sources,
            retrieval={
                "local_results": len(local_chunks),
                "web_results": len(web_results),
                "web_search_used": bool(web_results),
            },
        )

    def _retrieve_local_chunks(
        self,
        question: str,
    ) -> tuple[list[dict[str, Any]], Exception | None]:
        try:
            results = LegalVectorStore().search(
                query=question,
                limit=self.LOCAL_RESULT_LIMIT,
            )

            valid_results = [
                item
                for item in results
                if isinstance(item, dict) and self._clean_text(item.get("text"))
            ]

            return valid_results, None
        except (APIConnectionError, APITimeoutError, OpenAIError) as exc:
            logger.warning("Local embedding/vector search failed: %s", exc)
            return [], exc
        except Exception as exc:
            logger.exception("Unexpected local vector-search error.")
            return [], exc

    def _retrieve_web_results(
        self,
        question: str,
    ) -> tuple[list[dict[str, Any]], Exception | None]:
        try:
            results = TavilyService().search(
                query=self._build_tavily_query(question),
                max_results=self.WEB_RESULT_LIMIT,
            )

            valid_results = []

            for item in results:
                if not isinstance(item, dict):
                    continue

                url = self._clean_text(item.get("url"))
                content = self._clean_text(item.get("content"))

                if not url or not content:
                    continue

                valid_results.append(item)

            return valid_results, None
        except RequestsException as exc:
            logger.warning("Tavily request failed: %s", exc)
            return [], exc
        except Exception as exc:
            logger.exception("Unexpected Tavily search error.")
            return [], exc

    def _get_predefined_response(
        self,
        question: str,
        parent_context: dict | None = None,
    ) -> str | None:
        normalized = self._normalize_question(question)

        if normalized in GREETING_MESSAGES:
            return (
                "Hello! I’m AmoraCare AI Legal Guidance. I can help explain adoption "
                "requirements, document checklists, application steps, and general "
                "NACC, RACCO, and DSWD procedures. You may also ask about your own "
                "application status and parent-visible documents."
            )

        if normalized in THANK_YOU_MESSAGES:
            return "You’re welcome. Feel free to ask another adoption-related question."

        if self._contains_any(normalized, RESTRICTED_KEYWORDS):
            # Let explanatory questions continue to retrieval and OpenAI so the
            # assistant can explain the policy and cite official online sources.
            if self._is_restricted_explanation_question(normalized):
                return None

            # Actual requests to reveal, browse, rank, or recommend restricted
            # records remain blocked before retrieval or model generation.
            return (
                "I can’t browse child profiles, reveal confidential records, rank children, "
                "show matching scores, or provide placement recommendations. Those records "
                "and decisions are restricted for privacy and child protection. You may ask "
                "why these restrictions exist, what information parents can view, or who "
                "handles matching decisions. For case-specific help, contact authorized "
                "AmoraCare staff or your assigned social worker."
            )

        has_parent_context = bool(parent_context)

        if has_parent_context and self._contains_any(
            normalized,
            PARENT_IDENTITY_KEYWORDS,
        ):
            return None

        is_adoption_related = self._contains_any(normalized, ADOPTION_KEYWORDS)
        is_application_related = self._contains_any(
            normalized,
            APPLICATION_KEYWORDS,
        )
        has_parent_application = bool(
            parent_context and parent_context.get("has_application")
        )

        if not is_adoption_related:
            if has_parent_application and is_application_related:
                return None

            return (
                "I’m designed for adoption-related legal information, documentary "
                "requirements, application steps, and general NACC, RACCO, and DSWD "
                "procedures. Please ask an adoption-related question."
            )

        return None

    def _answer_from_parent_context(
        self,
        question: str,
        parent_context: dict,
    ) -> str | None:
        if not parent_context or not isinstance(parent_context, dict):
            return None

        normalized = self._normalize_question(question)
        parent = self._safe_dict(parent_context.get("parent"))
        matching_profile = self._safe_dict(
            parent_context.get("matching_profile")
        )

        if self._contains_any(normalized, PARENT_IDENTITY_KEYWORDS):
            if not parent:
                return (
                    "I could not find your parent profile in the current request context. "
                    "Please make sure you are logged in and that AmoraCare is sending your "
                    "parent context to the AI service."
                )

            answer_parts = [
                f"You are logged in as **{parent.get('name') or 'N/A'}**.",
                (
                    f"- **Email:** {parent.get('email') or 'N/A'}\n"
                    f"- **Phone number:** {parent.get('phone_number') or 'N/A'}\n"
                    f"- **Account status:** {parent.get('account_status') or 'N/A'}\n"
                    f"- **Role:** {parent.get('role') or 'Prospective Parent'}"
                ),
            ]

            if matching_profile:
                answer_parts.append(
                    "Your parent matching profile shows:\n"
                    f"- **Preferred child sex:** {matching_profile.get('preferred_child_sex') or 'N/A'}\n"
                    f"- **Preferred child age range:** "
                    f"{self._display_value(matching_profile.get('min_child_age'))} to "
                    f"{self._display_value(matching_profile.get('max_child_age'))}\n"
                    f"- **Open to special needs:** "
                    f"{self._yes_no(matching_profile.get('open_to_special_needs'))}\n"
                    f"- **Home study verified:** "
                    f"{self._yes_no(matching_profile.get('home_study_verified'))}\n"
                    f"- **Financial capacity score:** "
                    f"{self._display_value(matching_profile.get('financial_capacity_score'))}\n"
                    f"- **Housing readiness score:** "
                    f"{self._display_value(matching_profile.get('housing_score'))}\n"
                    f"- **Parenting capacity score:** "
                    f"{self._display_value(matching_profile.get('parenting_capacity_score'))}"
                )

            if parent_context.get("has_application"):
                case = self._safe_dict(parent_context.get("case"))
                answer_parts.append(
                    f"Your current application status is **"
                    f"{case.get('status_label') or case.get('status') or 'Not available'}**."
                )
            else:
                answer_parts.append(
                    "I could not find an active adoption application linked to your account."
                )

            answer_parts.append(
                "This answer is based only on your parent-visible AmoraCare account context."
            )

            return "\n\n".join(answer_parts)

        if not parent_context.get("has_application"):
            if self._contains_any(normalized, APPLICATION_KEYWORDS):
                answer_parts = [
                    "I could not find an active adoption application linked to your account."
                ]

                if parent:
                    answer_parts.append(
                        f"Your account on record is **{parent.get('name') or 'N/A'}** "
                        f"with status **{parent.get('account_status') or 'N/A'}**."
                    )

                if matching_profile:
                    answer_parts.append(
                        "Your parent matching profile may already exist, but an active "
                        "adoption case has not yet been assigned."
                    )

                answer_parts.append(
                    "Please contact authorized AmoraCare staff if you believe this is "
                    "incorrect or need the next official step."
                )

                return "\n\n".join(answer_parts)

            return None

        document_keywords = (
            "submit",
            "submitted",
            "still need",
            "need to submit",
            "missing",
            "requirements",
            "requirement",
            "documents",
            "document",
            "what do i need",
            "what do i still need",
        )
        progress_keywords = (
            "progress",
            "status",
            "application status",
            "case status",
            "where am i",
            "what stage",
            "next step",
            "next steps",
            "my case",
        )

        is_document_question = self._contains_any(
            normalized,
            document_keywords,
        )
        is_progress_question = self._contains_any(
            normalized,
            progress_keywords,
        )

        if not is_document_question and not is_progress_question:
            return None

        case = self._safe_dict(parent_context.get("case"))
        progress = self._safe_dict(parent_context.get("document_progress"))
        documents = self._safe_list(parent_context.get("parent_documents"))
        updates = self._safe_list(parent_context.get("parent_visible_updates"))

        grouped_documents: dict[str, list[dict[str, Any]]] = {
            "pending": [],
            "submitted": [],
            "under_review": [],
            "verified": [],
            "rejected": [],
            "expired": [],
        }

        for item in documents:
            document = self._safe_dict(item)
            document_name = self._clean_text(document.get("document_name"))
            document_status = self._clean_text(document.get("status"))

            if not document_name or document_status not in grouped_documents:
                continue

            grouped_documents[document_status].append(document)

        verified_count = progress.get("verified_documents_count", 0)
        required_count = progress.get("required_documents_count", 0)
        progress_percent = progress.get("progress_percent", 0)
        progress_sentence = (
            f"Your document progress is **{verified_count} out of {required_count} "
            f"verified** ({progress_percent}%)."
        )

        answer_parts: list[str] = []

        if is_progress_question:
            answer_parts.append(
                f"Your application is currently at **"
                f"{case.get('status_label') or case.get('status') or 'Not available'}**."
            )
            answer_parts.append(progress_sentence)

            if updates:
                latest_update = self._safe_dict(updates[0])
                title = latest_update.get("title") or "Update"
                body = self._clean_text(latest_update.get("body"))
                created_at = latest_update.get("created_at")
                update_text = f"- **{title}**"

                if created_at:
                    update_text += f" ({created_at})"

                if body:
                    update_text += f": {body}"

                answer_parts.extend(
                    [
                        "Latest parent-visible update:",
                        update_text,
                    ]
                )

        if is_document_question:
            if progress_sentence not in answer_parts:
                answer_parts.append(progress_sentence)

            action_needed = (
                grouped_documents["pending"]
                + grouped_documents["rejected"]
                + grouped_documents["expired"]
            )

            if action_needed:
                answer_parts.append("These items may still need action:")

                for document in grouped_documents["pending"]:
                    answer_parts.append(
                        f"- **{document.get('document_name')}** — not yet submitted."
                    )

                for document in grouped_documents["rejected"]:
                    text = (
                        f"- **{document.get('document_name')}** — rejected and may "
                        "need resubmission."
                    )
                    remarks = self._clean_text(document.get("remarks"))

                    if remarks:
                        text += f" Remarks: {remarks}"

                    answer_parts.append(text)

                for document in grouped_documents["expired"]:
                    answer_parts.append(
                        f"- **{document.get('document_name')}** — expired and may "
                        "need renewal or resubmission."
                    )
            else:
                answer_parts.append(
                    "There are no pending, rejected, or expired parent documents in "
                    "your current parent-visible record."
                )

            self._append_document_group(
                answer_parts,
                heading="Submitted and waiting for review:",
                documents=grouped_documents["submitted"],
                status_label="submitted",
            )
            self._append_document_group(
                answer_parts,
                heading="Currently under review:",
                documents=grouped_documents["under_review"],
                status_label="under review",
            )
            self._append_document_group(
                answer_parts,
                heading="Already verified:",
                documents=grouped_documents["verified"],
                status_label="verified",
            )

        assigned_worker = self._clean_text(case.get("assigned_social_worker"))

        if assigned_worker:
            answer_parts.append(
                f"For official confirmation, coordinate with your assigned social "
                f"worker, **{assigned_worker}**."
            )
        else:
            answer_parts.append(
                "For official confirmation, coordinate with authorized AmoraCare staff."
            )

        answer_parts.append(
            "This answer is based only on your parent-visible AmoraCare application record."
        )

        return "\n\n".join(answer_parts)

    def _should_search_web(
        self,
        question: str,
        local_chunks: list[dict[str, Any]],
    ) -> bool:
        normalized = self._normalize_question(question)
        current_year = str(date.today().year)

        if current_year in normalized:
            return True

        if self._contains_any(normalized, CURRENT_INFORMATION_KEYWORDS):
            return True

        # Privacy and matching-policy explanation questions benefit from
        # current official sources, so let Tavily search approved domains.
        if self._is_restricted_explanation_question(normalized):
            return True

        if not local_chunks:
            return True

        similarities = []

        for chunk in local_chunks:
            similarity = chunk.get("similarity")

            if isinstance(similarity, (int, float)):
                similarities.append(float(similarity))

        if similarities and max(similarities) < self.MIN_LOCAL_SIMILARITY:
            return True

        return False

    def _build_tavily_query(self, question: str) -> str:
        cleaned_question = self._clean_text(question)
        current_year = date.today().year

        return (
            f"{cleaned_question} Philippines adoption NACC RACCO DSWD "
            f"official {current_year}"
        )[:390]

    def _format_legal_context(
        self,
        local_chunks: list[dict[str, Any]],
        web_results: list[dict[str, Any]],
    ) -> str:
        sections: list[str] = []

        if local_chunks:
            local_context: list[str] = []

            for index, chunk in enumerate(local_chunks, start=1):
                source = self._clean_text(chunk.get("source")) or "Unknown source"
                chunk_index = chunk.get("chunk_index", "N/A")
                page_start = chunk.get("page_start")
                page_end = chunk.get("page_end")
                text = self._clean_text(chunk.get("text"))[
                    : self.MAX_LOCAL_CHUNK_CHARACTERS
                ]

                page_label = ""

                if page_start is not None:
                    page_label = f" | Page {page_start}"

                    if page_end is not None and page_end != page_start:
                        page_label += f"-{page_end}"

                local_context.append(
                    f"[Local Source {index}: {source} | Chunk {chunk_index}"
                    f"{page_label}]\n{text}"
                )

            sections.append(
                "LOCAL LEGAL KNOWLEDGE BASE:\n"
                + "\n\n---\n\n".join(local_context)
            )

        if web_results:
            web_context: list[str] = []

            for index, result in enumerate(web_results, start=1):
                title = self._clean_text(result.get("title")) or "Official web source"
                url = self._clean_text(result.get("url"))
                content = self._clean_text(result.get("content"))[
                    : self.MAX_WEB_RESULT_CHARACTERS
                ]

                web_context.append(
                    f"[Official Web Source {index}: {title}]\n"
                    f"URL: {url}\n"
                    f"Content: {content}"
                )

            sections.append(
                "CURRENT OFFICIAL WEB RETRIEVAL:\n"
                + "\n\n---\n\n".join(web_context)
            )

        context = "\n\n====================\n\n".join(sections)

        if not context:
            return (
                "No reliable legal context was retrieved. Do not guess. Advise the "
                "user to contact authorized AmoraCare staff, RACCO, NACC, DSWD, or a "
                "qualified legal professional."
            )

        return context[: self.MAX_CONTEXT_CHARACTERS]

    def _format_sources(
        self,
        local_chunks: list[dict[str, Any]],
        web_results: list[dict[str, Any]],
        include_parent_context: bool = False,
    ) -> list[dict[str, Any]]:
        sources: list[dict[str, Any]] = []

        if include_parent_context:
            sources.append(PARENT_SOURCE.copy())

        seen_local: set[tuple[Any, Any]] = set()

        for chunk in local_chunks:
            source_name = self._clean_text(chunk.get("source")) or "Local source"
            chunk_index = chunk.get("chunk_index")
            key = (source_name, chunk_index)

            if key in seen_local:
                continue

            seen_local.add(key)

            source = {
                "title": source_name,
                "type": "local_vector_store",
                "chunk_index": chunk_index,
                "page_start": chunk.get("page_start"),
                "page_end": chunk.get("page_end"),
                "similarity": chunk.get("similarity"),
                "distance": chunk.get("distance"),
            }

            sources.append(
                {key: value for key, value in source.items() if value is not None}
            )

        seen_urls: set[str] = set()

        for result in web_results:
            url = self._clean_text(result.get("url"))

            if not url or url in seen_urls:
                continue

            seen_urls.add(url)

            source = {
                "title": self._clean_text(result.get("title")) or url,
                "url": url,
                "type": "tavily_web",
                "score": result.get("score"),
            }

            sources.append(
                {key: value for key, value in source.items() if value is not None}
            )

        return sources

    def _success_response(
        self,
        question: str,
        answer: str,
        sources: list[dict[str, Any]],
        retrieval: dict[str, Any] | None = None,
    ) -> Response:
        payload: dict[str, Any] = {
            "success": True,
            "question": question,
            "answer": answer,
            "sources": sources,
            "disclaimer": DISCLAIMER,
        }

        if retrieval is not None:
            payload["retrieval"] = retrieval

        return Response(payload, status=status.HTTP_200_OK)

    def _error_response(
        self,
        message: str,
        http_status: int,
        errors: Any | None = None,
        exception: Exception | None = None,
    ) -> Response:
        payload: dict[str, Any] = {
            "success": False,
            "message": message,
        }

        if errors is not None:
            payload["errors"] = errors

        if exception is not None and getattr(settings, "DEBUG", False):
            payload["details"] = str(exception)

        return Response(payload, status=http_status)

    def _is_internal_request_authorized(self, request) -> bool:
        """
        Optional shared-secret protection.

        Add LEGAL_GUIDANCE_INTERNAL_API_KEY to Django settings to enable it.
        When the setting is empty, existing local development calls keep working.
        Laravel should send the value through the X-Legal-Guidance-Key header.
        """
        expected_key = str(
            getattr(settings, "LEGAL_GUIDANCE_INTERNAL_API_KEY", "") or ""
        ).strip()

        if not expected_key:
            return True

        supplied_key = str(
            request.headers.get("X-Legal-Guidance-Key", "") or ""
        ).strip()

        return bool(supplied_key) and secrets.compare_digest(
            supplied_key,
            expected_key,
        )

    @staticmethod
    def _normalize_question(value: Any) -> str:
        return " ".join(str(value or "").lower().strip().rstrip("?!.").split())

    @staticmethod
    def _clean_text(value: Any) -> str:
        if value is None:
            return ""

        return " ".join(str(value).replace("\x00", "").split()).strip()

    @staticmethod
    def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
        return any(keyword in text for keyword in keywords)

    @staticmethod
    def _is_restricted_explanation_question(text: str) -> bool:
        """Return True when the user asks why a restriction exists.

        This separates harmless policy/explanation questions from requests to
        browse, reveal, rank, or recommend protected records.
        """
        return any(keyword in text for keyword in RESTRICTED_EXPLANATION_KEYWORDS)

    @staticmethod
    def _safe_dict(value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _safe_list(value: Any) -> list[Any]:
        return value if isinstance(value, list) else []

    @staticmethod
    def _display_value(value: Any) -> str:
        if value is None or value == "":
            return "N/A"

        return str(value)

    @staticmethod
    def _append_document_group(
        answer_parts: list[str],
        heading: str,
        documents: list[dict[str, Any]],
        status_label: str,
    ) -> None:
        if not documents:
            return

        answer_parts.append(heading)

        for document in documents:
            document_name = document.get("document_name") or "Unnamed document"
            answer_parts.append(
                f"- **{document_name}** — {status_label}."
            )

    @staticmethod
    def _yes_no(value: Any) -> str:
        if value is True:
            return "Yes"

        if value is False:
            return "No"

        normalized = str(value).strip().lower()

        if normalized in {"1", "true", "yes"}:
            return "Yes"

        if normalized in {"0", "false", "no"}:
            return "No"

        return "N/A"
