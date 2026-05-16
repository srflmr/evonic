"""pinchtab_click — click on an element in a browser tab."""

from ._pinchtab_api import _api


def execute(agent: dict, args: dict) -> dict:
    """Click on an element in a browser tab.

    Args:
        tab_id: ID of the tab.
        selector: CSS selector or accessibility node ID of the element to click.

    Returns:
        Click result from PinchTab.
    """
    tab_id = args.get("tab_id", "")
    selector = args.get("selector", "")

    if not tab_id:
        return {"error": "tab_id is required."}
    if not selector:
        return {"error": "selector is required. Use a CSS selector or accessibility node ID from pinchtab_snapshot."}

    result = _api("POST", f"/api/tabs/{tab_id}/click", {"selector": selector})
    if "error" in result:
        return result
    return {
        "message": f"Clicked element '{selector}'.",
        "result": result,
    }
