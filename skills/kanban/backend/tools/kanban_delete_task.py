"""
Kanban delete task tool — permanently remove a task from the Kanban board.

Permission is controlled by setting 'kanban:delete_task_super_only':
- When enabled (default): only super agent and the task creator can delete tasks
- When disabled: all regular agents can delete (subject to human approval)

Permission model:
- Super agent: deletes immediately.
- Task owner (agent who created the task): can delete even when delete_task_super_only=true,
  subject to human approval for regular agents.
- Regular agent (non-owner): requires delete_task_super_only=false, then human approval
  → re-executes with _skip_safety=True.
"""

from plugins.kanban.db import kanban_db


def execute(agent: dict, args: dict) -> dict:
    task_id = args.get('task_id', '').strip().lstrip('#')

    if not task_id:
        return {'status': 'error', 'message': 'task_id is required'}

    # Fetch task before delete — db.delete() only returns bool
    task = kanban_db.get(task_id)
    if not task:
        return {'status': 'error', 'message': f'Task #{task_id} not found'}

    # Permission check
    is_super = agent.get('is_super')
    is_owner = task.get('created_by') and task.get('created_by') == agent.get('id')

    # Task owners can delete their own tasks regardless of delete_task_super_only
    # Non-owners must still pass the super_only gate
    if not is_super and not is_owner:
        try:
            from backend.skills_manager import skills_manager
            config = skills_manager.get_skill_config('kanban')
            super_only = bool(config.get('delete_task_super_only', True))
        except Exception:
            super_only = True  # fail closed
        if super_only:
            return {
                'status': 'error',
                'message': 'You are not authorized to delete tasks. Only the super agent or task owners can delete tasks.'
            }

    skip_safety = agent.get('_skip_safety')

    if not is_super and not skip_safety:
        return {
            'level': 'requires_approval',
            'approval_info': {
                'risk_level': 'medium',
                'description': 'Delete kanban task',
                'task_id': task_id,
                'task_title': task.get('title', ''),
            },
            'reasons': [f"Deleting task #{task_id}: '{task.get('title', '')}'"],
        }

    # Perform deletion
    kanban_db.delete(task_id)
    kanban_db.log_task_deleted(task_id)

    # Emit event
    try:
        from backend.event_stream import event_stream
        event_stream.emit('kanban_task_deleted', {'deleted_task': task})
    except Exception:
        pass

    return {
        'status': 'success',
        'message': f'Task #{task_id} deleted',
        'deleted_task': task,
    }
