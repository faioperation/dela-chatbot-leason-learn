from datetime import datetime

from sqlalchemy.orm import Session

from app.services.project_analysis_models import ProjectFact


def normalize(text: str) -> str:
    return text.lower().strip()


def get_project(item: dict) -> dict:
    project = item.get("project")

    if isinstance(project, dict):
        return project

    return item


def get_first_vendor(project: dict) -> dict:
    vendor = project.get("vendor")

    if isinstance(vendor, list):
        return vendor[0] if vendor and isinstance(vendor[0], dict) else {}

    if isinstance(vendor, dict):
        return vendor

    return {}


def format_vendor_answer(project_name: str, project: dict) -> str:
    vendor = get_first_vendor(project)
    vendor_name = vendor.get("name") or project.get("vendorName")

    if not vendor_name:
        return f"No vendor name was found for {project_name}."

    details = [f"The vendor for {project_name} is {vendor_name}."]

    if vendor.get("designation"):
        details.append(f"Designation: {vendor.get('designation')}.")
    if vendor.get("email"):
        details.append(f"Email: {vendor.get('email')}.")
    if vendor.get("phoneNumber"):
        details.append(f"Phone: {vendor.get('phoneNumber')}.")

    return " ".join(details)


def format_owner_answer(project_name: str, project: dict) -> str:
    owner_id = project.get("projectOwnerId")
    manager = project.get("manager") or {}
    manager_name = f"{manager.get('firstName', '')} {manager.get('lastName', '')}".strip()

    if owner_id and owner_id == manager.get("id") and manager_name:
        role = manager.get("role")
        answer = f"The project owner of {project_name} is {manager_name}"

        if role:
            answer += f" ({role})"

        answer += "."
        return answer

    if manager_name and not owner_id:
        role = manager.get("role")
        answer = f"The project owner of {project_name} is {manager_name}"

        if role:
            answer += f" ({role})"

        answer += "."
        return answer

    if owner_id:
        return f"The project owner ID for {project_name} is {owner_id}."

    return f"No project owner was found for {project_name}."


