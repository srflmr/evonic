/**
 * Agent Sidebar — persistent left sidebar across all Evonic pages.
 * Shows agent avatars sorted by recent activity, with busy-state indicators,
 * hover tooltips, and click-to-navigate to agent detail chat tab.
 */

/** Simple hash function for deterministic avatar background colors */
function _sidebarHash(str) {
    var h = 0;
    for (var i = 0; i < str.length; i++) {
        h = ((h << 5) - h) + str.charCodeAt(i);
        h |= 0;
    }
    return Math.abs(h);
}

/** HSL color palette for avatar backgrounds — vibrant, dark-friendly */
var _AVATAR_COLORS = [
    'hsl(200, 70%, 40%)',
    'hsl(260, 60%, 45%)',
    'hsl(330, 60%, 42%)',
    'hsl(160, 55%, 35%)',
    'hsl(30, 70%, 38%)',
    'hsl(290, 50%, 40%)',
    'hsl(80, 50%, 32%)',
    'hsl(10, 65%, 40%)',
];

function _sidebarAvatarColor(agentId) {
    return _AVATAR_COLORS[_sidebarHash(agentId) % _AVATAR_COLORS.length];
}

/** --- Unread state (persists across page navigations via sessionStorage) --- */
var _UNREAD_KEY = 'evonic_unread_agents';

function _getUnreadSet() {
    try {
        return new Set(JSON.parse(sessionStorage.getItem(_UNREAD_KEY) || '[]'));
    } catch (_) { return new Set(); }
}

function _markUnread(agentId) {
    try {
        var s = _getUnreadSet();
        s.add(agentId);
        sessionStorage.setItem(_UNREAD_KEY, JSON.stringify(Array.from(s)));
    } catch (_) {}
}

function _clearUnread(agentId) {
    try {
        var s = _getUnreadSet();
        s.delete(agentId);
        sessionStorage.setItem(_UNREAD_KEY, JSON.stringify(Array.from(s)));
    } catch (_) {}
    var avatar = document.querySelector(
        '#agent-sidebar .agent-avatar[data-agent-id="' + CSS.escape(agentId) + '"]'
    );
    if (avatar) avatar.removeAttribute('data-unread');
}

/** Update which avatar has the .selected ring based on current URL */
function _updateSelectedAvatar() {
    var match = window.location.pathname.match(/^\/agents\/([^/]+)/);
    var currentId = match ? decodeURIComponent(match[1]) : null;
    document.querySelectorAll('#agent-sidebar .agent-avatar').forEach(function (el) {
        el.classList.toggle('selected', currentId !== null && el.getAttribute('data-agent-id') === currentId);
    });
}

/**
 * Navigate to an agent's chat tab. On agent detail pages softSwitchAgent()
 * swaps the page in place without a full reload; everywhere else (and on
 * soft-switch failure) fall back to a normal navigation.
 */
function _navigateToAgentChat(agentId) {
    _clearUnread(agentId);
    var dest = '/agents/' + encodeURIComponent(agentId) + '#chat';
    if (typeof window.softSwitchAgent === 'function') {
        // softSwitchAgent manages its own loading bar across the in-place swap
        window.softSwitchAgent(agentId).then(function (ok) {
            if (ok) {
                _updateSelectedAvatar();
            } else {
                window.location = dest;
            }
        });
    } else {
        // Full navigation: show the bar until the new page replaces it
        if (window.startNavProgress) window.startNavProgress();
        window.location = dest;
    }
}

/** Current tooltip element reference */
var _currentTooltip = null;

/** Fetch sidebar data and render */
async function fetchSidebarAgents() {
    try {
        var resp = await fetch('/api/dashboard/sidebar', { credentials: 'same-origin' });
        if (!resp.ok) return;
        var data = await resp.json();
        renderSidebar(data.agents || []);
    } catch (e) {
        console.warn('[agent-sidebar] fetch failed:', e);
    }
}

