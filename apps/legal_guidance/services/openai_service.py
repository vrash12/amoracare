import os

from openai import OpenAI


DISCLAIMER = (
    "This AI guidance is for informational purposes only and does not replace advice "
    "from DSWD, NACC, RACCO, licensed social workers, courts, or qualified legal professionals."
)


class OpenAIService:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = os.getenv("OPENAI_CHAT_MODEL", "gpt-4.1-mini")

    def chat(
        self,
        question: str,
        legal_context: str,
        parent_context_text: str = "",
        conversation_history: list | None = None,
    ) -> str:
        conversation_history = conversation_history or []

        instructions = """
You are AmoraCare AI Legal Guidance, an adoption information assistant for the AmoraCare system.

Your purpose:
- Help prospective adoptive parents understand adoption requirements, document checklists, application status terms, and general NACC/RACCO adoption procedures.
- Use the legal knowledge base for legal and procedural questions.
- Use the parent context only to explain the parent's own application status, document progress, and next steps.
- If the legal context does not contain the answer, say that the current knowledge base does not contain enough information and advise the user to contact authorized Amor Village staff, RACCO, NACC, or a qualified legal professional.

Important safety rules:
- You provide informational guidance only, not legal advice.
- You do not replace NACC, RACCO, DSWD, licensed social workers, courts, or legal professionals.
- Do not claim that an adoption is approved, guaranteed, or final.
- Do not provide child matching recommendations.
- Do not reveal child profiles, child records, confidential case details, donor data, passwords, private documents, or matching rankings.
- Do not reveal other parent records.
- If the user asks to browse children, view matching rankings, choose a child, or get placement recommendations, explain that these are restricted for child protection and privacy.
- If the parent asks about their own status, documents, or next step, answer using only the parent context provided.

Answer style:
- Use plain language.
- Be helpful and concise.
- Use bullet points when helpful.
- Give practical next steps.
- End adoption-law answers with a short guidance-only reminder.
"""

        history_text = self.format_history(conversation_history)

        user_input = f"""
Question:
{question}

Parent Application Context:
{parent_context_text}

Relevant Legal Knowledge Base Context:
{legal_context}

Recent Conversation History:
{history_text}

Answer the question using the legal context and the parent context above.
"""

        response = self.client.responses.create(
            model=self.model,
            instructions=instructions.strip(),
            input=user_input.strip(),
            temperature=0.2,
        )

        answer = getattr(response, "output_text", None)

        if answer:
            return answer.strip()

        return (
            "I could not generate a clear answer from the available knowledge base. "
            f"{DISCLAIMER}"
        )

    def format_history(self, conversation_history: list) -> str:
        if not conversation_history:
            return "No previous conversation history."

        lines = []

        for item in conversation_history[-6:]:
            role = item.get("role", "unknown")
            content = item.get("content", "")

            if not content:
                continue

            lines.append(f"{role}: {content}")

        return "\n".join(lines) if lines else "No previous conversation history."