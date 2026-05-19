import json
from typing import Any, Dict, List


def safe_value(value, default="unknown"):
    if value is None or value == "":
        return default
    return value


def make_chunk_id(project_id: str, chunk_type: str, item_id: str = "main") -> str:
    return f"{safe_value(project_id)}:{chunk_type}:{safe_value(item_id, 'main')}"


def flatten_json(obj: Any, prefix: str = "") -> List[str]:
    lines = []

    if isinstance(obj, dict):
        for key, value in obj.items():
            new_prefix = f"{prefix}.{key}" if prefix else key
            lines.extend(flatten_json(value, new_prefix))
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            new_prefix = f"{prefix}[{index}]"
            lines.extend(flatten_json(value, new_prefix))
    else:
        lines.append(f"{prefix}: {obj}")

    return lines


def normalize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {"data": []}

    data = payload.get("data")

    if isinstance(data, list):
        return payload

    if isinstance(data, dict):
        return {**payload, "data": [data]}

    if "project" in payload:
        return {"data": [payload]}

    return {**payload, "data": []}


def get_raidd_parts(item: Dict[str, Any]) -> Dict[str, Any]:
    project = item.get("project", {}) or {}
    top_raidd = item.get("raidd") or {}
    ai_detection = top_raidd.get("aiDetection") or {}

    old_ai = project.get("projectAiDetails") or {}
    old_flags = old_ai.get("raiddFlags") or {}

    email = ai_detection.get("email") or {}
    raidd_data = ai_detection.get("raiddData") or email.get("raiddData") or {}

    return {
        "raidd": top_raidd,
        "ai_detection": ai_detection,
        "email": email,
        "risks": raidd_data.get("risks") or old_flags.get("risks") or [],
        "issues": raidd_data.get("issues") or old_flags.get("issues") or [],
        "assumptions": raidd_data.get("assumptions") or old_flags.get("assumptions") or [],
        "dependencies": raidd_data.get("dependencies") or old_flags.get("dependencies") or [],
        "decisions": raidd_data.get("decisions") or old_flags.get("decisions") or [],
        "message": ai_detection.get("raiddMessage") or email.get("raiddMessage") or old_ai.get("summary"),
        "analysis": ai_detection.get("raiddAnalysis") or email.get("raiddAnalysis") or top_raidd.get("type") or [],
        "summary": ai_detection.get("summary") or old_ai.get("summary"),
        "source_type": ai_detection.get("sourceType") or email.get("source") or "unknown",
        "title": ai_detection.get("title") or email.get("subject") or top_raidd.get("title") or "Untitled",
    }


def chunk_full_json_payload(payload: Dict[str, Any], max_lines: int = 40) -> List[Dict[str, Any]]:
    payload = normalize_payload(payload)
    chunks = []

    for item in payload.get("data", []):
        project = item.get("project", {}) or {}
        project_id = safe_value(project.get("id"))
        project_name = safe_value(project.get("name"), "Unknown Project")

        lines = flatten_json(item)

        for i in range(0, len(lines), max_lines):
            part = lines[i:i + max_lines]

            text = f"""
Project Name: {project_name}
Project ID: {project_id}

Full JSON searchable data:
{chr(10).join(part)}
""".strip()

            chunks.append({
                "id": f"{project_id}:full_json:{i // max_lines}",
                "text": text,
                "metadata": {
                    "project_id": project_id,
                    "project_name": project_name,
                    "type": "full_json",
                    "chunk_index": i // max_lines,
                },
            })

    return chunks