def save_project_facts(db: Session, payload: dict):
    seen_ids = set()

    for item in payload.get("data", []):
        project = get_project(item)
        project_id = project.get("id")
        project_name = project.get("name", "")

        if not project_id:
            continue

        ai = project.get("projectAiDetails") or {}
        raidd = ai.get("raiddFlags") or {}
        manager = project.get("manager") or {}
        assign_team = project.get("assignTeam") or {}
        manager_name = f"{manager.get('firstName', '')} {manager.get('lastName', '')}".strip()

        task_titles = [
            f"{task.get('title')} ({task.get('status')}, {task.get('priority')})"
            for task in project.get("tasks", [])
        ]
        meeting_titles = [
            f"{meeting.get('title')} on {meeting.get('meetingDate')}"
            for meeting in project.get("meetings", [])
        ]

        meeting_links = []
        for meeting in project.get("meetings", []):
            title = meeting.get("title") or "Meeting"
            for label, link in (
                ("", meeting.get("meetingUrl")),
                (" video link", meeting.get("videoPlayUrl")),
                (" transcript link", meeting.get("transcriptUrl")),
            ):
                if link:
                    meeting_links.append(f"{title}{label}: {link}")

        for link_item in project.get("meetingLinks", []):
            title = link_item.get("title", "Meeting link")
            link = link_item.get("link")
            if link:
                meeting_links.append(f"{title}: {link}")

        facts = [
            {
                "fact_type": "meeting_links",
                "question_key": "meeting links",
                "answer": f"Meeting links for {project_name}: "
                + ("\n".join(meeting_links) if meeting_links else "No meeting links found."),
            },
            {
                "fact_type": "description",
                "question_key": "description",
                "answer": project.get("description") or "No description found.",
            },
            {
                "fact_type": "status",
                "question_key": "status",
                "answer": (
                    f"The project {project_name} is currently {project.get('status')}. "
                    f"Its health is {project.get('projectHealth')}, "
                    f"progress is {project.get('projectProgress')}, "
                    f"and AI flag is {ai.get('flag')}."
                ),
            },
            {
                "fact_type": "manager",
                "question_key": "manager",
                "answer": f"The manager of {project_name} is {manager_name}. Their role is {manager.get('role')}.",
            },
            {"fact_type": "vendor", "question_key": "vendor", "answer": format_vendor_answer(project_name, project)},
            {"fact_type": "team", "question_key": "team", "answer": f"The assigned team for {project_name} is {assign_team.get('name')}."},
            {"fact_type": "owner", "question_key": "owner", "answer": format_owner_answer(project_name, project)},
            {
                "fact_type": "health",
                "question_key": "health",
                "answer": f"The project {project_name} health is {project.get('projectHealth')}. AI score is {ai.get('projectScore')} and flag is {ai.get('flag')}.",
            },
            {"fact_type": "progress", "question_key": "progress", "answer": f"The project {project_name} progress is {project.get('projectProgress')}."},
            {"fact_type": "tasks", "question_key": "tasks", "answer": f"Tasks for {project_name}: " + (", ".join(task_titles) if task_titles else "No tasks found.")},
            {"fact_type": "meetings", "question_key": "meetings", "answer": f"Meetings for {project_name}: " + (", ".join(meeting_titles) if meeting_titles else "No meetings found.")},
            {"fact_type": "action_points", "question_key": "action points", "answer": f"Recommended action points for {project_name}: " + (", ".join(ai.get("actionPoints", [])) if ai.get("actionPoints") else "No action points found.")},
            {"fact_type": "summary", "question_key": "summary", "answer": ai.get("summary") or project.get("weeklyAiSummary") or "No summary found."},
        ]

        for fact in facts:
            record_id = f"{project_id}:{fact['fact_type']}"
            if record_id in seen_ids:
                continue
            seen_ids.add(record_id)

            now = datetime.utcnow()
            existing = db.query(ProjectFact).filter(ProjectFact.id == record_id).first()

            if existing:
                existing.project_name = project_name
                existing.fact_type = fact["fact_type"]
                existing.question_key = fact["question_key"]
                existing.answer = fact["answer"]
                existing.updated_at = now
            else:
                db.add(ProjectFact(
                    id=record_id,
                    project_id=project_id,
                    project_name=project_name,
                    fact_type=fact["fact_type"],
                    question_key=fact["question_key"],
                    answer=fact["answer"],
                    updated_at=now,
                ))

    db.commit()


def find_cached_answer(db: Session, question: str):
    q = normalize(question)

    if "report" in q or "owner" in q:
        return None

    project = None
    project_names = [row[0] for row in db.query(ProjectFact.project_name).distinct().all() if row[0]]

    for name in project_names:
        if name.lower() in q:
            project = name
            break

    if not project and len(project_names) == 1:
        project = project_names[0]

    if not project:
        return None

    fact_types = []
    keyword_map = (
        ("manager", ("manager", "project manager")),
        ("vendor", ("vendor",)),
        ("team", ("team", "assigned")),
        ("owner", ("owner",)),
        ("status", ("status",)),
        ("health", ("health",)),
        ("progress", ("progress",)),
        ("tasks", ("task",)),
        ("action_points", ("action", "todo", "next step")),
        ("summary", ("summary", "summarize", "note", "detail", "weekly")),
        ("description", ("about", "describe")),
    )

    if ("meeting" in q and ("link" in q or "url" in q)) or "meeting link" in q:
        fact_types.append("meeting_links")
    elif "meeting" in q:
        fact_types.append("meetings")

    for fact_type, keywords in keyword_map:
        if any(keyword in q for keyword in keywords):
            fact_types.append(fact_type)

    fact_types = list(dict.fromkeys(fact_types))
    if not fact_types:
        return None

    answers = []
    for fact_type in fact_types:
        fact = (
            db.query(ProjectFact)
            .filter(ProjectFact.project_name == project)
            .filter(ProjectFact.fact_type == fact_type)
            .first()
        )
        if fact:
            if fact.fact_type == "vendor" and " is None." in fact.answer:
                continue
            answers.append(fact.answer)

    if not answers:
        return None

    return {"answer": "\n\n".join(answers), "source": "database_cache"}