/** Render agent avatars inside #agent-sidebar */
function renderSidebar(agents) {
    var sidebar = document.getElementById('agent-sidebar');
    if (!sidebar) return;

    sidebar.innerHTML = '';

    agents.forEach(function (agent) {
        var avatar = document.createElement('div');
        avatar.className = 'agent-avatar';
        avatar.setAttribute('data-agent-id', agent.id);
        avatar.setAttribute('data-busy', agent.busy ? 'true' : 'false');
        if (_getUnreadSet().has(agent.id)) avatar.setAttribute('data-unread', 'true');
        avatar.setAttribute('title', agent.name);

        if (agent.avatar_path) {
            // Render custom avatar image
            var img = document.createElement('img');
            img.src = '/api/agents/' + encodeURIComponent(agent.id) + '/avatar';
            img.alt = agent.name;
            img.className = 'agent-avatar-img';
            img.onerror = function () {
                // Fallback to initial letter on load error
                img.style.display = 'none';
                var fallback = document.createElement('span');
                fallback.textContent = agent.name.charAt(0).toUpperCase();
                avatar.appendChild(fallback);
                avatar.style.backgroundColor = _sidebarAvatarColor(agent.id);
            };
            avatar.appendChild(img);
        } else {
            // No custom avatar: show initial letter with colored background
            avatar.style.backgroundColor = _sidebarAvatarColor(agent.id);
            var letter = document.createElement('span');
            letter.textContent = agent.name.charAt(0).toUpperCase();
            avatar.appendChild(letter);
        }

        avatar.addEventListener('click', function () {
            _navigateToAgentChat(agent.id);
        });

        avatar.addEventListener('mouseenter', function (e) {
            // Skip tooltip popup on mobile — tap goes directly to agent detail
            if (window.innerWidth <= 768) return;
            showTooltip(e, agent);
        });

        avatar.addEventListener('mouseleave', function () {
            hideTooltip();
        });

        sidebar.appendChild(avatar);
    });

    // Apply saved sidebar state after all elements (including burger) are rendered
    _applySidebarState();
    _updateSelectedAvatar();
}

/** Create and position tooltip */
function showTooltip(e, agent) {
    hideTooltip();

    var tooltip = document.createElement('div');
    tooltip.className = 'agent-sidebar-tooltip';

    var nameEl = document.createElement('span');
    nameEl.className = 'tt-name';
    nameEl.textContent = agent.name;

    var descEl = document.createElement('span');
    descEl.className = 'tt-desc';
    descEl.textContent = agent.description || '';

    var badge = document.createElement('span');
    badge.className = 'tt-badge ' + (agent.busy ? 'busy' : 'idle');
    badge.textContent = agent.busy ? 'Busy' : 'Idle';

    tooltip.appendChild(nameEl);
    if (agent.description) tooltip.appendChild(descEl);
    tooltip.appendChild(badge);

    document.body.appendChild(tooltip);

    // Position to the right of the avatar
    var avatarRect = e.currentTarget.getBoundingClientRect();
    var top = avatarRect.top + avatarRect.height / 2 - tooltip.offsetHeight / 2;

    // Keep tooltip within viewport vertically
    if (top < 8) top = 8;
    if (top + tooltip.offsetHeight > window.innerHeight - 8) {
        top = window.innerHeight - tooltip.offsetHeight - 8;
    }

    tooltip.style.left = (avatarRect.right + 10) + 'px';
    tooltip.style.top = top + 'px';

    _currentTooltip = tooltip;
}

/** Remove tooltip */
function hideTooltip() {
    if (_currentTooltip) {
        _currentTooltip.remove();
        _currentTooltip = null;
    }
}

/** Active bubble popup map: agentId -> { element, timer } */
var _activeBubbles = {};

/** Maximum characters to show in the bubble preview */
var _BUBBLE_MAX_CHARS = 140;

/** Auto-dismiss timeout in milliseconds */
var _BUBBLE_TIMEOUT = 7000;

/**
 * Truncate text to a maximum length at a word boundary.
 * Returns the truncated text with ellipsis if shortened.
 */
function _truncatePreview(text, maxLen) {
    if (!text) return '';
    text = text.trim();
    if (text.length <= maxLen) return text;

    // Try to break at the last space within the limit
    var truncated = text.substring(0, maxLen);
    var lastSpace = truncated.lastIndexOf(' ');
    if (lastSpace > maxLen * 0.6) {
        truncated = truncated.substring(0, lastSpace);
    }
    // Remove trailing punctuation before ellipsis
    truncated = truncated.replace(/[,;:.!?\\-]+$/, '');
    return truncated + '…';
}