def chunk_project_payload(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    payload = normalize_payload(payload)
    chunks = []

    for item in payload.get("data", []):
        project = item.get("project", {}) or {}
        project_id = safe_value(project.get("id"))
        project_name = safe_value(project.get("name"), "Unknown Project")

        manager = project.get("manager") or {}
        assign_team = project.get("assignTeam") or {}
        client = project.get("client") or {}
        raidd_parts = get_raidd_parts(item)

        manager_name = f"{manager.get('firstName', '')} {manager.get('lastName', '')}".strip()

        overview_text = f"""
Project Name: {project_name}
Project ID: {project_id}
Project Status: {project.get("status")}
Project Health: {project.get("projectHealth")}
Project Progress: {project.get("projectProgress")}
Client Name: {project.get("clientName") or client.get("name")}
Client Email: {client.get("email")}
Manager Name: {manager_name}
Manager Role: {manager.get("role")}
Assigned Team: {assign_team.get("name")}
Project Owner ID: {project.get("projectOwnerId")}
Manager ID: {project.get("managerId")}
Start Date: {project.get("startDate")}
End Date: {project.get("endDate")}

Description:
{project.get("description")}

Discussion Points:
{json.dumps(project.get("discussionPoints", []), ensure_ascii=False)}

Action Points:
{json.dumps(project.get("actionPoints", []), ensure_ascii=False)}
"""

        chunks.append({
            "id": make_chunk_id(project_id, "overview"),
            "text": overview_text.strip(),
            "metadata": {
                "project_id": project_id,
                "project_name": project_name,
                "type": "project_overview",
                "status": safe_value(project.get("status")),
                "health": safe_value(project.get("projectHealth")),
            },
        })

        raidd_id = safe_value(raidd_parts["raidd"].get("id"), "main")
        raidd_text = f"""
Project Name: {project_name}
Project ID: {project_id}
RAIDD ID: {raidd_id}
RAIDD Type: {json.dumps(raidd_parts["raidd"].get("type") or raidd_parts["analysis"], ensure_ascii=False)}
RAIDD Status: {raidd_parts["raidd"].get("status")}
AI Detection Title: {raidd_parts["title"]}
AI Detection Summary: {raidd_parts["summary"]}
AI Detection Source Type: {raidd_parts["source_type"]}
RAIDD Message: {raidd_parts["message"]}
RAIDD Analysis: {json.dumps(raidd_parts["analysis"], ensure_ascii=False)}

Risks:
{json.dumps(raidd_parts["risks"], ensure_ascii=False)}

Assumptions:
{json.dumps(raidd_parts["assumptions"], ensure_ascii=False)}

Issues:
{json.dumps(raidd_parts["issues"], ensure_ascii=False)}

Dependencies:
{json.dumps(raidd_parts["dependencies"], ensure_ascii=False)}

Decisions:
{json.dumps(raidd_parts["decisions"], ensure_ascii=False)}

Source Email Subject: {raidd_parts["email"].get("subject")}
Source Email Sentiment: {raidd_parts["email"].get("sentiment")}
Source Email Body:
{raidd_parts["email"].get("body")}
"""

        chunks.append({
            "id": make_chunk_id(project_id, "raidd", raidd_id),
            "text": raidd_text.strip(),
            "metadata": {
                "project_id": project_id,
                "project_name": project_name,
                "type": "raidd_ai_detection",
                "raidd_id": raidd_id,
                "source_type": safe_value(raidd_parts["source_type"]),
            },
        })

        for task in project.get("tasks", []):
            task_text = f"""
Project Name: {project_name}
Project ID: {project_id}
Task Title: {task.get("title")}
Task Status: {task.get("status")}
Task Priority: {task.get("priority")}
Start Date: {task.get("startDate")}
End Date: {task.get("endDate")}

Description:
{task.get("taskDescription")}
"""

            chunks.append({
                "id": make_chunk_id(project_id, "task", task.get("id")),
                "text": task_text.strip(),
                "metadata": {
                    "project_id": project_id,
                    "project_name": project_name,
                    "type": "task",
                    "task_id": safe_value(task.get("id")),
                    "task_status": safe_value(task.get("status")),
                    "priority": safe_value(task.get("priority")),
                },
            })

        for meeting in project.get("meetings", []):
            transcript = meeting.get("transcriptData") or []
            meeting_text = f"""
Project Name: {project_name}
Project ID: {project_id}
Meeting Title: {meeting.get("title")}
Meeting Date: {meeting.get("meetingDate")}
Meeting URL: {meeting.get("meetingUrl")}
Video Play URL: {meeting.get("videoPlayUrl")}
Transcript URL: {meeting.get("transcriptUrl")}
Transcript Play URL: {meeting.get("transcriptPlayUrl")}
Transcript Status: {meeting.get("transcriptStatus")}

Notes:
{meeting.get("notes")}

Project Summary:
{meeting.get("projectSummary")}

Last Meeting Summary:
{meeting.get("lastMeetingSummary")}

Agenda:
{json.dumps(meeting.get("agenda", {}), ensure_ascii=False)}

Key Points:
{json.dumps(meeting.get("keyPoints", []), ensure_ascii=False)}

Action Points:
{json.dumps(meeting.get("actionPoints", []), ensure_ascii=False)}

Transcript:
{json.dumps(transcript[:80], ensure_ascii=False)}
"""

            chunks.append({
                "id": make_chunk_id(project_id, "meeting", meeting.get("id")),
                "text": meeting_text.strip(),
                "metadata": {
                    "project_id": project_id,
                    "project_name": project_name,
                    "type": "meeting",
                    "meeting_id": safe_value(meeting.get("id")),
                    "meeting_title": safe_value(meeting.get("title")),
                },
            })

    return chunks