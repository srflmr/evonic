/* ========================================
   Agent State Component (unified)
   Shared by agent_detail.html & sessions.html
   ======================================== */

var _stateAgentId = null;
var _stateSessionId = null;

function esc(str) {
    if (str === null || str === undefined) return '';
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

/**
 * Build HTML for loaded skill badges.
 * Returns an object: { html, hasBadges }
 */
function _buildSkillBadges(skills) {
    if (!skills || skills.length === 0) return { html: '', hasBadges: false, count: 0 };

    var maxVisible = 4;
    var visible = skills.slice(0, maxVisible);
    var hidden = skills.slice(maxVisible);
    var parts = [];

    for (var i = 0; i < visible.length; i++) {
        var s = visible[i];
        // Error detection: name === skill_id means manifest wasn't found
        var isError = (s.name === s.skill_id);
        var errorClass = isError ? ' border border-yellow-400 dark:border-yellow-500' : '';
        var tooltip = isError ? 'Skill error: failed to load metadata' : (s.tool_count ? s.tool_count + ' tools' : '');
        parts.push(
            '<span class="skill-badge inline-flex items-center px-2 py-0.5 rounded text-xs font-medium' +
            ' bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-300 ml-1 group' +
            errorClass +
            '" style="transition: opacity 0.15s ease"' +
            (tooltip ? ' title="' + esc(tooltip) + '"' : '') +
            ' data-skill-id="' + esc(s.skill_id) + '">' +
            esc(s.name) +
            '<button onclick="event.stopPropagation();_unloadSkill(\'' + esc(s.skill_id) + '\')"' +
            ' class="ml-1.5 inline-flex items-center justify-center w-4 h-4 rounded-full' +
            ' opacity-0 group-hover:opacity-100' +
            ' bg-gray-300 hover:bg-red-300 dark:bg-gray-600 dark:hover:bg-red-600' +
            ' text-gray-500 hover:text-red-600 dark:text-gray-400 dark:hover:text-red-300' +
            ' transition-all cursor-pointer"' +
            ' title="Unload skill">\u00d7</button>' +
            '</span>'
        );
    }

    // Truncation: "+N more" pill
    if (hidden.length > 0) {
        parts.push(
            '<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium' +
            ' bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-300 ml-1' +
            ' cursor-pointer" style="transition: opacity 0.15s ease"' +
            ' onclick="var p=this.parentElement;var all=p.querySelectorAll(\'.skill-badge-hidden\');' +
            'for(var i=0;i<all.length;i++)all[i].classList.toggle(\'hidden\');' +
            'this.textContent=all[0].classList.contains(\'hidden\')?\'+' + hidden.length + ' more\':\'Show less\'">' +
            '+' + hidden.length + ' more</span>'
        );
        // Add hidden badges
        for (var j = 0; j < hidden.length; j++) {
            var hs = hidden[j];
            var hsError = (hs.name === hs.skill_id);
            var hsErrorClass = hsError ? ' border border-yellow-400 dark:border-yellow-500' : '';
            var hsTooltip = hsError ? 'Skill error: failed to load metadata' : (hs.tool_count ? hs.tool_count + ' tools' : '');
            parts.push(
                '<span class="skill-badge-hidden skill-badge hidden inline-flex items-center px-2 py-0.5 rounded text-xs font-medium' +
                ' bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-300 ml-1 group' +
                hsErrorClass +
                '" style="transition: opacity 0.15s ease"' +
                (hsTooltip ? ' title="' + esc(hsTooltip) + '"' : '') +
                ' data-skill-id="' + esc(hs.skill_id) + '">' +
                esc(hs.name) +
                '<button onclick="event.stopPropagation();_unloadSkill(\'' + esc(hs.skill_id) + '\')"' +
                ' class="ml-1.5 inline-flex items-center justify-center w-4 h-4 rounded-full' +
                ' opacity-0 group-hover:opacity-100' +
                ' bg-gray-300 hover:bg-red-300 dark:bg-gray-600 dark:hover:bg-red-600' +
                ' text-gray-500 hover:text-red-600 dark:text-gray-400 dark:hover:text-red-300' +
                ' transition-all cursor-pointer"' +
                ' title="Unload skill">\u00d7</button>' +
                '</span>'
            );
        }
    }

    return { html: parts.join(''), hasBadges: true, count: skills.length };
}

/**
 * Core rendering logic (no debounce).
 */
function _renderAgentStateCore(containerIds, data) {
    var empty = '<p class="text-sm text-gray-400 dark:text-gray-500 italic">No state yet.</p>';
    var hasAnyState = data.focus ||
        data.active_model ||
        (data.states && Object.keys(data.states).length > 0);
    if (!hasAnyState) {
        (Array.isArray(containerIds) ? containerIds : [containerIds]).forEach(function(id) {
            var el = document.getElementById(id);
            if (el) el.innerHTML = empty;
        });
        return;
    }

    // Build status cards row (Focus + Model + Skills)
    var cards = '';

    // Focus badge
    if (data.focus) {
        var reasonText = data.focus_reason ? ' \u2014 ' + esc(data.focus_reason) : '';
        cards += '<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300 ml-1">Focus' + reasonText + '</span>';
    }

    // Active model badge
    if (data.active_model) {
        var am = data.active_model;
        if (am.is_fallback) {
            cards += '<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300 ml-1" title="Using fallback model due to primary failure">Model: ' + esc(am.name) + ' <span class="ml-1 text-[10px] opacity-75">(fallback)</span>' +
                '<button onclick="event.stopPropagation();_resetActiveModel()" class="ml-1.5 inline-flex items-center justify-center w-4 h-4 rounded-full bg-amber-200 hover:bg-red-200 dark:bg-amber-700 dark:hover:bg-red-700 text-amber-600 hover:text-red-600 dark:text-amber-300 dark:hover:text-red-300 transition-colors cursor-pointer" title="Reset to primary model">\u00d7</button>' +
                '</span>';
        } else {
            cards += '<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300 ml-1">Model: ' + esc(am.name) + '</span>';
        }
    }

    // Raw JSON for debug
    var rawJson = JSON.stringify(data, null, 2);

    var html = '<div class="space-y-2 text-sm">';

    // Status cards row
    html += '<div class="flex flex-wrap gap-1">' + cards + '</div>';

    // Plugin states section
    if (data.states && Object.keys(data.states).length > 0) {
        html += '<div class="border-t border-gray-100 dark:border-gray-700 pt-2"><div class="text-gray-500 dark:text-gray-400 font-medium mb-1 text-xs uppercase tracking-wide">Plugin States</div><ul class="space-y-1">';
        var stateEntries = Object.entries(data.states);
        for (var si = 0; si < stateEntries.length; si++) {
            var ns = stateEntries[si][0];
            var slot = stateEntries[si][1];
            var stateVal = slot.state || 'unknown';
            var dataStr = slot.data ? JSON.stringify(slot.data) : '';
            html += '<li><div class="flex items-center gap-1"><span class="font-medium text-xs text-gray-700 dark:text-gray-200">' + esc(ns) + ':</span><code class="text-xs bg-gray-100 dark:bg-gray-700 px-1.5 py-0.5 rounded">' + esc(stateVal) + '</code></div>';
            if (dataStr) {
                html += '<div class="text-[10px] text-gray-400 dark:text-gray-500 mt-0.5 font-mono break-all">' + esc(dataStr) + '</div>';
            }
            html += '</li>';
        }
        html += '</ul></div>';
    }

    // Debug: raw JSON toggle
    html += '<div class="mt-2 pt-2 border-t border-gray-100 dark:border-gray-700">';
    html += '<div class="flex justify-end">';
    html += '<button onclick="this.parentElement.nextElementSibling.classList.toggle(\'hidden\');this.textContent=this.parentElement.nextElementSibling.classList.contains(\'hidden\')?\'Show Raw JSON\':\'Hide Raw JSON\'" class="text-[10px] text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 underline cursor-pointer">Show Raw JSON</button>';
    html += '</div>';
    html += '<pre class="hidden mt-1 rounded p-2 text-[10px] font-mono overflow-x-auto whitespace-pre-wrap break-all max-h-40 overflow-y-auto">' + esc(rawJson) + '</pre>';
    html += '</div>';

    html += '</div>';

    (Array.isArray(containerIds) ? containerIds : [containerIds]).forEach(function(id) {
        var el = document.getElementById(id);
        if (el) el.innerHTML = html;
    });
}

/**
 * Public entry point. Fetches state API and renders.
 * Pass `preloadedData` to render from an already-fetched state payload
 * (avoids a duplicate /chat/state request when the caller has one).
 */
async function renderAgentState(agentId, userId, containerIds, sessionId, preloadedData) {
    if (!agentId) return;
    _stateAgentId = agentId;
    _stateSessionId = sessionId || null;
    try {
        var data = preloadedData;
        if (!data) {
            var url = '/api/agents/' + agentId + '/chat/state?user_id=' + encodeURIComponent(userId || 'web_test');
            if (sessionId) url += '&session_id=' + encodeURIComponent(sessionId);
            var res = await fetch(url);
            if (!res.ok) { console.warn('[AgentState] API error:', res.status, res.statusText); return; }
            data = await res.json();
        }
        _renderAgentStateCore(containerIds, data);
    } catch (e) { console.error('[AgentState] error:', e); }
}

function clearAgentState(containerIds) {
    var empty = '<p class="text-sm text-gray-400 dark:text-gray-500 italic">No state yet.</p>';
    (Array.isArray(containerIds) ? containerIds : [containerIds]).forEach(function(id) {
        var el = document.getElementById(id);
        if (el) el.innerHTML = empty;
    });
}

function _resetActiveModel() {
    if (!_stateAgentId) { console.warn('[AgentState] No agent ID for reset'); return; }
    fetch('/api/agents/' + _stateAgentId + '/model/reset', { method: 'POST' })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.success) {
                document.dispatchEvent(new CustomEvent('evonic:agent-state-changed'));
            } else {
                console.warn('[AgentState] Reset failed:', data.error || data.result);
            }
        })
        .catch(function(e) { console.error('[AgentState] Reset error:', e); });
}

function _unloadSkill(skillId) {
    if (!_stateAgentId || !_stateSessionId) {
        console.warn('[AgentState] No agent/session ID for skill unload');
        return;
    }
    var url = '/api/agents/' + _stateAgentId + '/skills/' + encodeURIComponent(skillId) + '/unload?session_id=' + encodeURIComponent(_stateSessionId);
    fetch(url, { method: 'POST' })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.success) {
                document.dispatchEvent(new CustomEvent('evonic:agent-state-changed'));
            } else {
                console.warn('[AgentState] Skill unload failed:', data.error || data.result);
            }
        })
        .catch(function(e) { console.error('[AgentState] Skill unload error:', e); });
}
