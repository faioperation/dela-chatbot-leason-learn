from datetime import datetime

from sqlalchemy.orm import Session

from app.services.project_analysis_models import ProjectFact


def normalize(text: str) -> str:
    return text.lower().strip()


def save_project_facts(db: Session, payload: dict):
    seen_ids = set()

    for item in payload.get("data", []):
        project = item.get("project", {})
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
            {"fact_type": "vendor", "question_key": "vendor", "answer": f"The vendor for {project_name} is {project.get('vendorName')}."},
            {"fact_type": "team", "question_key": "team", "answer": f"The assigned team for {project_name} is {assign_team.get('name')}."},
            {"fact_type": "owner", "question_key": "owner", "answer": f"The project owner ID for {project_name} is {project.get('projectOwnerId')}."},
            {
                "fact_type": "health",
                "question_key": "health",
                "answer": f"The project {project_name} health is {project.get('projectHealth')}. AI score is {ai.get('projectScore')} and flag is {ai.get('flag')}.",
            },
            {"fact_type": "progress", "question_key": "progress", "answer": f"The project {project_name} progress is {project.get('projectProgress')}."},
            {"fact_type": "tasks", "question_key": "tasks", "answer": f"Tasks for {project_name}: " + (", ".join(task_titles) if task_titles else "No tasks found.")},
            {"fact_type": "meetings", "question_key": "meetings", "answer": f"Meetings for {project_name}: " + (", ".join(meeting_titles) if meeting_titles else "No meetings found.")},
            {"fact_type": "issues", "question_key": "issues", "answer": f"Issues for {project_name}: " + (", ".join(raidd.get("issues", [])) if raidd.get("issues") else "No issues found.")},
            {"fact_type": "risks", "question_key": "risks", "answer": f"Risks for {project_name}: " + (", ".join(raidd.get("risks", [])) if raidd.get("risks") else "No risks found.")},
            {"fact_type": "decisions", "question_key": "decisions", "answer": f"Decisions for {project_name}: " + (", ".join(raidd.get("decisions", [])) if raidd.get("decisions") else "No decisions found.")},
            {"fact_type": "assumptions", "question_key": "assumptions", "answer": f"Assumptions for {project_name}: " + (", ".join(raidd.get("assumptions", [])) if raidd.get("assumptions") else "No assumptions found.")},
            {"fact_type": "dependencies", "question_key": "dependencies", "answer": f"Dependencies for {project_name}: " + (", ".join(raidd.get("dependencies", [])) if raidd.get("dependencies") else "No dependencies found.")},
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
        ("issues", ("issue", "problem")),
        ("risks", ("risk",)),
        ("decisions", ("decision",)),
        ("assumptions", ("assumption",)),
        ("dependencies", ("depend", "dependency")),
        ("action_points", ("action", "todo", "next step")),
        ("summary", ("summary", "summarize", "note", "detail", "weekly")),
        ("description", ("what is", "about", "describe")),
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
            answers.append(fact.answer)

    if not answers:
        return None

    return {"answer": "\n\n".join(answers), "source": "database_cache"}
