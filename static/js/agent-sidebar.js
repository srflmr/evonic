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
            window.location = '/agents/' + encodeURIComponent(agent.id) + '#chat';
        });

        avatar.addEventListener('mouseenter', function (e) {
            showTooltip(e, agent);
        });

        avatar.addEventListener('mouseleave', function () {
            hideTooltip();
        });

        sidebar.appendChild(avatar);
    });

    // Apply saved sidebar state after all elements (including burger) are rendered
    _applySidebarState();
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

/** Subscribe to SSE for real-time busy state updates */
function subscribeBusySSE() {
    try {
        var es = new EventSource('/api/agents/status/stream');
        es.addEventListener('agent_busy_changed', function (e) {
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
        es.addEventListener('error', function () {
            // EventSource will auto-reconnect; no action needed
        });
    } catch (_) {
        // EventSource not supported — polling fallback already active
    }
}

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

/** Initialize the sidebar */
function initSidebar() {
    var sidebar = document.getElementById('agent-sidebar');
    if (!sidebar) return;

    fetchSidebarAgents();
    subscribeBusySSE();
}
