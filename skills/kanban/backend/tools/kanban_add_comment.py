"""
Kanban add comment tool — log progress notes on a kanban task.
"""

import re
from plugins.kanban.db import kanban_db


def _is_subagent_of(assignee_id: str, agent_id: str) -> bool:
    if not assignee_id or not agent_id:
        return False
    return bool(re.match(f"^{re.escape(agent_id)}_sub_\\d+$", assignee_id))


def execute(agent: dict, args: dict) -> dict:
    agent_id = agent.get('id', '')
    task_id = args.get('task_id', '').strip().lstrip('#')
    content = args.get('content', '').strip()

    if not task_id:
        return {'status': 'error', 'message': 'task_id is required'}
    if not content:
        return {'status': 'error', 'message': 'content is required'}

    task = kanban_db.get(task_id)
    if not task:
        return {'status': 'error', 'message': f'Task {task_id} not found'}

    parent_id = agent.get('parent_id', '')
    assignee = task.get('assignee')
    picked_by = task.get('picked_by')
    is_assignee_ok = (assignee == agent_id or assignee == parent_id or _is_subagent_of(assignee, agent_id))
    is_picker_ok = (picked_by == agent_id or picked_by == parent_id or _is_subagent_of(picked_by, agent_id))
    if not is_assignee_ok and not is_picker_ok:
        return {'status': 'error', 'message': 'You are not authorized to comment on this task'}

    comment = kanban_db.add_comment(task_id, content, author=agent_id)
    if not comment:
        return {'status': 'error', 'message': 'Failed to add comment'}

    return {'status': 'success', 'comment': comment}