/**
 * Dismiss a bubble popup for the given agent ID.
 * If no agentId is given, dismiss all bubbles.
 */
function dismissBubble(agentId) {
    if (agentId) {
        var entry = _activeBubbles[agentId];
        if (entry) {
            clearTimeout(entry.timer);
            entry.element.remove();
            delete _activeBubbles[agentId];
        }
    } else {
        Object.keys(_activeBubbles).forEach(function (id) {
            dismissBubble(id);
        });
    }
}

/**
 * Show a bubble popup next to an agent's avatar in the sidebar.
 * The bubble displays a truncated preview of the agent's final response.
 * Clicking the bubble navigates to the agent detail chat tab.
 */
function showBubblePopup(agentId, agentName, response, sessionId, externalUserId) {
    var avatar = document.querySelector(
        '#agent-sidebar .agent-avatar[data-agent-id="' + CSS.escape(agentId) + '"]'
    );
    if (!avatar) return;

    // Dismiss any existing bubble for this agent
    dismissBubble(agentId);

    var preview = _truncatePreview(response, _BUBBLE_MAX_CHARS);
    if (!preview) return;

    var bubble = document.createElement('div');
    bubble.className = 'agent-bubble-popup';
    if (sessionId) bubble.setAttribute('data-session-id', sessionId);
    if (externalUserId) bubble.setAttribute('data-external-user-id', externalUserId);

    // Arrow pointing left toward the avatar
    var arrow = document.createElement('div');
    arrow.className = 'agent-bubble-arrow';

    // Header with agent name
    var header = document.createElement('div');
    header.className = 'agent-bubble-header';
    header.textContent = agentName || agentId;

    // Body with truncated response
    var body = document.createElement('div');
    body.className = 'agent-bubble-body';
    body.textContent = preview;

    // Close button
    var closeBtn = document.createElement('button');
    closeBtn.className = 'agent-bubble-close';
    closeBtn.innerHTML = '×';
    closeBtn.setAttribute('aria-label', 'Dismiss');
    closeBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        dismissBubble(agentId);
    });

    bubble.appendChild(arrow);
    bubble.appendChild(header);
    bubble.appendChild(body);
    bubble.appendChild(closeBtn);

    // Click on bubble (not on close button) navigates to agent chat
    bubble.addEventListener('click', function (e) {
        if (e.target === closeBtn) return;
        dismissBubble(agentId);
        var bubbleSessionId = bubble.getAttribute('data-session-id');
        var externalUserId = bubble.getAttribute('data-external-user-id');
        if (bubbleSessionId && externalUserId !== 'web_test') {
            sessionStorage.setItem('evonic_last_session', bubbleSessionId);
            window.location = '/sessions';
        } else {
            _navigateToAgentChat(agentId);
        }
    });

    document.body.appendChild(bubble);

    // Position the bubble to the right of the avatar
    var avatarRect = avatar.getBoundingClientRect();
    var bubbleLeft = avatarRect.right + 12;
    var bubbleTop = avatarRect.top + avatarRect.height / 2 - 30;

    // Keep within viewport
    if (bubbleLeft + 280 > window.innerWidth - 12) {
        bubbleLeft = avatarRect.left - 280 - 12;
        bubble.classList.add('bubble-left');
    }
    if (bubbleTop < 8) bubbleTop = 8;
    if (bubbleTop + 80 > window.innerHeight - 8) {
        bubbleTop = window.innerHeight - 88;
    }

    bubble.style.left = bubbleLeft + 'px';
    bubble.style.top = bubbleTop + 'px';

    // Fade in
    requestAnimationFrame(function () {
        bubble.classList.add('bubble-visible');
    });

    // Auto-dismiss timer
    var timer = setTimeout(function () {
        dismissBubble(agentId);
    }, _BUBBLE_TIMEOUT);

    _activeBubbles[agentId] = { element: bubble, timer: timer };
}

/**
 * Global click handler: dismiss any visible bubble when user clicks outside it.
 */
document.addEventListener('click', function (e) {
    var clickedOnBubble = e.target.closest('.agent-bubble-popup');
    var clickedOnAvatar = e.target.closest('#agent-sidebar .agent-avatar');
    if (!clickedOnBubble && !clickedOnAvatar) {
        dismissBubble();
    }
});

