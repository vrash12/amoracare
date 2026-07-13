class ParentContextService:
    """
    Formats the current parent's live context for the AI chatbot.

    Important:
    - Do not store parent information in ChromaDB.
    - Parent information should come live from Laravel.
    - This service only formats the safe parent-side context.
    """

    def build_context_text(self, parent_context: dict | None) -> str:
        if not parent_context or not isinstance(parent_context, dict):
            return (
                "No parent application context was provided. "
                "Use only the legal knowledge base and advise the parent to contact authorized staff "
                "for account-specific information."
            )

        has_application = parent_context.get("has_application", False)

        parent = parent_context.get("parent", {})
        matching_profile = parent_context.get("matching_profile", {})

        if not has_application:
            return f"""
Parent Context:
- Parent name: {parent.get("name") or parent_context.get("parent_name") or "N/A"}
- Email: {parent.get("email") or "N/A"}
- Phone number: {parent.get("phone_number") or "N/A"}
- Account status: {parent.get("account_status") or "N/A"}
- Application status: No active adoption application case is currently assigned.

Matching Profile:
- Preferred child sex: {matching_profile.get("preferred_child_sex") or "N/A"}
- Preferred child age range: {matching_profile.get("min_child_age") or "N/A"} to {matching_profile.get("max_child_age") or "N/A"}
- Open to special needs: {self.yes_no(matching_profile.get("open_to_special_needs"))}
- Home study verified: {self.yes_no(matching_profile.get("home_study_verified"))}
- Financial capacity score: {matching_profile.get("financial_capacity_score") or "N/A"}
- Housing readiness score: {matching_profile.get("housing_score") or "N/A"}
- Parenting capacity score: {matching_profile.get("parenting_capacity_score") or "N/A"}

Guidance:
- The chatbot may explain general adoption requirements.
- The chatbot may tell the parent that no active case is currently assigned.
- The chatbot must not reveal child profiles, matching rankings, or confidential records.
""".strip()

        case = parent_context.get("case", {})
        document_progress = parent_context.get("document_progress", {})
        parent_documents = parent_context.get("parent_documents", [])
        parent_visible_updates = parent_context.get("parent_visible_updates", [])
        privacy_rules = parent_context.get("privacy_rules", [])

        document_lines = []

        for document in parent_documents:
            document_lines.append(
                "- {name} | Status: {status} | Remarks: {remarks}".format(
                    name=document.get("document_name", "Unnamed document"),
                    status=document.get("status_label") or document.get("status") or "N/A",
                    remarks=document.get("remarks") or "No remarks",
                )
            )

        if not document_lines:
            document_lines.append("- No parent-side documents are currently listed.")

        update_lines = []

        for update in parent_visible_updates:
            update_lines.append(
                "- {title}: {body} ({date})".format(
                    title=update.get("title") or "Case update",
                    body=update.get("body") or "No update body",
                    date=update.get("created_at") or "No date",
                )
            )

        if not update_lines:
            update_lines.append("- No parent-visible updates are currently available.")

        privacy_lines = []

        for rule in privacy_rules:
            privacy_lines.append(f"- {rule}")

        if not privacy_lines:
            privacy_lines = [
                "- Do not reveal child profiles.",
                "- Do not reveal confidential case notes.",
                "- Do not reveal donor data.",
                "- Do not provide child matching recommendations.",
                "- Do not reveal matching rankings.",
                "- Do not reveal other parent records.",
                "- Only guide the parent about their own application status and next steps.",
            ]

        return f"""
Parent Context:
- Parent name: {parent.get("name") or parent_context.get("parent_name") or "N/A"}
- Email: {parent.get("email") or "N/A"}
- Phone number: {parent.get("phone_number") or "N/A"}
- Account status: {parent.get("account_status") or "N/A"}
- Role: {parent.get("role") or "N/A"}

Matching Profile:
- Preferred child sex: {matching_profile.get("preferred_child_sex") or "N/A"}
- Preferred child age range: {matching_profile.get("min_child_age") or "N/A"} to {matching_profile.get("max_child_age") or "N/A"}
- Open to special needs: {self.yes_no(matching_profile.get("open_to_special_needs"))}
- Home study verified: {self.yes_no(matching_profile.get("home_study_verified"))}
- Financial capacity score: {matching_profile.get("financial_capacity_score") or "N/A"}
- Housing readiness score: {matching_profile.get("housing_score") or "N/A"}
- Parenting capacity score: {matching_profile.get("parenting_capacity_score") or "N/A"}
- Matching notes: {matching_profile.get("matching_notes") or "No matching notes recorded"}

Application Case:
- Case code: {case.get("case_code") or "N/A"}
- Case type: {case.get("case_type_label") or case.get("case_type") or "N/A"}
- Current status: {case.get("status_label") or case.get("status") or "N/A"}
- Priority: {case.get("priority_label") or case.get("priority") or "N/A"}
- Opened at: {case.get("opened_at") or "N/A"}
- Target completion date: {case.get("target_completion_date") or "N/A"}
- Assigned social worker/staff: {case.get("assigned_social_worker") or "Not assigned"}

Document Progress:
- Required documents: {document_progress.get("required_documents_count", 0)}
- Submitted documents: {document_progress.get("submitted_documents_count", 0)}
- Verified documents: {document_progress.get("verified_documents_count", 0)}
- Progress percent: {document_progress.get("progress_percent", 0)}%

Parent Documents:
{chr(10).join(document_lines)}

Parent-Visible Updates:
{chr(10).join(update_lines)}

Privacy Rules:
{chr(10).join(privacy_lines)}
""".strip()

    def yes_no(self, value) -> str:
        if value is True:
            return "Yes"

        if value is False:
            return "No"

        if value in [1, "1", "true", "True", "yes", "Yes"]:
            return "Yes"

        if value in [0, "0", "false", "False", "no", "No"]:
            return "No"

        return "N/A"