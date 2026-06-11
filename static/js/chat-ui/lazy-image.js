/**
 * lazy-image.js — Viewport-based lazy loading for chat images.
 *
 * Replaces eager src loading with IntersectionObserver-driven lazy loading:
 *   1. Images start with data-src (not src) and a CSS skeleton shimmer placeholder
 *   2. When the image scrolls within 300px of the viewport, swap data-src → src
 *   3. On load: fade-in transition + remove skeleton
 *
 * API:
 *   initLazyImages($scrollContainer)  — one-time setup, scans existing [data-src] images
 *   setupImageForLazy($img)           — prepare a single new <img> for lazy loading
 */

let _observer = null;
let _observerRoot = null;

/**
 * Walk up from the image to locate the scrollable chat container.
 * Falls back to document.body if no scrollable ancestor found.
 */
function _findScrollContainer($img) {
    const $c = $img.closest('#chat-messages, .chat-messages, [data-chat-container]');
    return $c.length ? $c : $(document.body);
}

/**
 * Creates (or reuses) a single IntersectionObserver for the given scroll container.
 * @param {jQuery} $scrollContainer — chat messages element (overflow-y: auto)
 * @returns {IntersectionObserver}
 */
function _getObserver($scrollContainer) {
    const root = $scrollContainer[0];
    if (_observer && _observerRoot === root) return _observer;

    // Dispose previous observer if container changed
    if (_observer) {
        _observer.disconnect();
        _observer = null;
        _observerRoot = null;
    }

    _observer = new IntersectionObserver((entries) => {
        for (const entry of entries) {
            if (!entry.isIntersecting) continue;

            const img = entry.target;
            const $img = $(img);
            const src = $img.attr('data-src');
            if (!src) {
                _observer.unobserve(img);
                continue;
            }

            // Remove from observer — single-shot
            _observer.unobserve(img);

            // Set src to trigger load
            $img.attr('src', src);

            // Handle cached (already-loaded) images
            if (img.complete) {
                _onImageReady($img);
            } else {
                $img.one('load', function () { _onImageReady($(this)); });
                $img.one('error', function () { _onImageError($(this)); });
            }
        }
    }, {
        root,
        rootMargin: '300px',
        threshold: 0,
    });

    _observerRoot = root;
    return _observer;
}

/**
 * Called when an image has successfully loaded.
 * Fades in the image and removes the skeleton placeholder.
 */
function _onImageReady($img) {
    const skeleton = $img[0]._lazySkeleton;
    if (skeleton) {
        $(skeleton).remove();
        delete $img[0]._lazySkeleton;
    }
    $img.removeClass('chat-img-loading')
        .css({ opacity: '1', transition: 'opacity 0.35s ease' });
}

/**
 * Called when an image fails to load.
 * Removes the skeleton (image stays hidden).
 */
function _onImageError($img) {
    const skeleton = $img[0]._lazySkeleton;
    if (skeleton) {
        $(skeleton).remove();
        delete $img[0]._lazySkeleton;
    }
    $img.removeClass('chat-img-loading')
        .css({ opacity: '1' });
}

/**
 * Insert a skeleton shimmer placeholder inside the image's wrapper div,
 * resize to match the image's constrained dimensions, and register with
 * the IntersectionObserver.
 *
 * Precondition: the image must already be wrapped by _wrapImageWithDownload()
 * (i.e. $img.parent() is the positioned wrapper div).
 *
 * @param {jQuery} $img — a jQuery-wrapped <img> element with data-src set
 * @param {jQuery} $scrollContainer — the scrollable chat container
 */
export function setupImageForLazy($img, $scrollContainer) {
    if (!$img.length) return;
    const imageUrl = $img.attr('data-src');
    if (!imageUrl) return;

    if (!$scrollContainer) $scrollContainer = _findScrollContainer($img);

    // Ensure the image is hidden until loaded
    $img.addClass('chat-img-loading').css('opacity', '0');

    // Build skeleton — use image's computed max dimensions as skeleton size
    const $wrapper = $img.parent();
    const skeleton = $('<div>')
        .addClass('chat-img-skeleton')
        .css({
            width: $img.css('max-width') || '400px',
            height: $img.css('max-height') || '300px',
        });

    // Insert skeleton as first child of the wrapper so the download button
    // (appended later by _wrapImageWithDownload) still renders on top.
    $wrapper.prepend(skeleton);

    // Stash skeleton reference on the DOM element for cleanup
    $img[0]._lazySkeleton = skeleton[0];

    const observer = _getObserver($scrollContainer);
    observer.observe($img[0]);
}

/**
 * Scan an entire container for existing img[data-src] elements and
 * register them with the observer. Use this as a catch-all after
 * HTML-rendered content (markdown) is injected.
 *
 * @param {jQuery} $scrollContainer — the scrollable chat container
 * @param {jQuery} [$scope] — optional scoped root to scan (default: $scrollContainer)
 */
export function initLazyImages($scrollContainer, $scope) {
    const $root = $scope || $scrollContainer;
    if (!$scrollContainer) $scrollContainer = _findScrollContainer($root);
    $root.find('img[data-src]').each(function () {
        // Skip if already being observed or already loaded
        if (this._lazyObserved) return;
        this._lazyObserved = true;
        setupImageForLazy($(this), $scrollContainer);
    });
}

/**
 * Create a new <img> element pre-configured for lazy loading.
 * The caller is responsible for appending it and calling _wrapImageWithDownload().
 *
 * @param {string} imageUrl  — the image URL to load lazily
 * @returns {jQuery}  a jQuery-wrapped <img> with data-src (not src)
 */
export function createLazyImage(imageUrl) {
    return $('<img>')
        .attr('data-src', imageUrl)
        .attr('alt', 'Attached image');
}

/**
 * Reset the global observer (e.g. when chat is cleared).
 */
export function disposeLazyObserver() {
    if (_observer) {
        _observer.disconnect();
        _observer = null;
        _observerRoot = null;
    }
}

/**
 * Public: force-observe an already-sourced img (e.g. after Markdown html() insertion).
 * Moves src → data-src then calls setupImageForLazy.
 *
 * @param {jQuery} $img — an <img> with src already set
 * @param {jQuery} $scrollContainer
 */
export function retrofitImageForLazy($img, $scrollContainer) {
    const src = $img.attr('src');
    if (!src || src.startsWith('data:')) return;
    $img.removeAttr('src').attr('data-src', src);
    setupImageForLazy($img, $scrollContainer || _findScrollContainer($img));
}