/** Subscribe via RealtimeClient for real-time busy state updates and turn-complete notifications */
var _statusSSE = null;
function subscribeBusySSE() {
    if (typeof RealtimeClient === 'undefined') {
        // Fallback: use old EventSource if RealtimeClient not loaded
        try {
            _statusSSE = new EventSource('/api/agents/status/stream');
            _statusSSE.addEventListener('agent_busy_changed', function (e) {
                try {
                    var payload = JSON.parse(e.data);
                    var avatar = document.querySelector(
                        '#agent-sidebar .agent-avatar[data-agent-id="' + CSS.escape(payload.agent_id) + '"]'
                    );
                    if (avatar) {
                        avatar.setAttribute('data-busy', payload.busy ? 'true' : 'false');
                    }
                } catch (_) {}
            });
            _statusSSE.addEventListener('agent_turn_complete', function (e) {
                try {
                    var payload = JSON.parse(e.data);
                    if (window.location.pathname === '/agents/' + payload.agent_id) return;
                    _markUnread(payload.agent_id);
                    var av = document.querySelector('#agent-sidebar .agent-avatar[data-agent-id="' + CSS.escape(payload.agent_id) + '"]');
                    if (av) av.setAttribute('data-unread', 'true');
                    showBubblePopup(payload.agent_id, payload.agent_name, payload.response, payload.session_id, payload.external_user_id);
                } catch (_) {}
            });
            _statusSSE.addEventListener('error', function () {});
        } catch (_) {}
        return;
    }

    var rt = window._evRealtime = window._evRealtime || new RealtimeClient({
        channels: 'status'
    });
    rt.on('status', 'agent_busy_changed', function (payload) {
        var avatar = document.querySelector(
            '#agent-sidebar .agent-avatar[data-agent-id="' + CSS.escape(payload.agent_id) + '"]'
        );
        if (avatar) {
            avatar.setAttribute('data-busy', payload.busy ? 'true' : 'false');
        }
    });
    rt.on('status', 'agent_turn_complete', function (payload) {
        if (window.location.pathname === '/agents/' + payload.agent_id) return;
        _markUnread(payload.agent_id);
        var av = document.querySelector('#agent-sidebar .agent-avatar[data-agent-id="' + CSS.escape(payload.agent_id) + '"]');
        if (av) av.setAttribute('data-unread', 'true');
        showBubblePopup(payload.agent_id, payload.agent_name, payload.response, payload.session_id, payload.external_user_id);
    });
    rt.start();
}

// Close SSE/RealtimeClient on page unload to free HTTP connections during navigation
window.addEventListener('beforeunload', function () {
    if (_statusSSE instanceof EventSource) { _statusSSE.close(); _statusSSE = null; }
    if (window._evRealtime) { window._evRealtime.stop(); }
});

/** Toggle sidebar collapsed state */
function toggleSidebar() {
    var sidebar = document.getElementById('agent-sidebar');
    var burger = document.getElementById('sidebar-toggle-btn');
    if (!sidebar) return;

    var collapsed = sidebar.classList.toggle('collapsed');
    if (burger) {
        burger.classList.toggle('collapsed', collapsed);
    }
    try {
        localStorage.setItem('evonic-sidebar-collapsed', collapsed ? '1' : '0');
    } catch (_) {}
}

/** Apply saved sidebar state from localStorage */
function _applySidebarState() {
    var sidebar = document.getElementById('agent-sidebar');
    if (!sidebar) return;
    var burger = document.getElementById('sidebar-toggle-btn');

    var collapsed;
    try {
        var saved = localStorage.getItem('evonic-sidebar-collapsed');
        if (saved !== null) {
            collapsed = saved === '1';
        } else {
            // Default: collapsed on mobile, open on desktop
            collapsed = window.innerWidth <= 768;
        }
    } catch (_) {
        collapsed = window.innerWidth <= 768;
    }

    if (collapsed) {
        sidebar.classList.add('collapsed');
        if (burger) burger.classList.add('collapsed');
    }
}

// Update selected ring when browser navigates back/forward (soft-switch uses pushState)
window.addEventListener('popstate', _updateSelectedAvatar);

/** Initialize the sidebar */
function initSidebar() {
    var sidebar = document.getElementById('agent-sidebar');
    if (!sidebar) return;

    fetchSidebarAgents();
    subscribeBusySSE();
}
