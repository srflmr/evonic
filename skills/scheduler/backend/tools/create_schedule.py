"""Create a new scheduled job."""

import json

from backend.scheduler import scheduler


def _ensure_dict(val, default=None):
    """Normalize a value to a dict — parse JSON string if needed."""
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            pass
    return default if default is not None else {}


def execute(agent: dict, args: dict) -> dict:
    agent_id = agent.get('id', '')

    action_config = _ensure_dict(args.get('action_config'))
    trigger_config = _ensure_dict(args.get('trigger_config'))
    action_type = args.get('action_type', '')

    # Default target to the calling agent for message-type actions.
    # agent_message is a deprecated alias for static_message.
    if action_type in ('static_message', 'agent_message', 'session_prompt') and 'agent_id' not in action_config:
        action_config['agent_id'] = agent_id

    # Check for bare (no timezone) run_date in date triggers before calling scheduler
    _warning = None
    if args.get('trigger_type') == 'date':
        run_date = trigger_config.get('run_date', '')
        if run_date and isinstance(run_date, str):
            try:
                from datetime import datetime
                if datetime.fromisoformat(run_date).tzinfo is None:
                    _warning = "run_date has no timezone info — treated as local time (WIB/UTC+7)"
            except (ValueError, TypeError):
                pass  # Malformed — let scheduler.create_schedule handle errors

    try:
        result = scheduler.create_schedule(
            name=args['name'],
            owner_type='agent',
            owner_id=agent_id,
            trigger_type=args['trigger_type'],
            trigger_config=trigger_config,
            action_type=args['action_type'],
            action_config=action_config,
            max_runs=args.get('max_runs'),
        )
        response = {
            'status': 'success',
            'schedule_id': result['id'],
            'name': result['name'],
            'trigger_type': result['trigger_type'],
            'enabled': bool(result['enabled']),
        }
        if _warning:
            response['_warning'] = _warning
        return response
    except Exception as e:
        return {'status': 'error', 'error': str(e)}
