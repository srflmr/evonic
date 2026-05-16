"""pinchtab_new_tab — open a new browser tab in a PinchTab instance."""

from ._pinchtab_api import _api


def execute(agent: dict, args: dict) -> dict:
    """Open a new tab in a PinchTab instance.

    Args:
        instance_id: ID of the browser instance to create a tab in.
        url: Optional URL to navigate the new tab to.

    Returns:
        The new tab's info including its tab_id.
    """
    instance_id = args.get("instance_id", "")
    if not instance_id:
        return {"error": "instance_id is required. Use pinchtab_list_instances to find available instances."}

    body = {}
    url = args.get("url", "")
    if url:
        body["url"] = url

    result = _api("POST", f"/api/instances/{instance_id}/tabs", body)
    if "error" in result:
        return result
    return {
        "message": "Tab created successfully.",
        "tab": result,
    }
