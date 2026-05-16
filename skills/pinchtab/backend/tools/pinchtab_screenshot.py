"""pinchtab_screenshot — take a screenshot of a browser tab."""

from ._pinchtab_api import _api


def execute(agent: dict, args: dict) -> dict:
    """Take a screenshot of a browser tab.

    Args:
        tab_id: ID of the tab to screenshot.
        full_page: If true, capture the full scrollable page (default: false).

    Returns:
        Screenshot result, typically containing a base64-encoded image.
    """
    tab_id = args.get("tab_id", "")
    full_page = args.get("full_page", False)

    if not tab_id:
        return {"error": "tab_id is required."}

    # PinchTab may support query parameters for screenshot options
    path = f"/api/tabs/{tab_id}/screenshot"
    if full_page:
        path += "?full_page=true"

    result = _api("GET", path)
    if "error" in result:
        return result
    return {
        "tab_id": tab_id,
        "full_page": full_page,
        "screenshot": result,
    }
