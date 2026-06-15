/**
 * lightbox.js — Full-screen lightbox modal for chat images.
 *
 * Provides:
 *   Lightbox.open(imageUrls, startIndex)  — open with explicit URL list
 *   Lightbox.openFromImage(imgElement)    — open from a clicked <img>, auto-collects chat images
 *   Lightbox.close()                      — close the lightbox
 *   Lightbox.isOpen()                     — boolean
 *
 * Features:
 *   - Keyboard navigation (Left/Right arrows, Escape to close)
 *   - Click outside image to close
 *   - Touch swipe support on mobile
 *   - Image counter (e.g. "3 / 7")
 *   - Lazy-loads images only when they become visible
 *   - Accessible: ARIA labels, focus-aware
 */

const Lightbox = (function() {
    let _images = [];
    let _currentIndex = 0;
    let _$overlay = null;
    let _$img = null;
    let _$prevBtn = null;
    let _$nextBtn = null;
    let _$counter = null;
    let _$downloadBtn = null;
    let _$filename = null;
    let _isOpen = false;
    let _prevFocusedEl = null;
    let _boundKeyHandler = null;
    let _touchStartX = 0;
    let _touchStartY = 0;

    /**
     * Collect all chat images from the DOM, excluding avatars and lightbox-internal images.
     * @returns {{ urls: string[], index: number }} or null if the clicked element is not found
     */
    function _collectChatImages($clickedImg) {
        // Find the chat container — try common selectors, then fall back to document
        const $chatContainer = $clickedImg.closest('#chat-messages, .chat-messages, [data-chat-container]');
        const $scope = $chatContainer.length ? $chatContainer : $(document.body);
        const images = [];
        let startIndex = -1;

        // Collect all visible images in chat that aren't avatars or lightbox internal
        $scope.find('img').each(function() {
            const $this = $(this);
            // Skip avatar images (rounded-full is the avatar class)
            if ($this.hasClass('rounded-full')) return;
            // Skip lightbox internal images
            if ($this.closest('.ev-lightbox-overlay').length) return;
            // Skip images without a real src
            const src = $this.attr('src');
            if (!src) return;
            // Skip tiny icons, data URIs that are likely icons
            if (src.startsWith('data:image/svg+xml')) return;

            images.push(src);
            if (this === $clickedImg[0]) {
                startIndex = images.length - 1;
            }
        });

        if (!images.length) return null;
        if (startIndex < 0) startIndex = 0;
        return { urls: images, index: startIndex };
    }

    function _buildDOM() {
        // Overlay backdrop — use inline CSS for z-index & bg opacity (Tailwind
        // compiled CSS may not include arbitrary-value or opacity-modifier classes)
        _$overlay = $('<div>')
            .addClass('ev-lightbox-overlay fixed inset-0 hidden flex flex-col items-center justify-center')
            .css({ zIndex: 9999, backgroundColor: 'rgba(0,0,0,0.9)' });

        // Helper: build a nav button (close, prev, next) with inline styling
        function _navBtn(cls, label, svgHtml, onClick) {
            const sizes = {
                close: { w: 48, h: 48, top: '16px', right: '16px', left: 'auto' },
                prev:  { w: 40, h: 40, top: '50%', right: 'auto', left: '8px' },
                next:  { w: 40, h: 40, top: '50%', right: '8px', left: 'auto' },
            };
            const s = sizes[cls] || sizes.close;
            const $btn = $('<button>')
                .addClass('ev-lightbox-' + cls + ' rounded-full text-white cursor-pointer duration-200')
                .css({
                    position: 'absolute',
                    top: s.top,
                    right: s.right,
                    left: s.left,
                    zIndex: 20,
                    width: s.w + 'px',
                    height: s.h + 'px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    backgroundColor: 'rgba(255,255,255,0.1)',
                    border: 'none',
                    transform: cls !== 'close' ? 'translateY(-50%)' : 'none',
                    transition: 'background-color 200ms ease',
                    outline: 'none',
                })
                .attr('aria-label', label)
                .attr('type', 'button')
                .html(svgHtml)
                .on('click', onClick)
                .on('mouseenter', function() { $(this).css('backgroundColor', 'rgba(255,255,255,0.2)'); })
                .on('mouseleave', function() { $(this).css('backgroundColor', 'rgba(255,255,255,0.1)'); })
                .on('focus', function() { $(this).css({ outline: '2px solid rgba(255,255,255,0.7)', outlineOffset: '2px' }); })
                .on('blur', function() { $(this).css({ outline: 'none', outlineOffset: '0' }); });
            return $btn;
        }

        // Close button (X)
        const $closeBtn = _navBtn('close', 'Close lightbox',
            '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>',
            function() { Lightbox.close(); });

        // Previous button
        _$prevBtn = _navBtn('prev', 'Previous image',
            '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>',
            function(e) { e.stopPropagation(); Lightbox._navigate(-1); });

        // Next button
        _$nextBtn = _navBtn('next', 'Next image',
            '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>',
            function(e) { e.stopPropagation(); Lightbox._navigate(1); });

        // Image container (position-relative so download button aligns to image area)
        const _$imgContainer = $('<div>')
            .css({ position: 'relative', display: 'inline-block' });

        // Image element (lazy-loaded — src set when showing)
        _$img = $('<img>')
            .addClass('ev-lightbox-img max-h-[90vh] select-none')
            .css({ maxWidth: '90vw', objectFit: 'contain' })
            .attr('draggable', 'false')
            .attr('alt', '')
            .on('load', function() {
                // Fade in effect
                $(this).css('opacity', '1');
            });

        _$imgContainer.append(_$img);

        // Download button (top-right of image area, matches chat thumbnail style)
        _$downloadBtn = $('<button>')
            .addClass('w-9 h-9 rounded-md text-white cursor-pointer')
            .css({
                position: 'absolute',
                top: '6px',
                left: '6px',
                zIndex: 20,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                opacity: 0,
                transition: 'opacity 200ms ease',
                backgroundColor: 'rgba(0,0,0,0.4)',
                border: 'none',
            })
            .attr('title', 'Download image')
            .attr('aria-label', 'Download image')
            .attr('type', 'button')
            .html('<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>')
            .on('click', async function(e) {
                e.preventDefault();
                e.stopPropagation();
                const url = _images[_currentIndex];
                try {
                    const response = await fetch(url);
                    const blob = await response.blob();
                    const blobUrl = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = blobUrl;
                    a.download = url.split('/').pop().split('?')[0] || 'image';
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    URL.revokeObjectURL(blobUrl);
                } catch (err) {
                    window.open(url, '_blank');
                }
            });

        _$imgContainer.append(_$downloadBtn);

        // Hover on image container: show download button
        _$imgContainer.on('mouseenter', function() { _$downloadBtn.css('opacity', 1); });
        _$imgContainer.on('mouseleave', function() { _$downloadBtn.css('opacity', 0); });

        // Download button hover: darker background
        _$downloadBtn.on('mouseenter', function() { $(this).css('backgroundColor', 'rgba(0,0,0,0.6)'); });
        _$downloadBtn.on('mouseleave', function() { $(this).css('backgroundColor', 'rgba(0,0,0,0.4)'); });

        // Focus: show button with ring
        _$downloadBtn.on('focus', function() {
            $(this).css({ opacity: 1, outline: '2px solid rgba(255,255,255,0.7)', outlineOffset: '2px' });
        });
        _$downloadBtn.on('blur', function() {
            $(this).css({ outline: 'none', outlineOffset: '0' });
            if (!_$imgContainer.is(':hover')) _$downloadBtn.css('opacity', 0);
        });

        // Counter indicator — use inline CSS for fractional positioning & opacity
        _$counter = $('<span>')
            .addClass('ev-lightbox-counter text-sm font-mono backdrop-blur-sm px-3 py-1 rounded-full')
            .css({
                position: 'absolute',
                bottom: '16px',
                left: '50%',
                transform: 'translateX(-50%)',
                zIndex: 20,
                color: 'rgba(255,255,255,0.8)',
                backgroundColor: 'rgba(0,0,0,0.5)',
                whiteSpace: 'nowrap',
            });

        // Hide counter if only 1 image
        _$counter.attr('data-count', '0');

        // Filename label — positioned above the counter, inline pill style
        _$filename = $('<span>')
            .addClass('ev-lightbox-filename text-xs font-mono px-2 py-0.5 rounded')
            .css({
                position: 'absolute',
                bottom: '44px',
                left: '50%',
                transform: 'translateX(-50%)',
                zIndex: 20,
                color: '#fff',
                backgroundColor: 'rgba(0,0,0,0.5)',
                whiteSpace: 'nowrap',
            });

        // Click on backdrop to close
        _$overlay.on('click', function(e) {
            if (e.target === _$overlay[0]) {
                Lightbox.close();
            }
        });

        // Prevent clicks on the image from closing
        _$img.on('click', function(e) {
            e.stopPropagation();
        });

        // Touch swipe support
        _$overlay.on('touchstart', function(e) {
            _touchStartX = e.originalEvent.touches[0].clientX;
            _touchStartY = e.originalEvent.touches[0].clientY;
        });

        _$overlay.on('touchend', function(e) {
            const touchEndX = e.originalEvent.changedTouches[0].clientX;
            const touchEndY = e.originalEvent.changedTouches[0].clientY;
            const diffX = _touchStartX - touchEndX;
            const diffY = _touchStartY - touchEndY;

            // Only swipe if horizontal movement dominates
            if (Math.abs(diffX) > Math.abs(diffY) && Math.abs(diffX) > 50) {
                Lightbox._navigate(diffX > 0 ? 1 : -1);
            }
        });

        // Keyboard handler
        _boundKeyHandler = function(e) {
            if (!_isOpen) return;
            switch (e.key) {
                case 'Escape':
                    e.preventDefault();
                    Lightbox.close();
                    break;
                case 'ArrowLeft':
                    e.preventDefault();
                    Lightbox._navigate(-1);
                    break;
                case 'ArrowRight':
                    e.preventDefault();
                    Lightbox._navigate(1);
                    break;
                case 'Tab':
                    e.preventDefault();
                    _trapFocus(e.shiftKey);
                    break;
            }
        };

        // Focus trap: cycle between close, download, prev, next buttons
        function _trapFocus(shiftKey) {
            const focusable = [];
            const $closeBtn = _$overlay.find('.ev-lightbox-close');
            if ($closeBtn.length) focusable.push($closeBtn[0]);
            if (_$downloadBtn && _$downloadBtn.length) focusable.push(_$downloadBtn[0]);
            if (_images.length > 1) {
                if (_$prevBtn && _$prevBtn.length) focusable.push(_$prevBtn[0]);
                if (_$nextBtn && _$nextBtn.length) focusable.push(_$nextBtn[0]);
            }
            if (!focusable.length) return;
            const currentIndex = focusable.indexOf(document.activeElement);
            let nextIndex;
            if (shiftKey) {
                nextIndex = currentIndex <= 0 ? focusable.length - 1 : currentIndex - 1;
            } else {
                nextIndex = currentIndex >= focusable.length - 1 ? 0 : currentIndex + 1;
            }
            focusable[nextIndex].focus();
        }

        _$overlay.append($closeBtn, _$prevBtn, _$nextBtn, _$imgContainer, _$filename, _$counter);
        $('body').append(_$overlay);
    }

    function _showImage(index) {
        _currentIndex = index;
        _$img.css('opacity', '0');
        // Lazy-load: set src only when the image becomes visible
        _$img.attr('src', _images[index]);
        _$counter.text((index + 1) + ' / ' + _images.length);
        // Extract and display filename
        var filename = _images[index].split('/').pop().split('?')[0] || 'image';
        _$filename.text(filename);
    }

    function _updateNavigation() {
        // The prev/next buttons carry an inline `display: flex` (set in _navBtn),
        // which overrides the `hidden` class — so toggle their inline display
        // directly. Otherwise the buttons stay visible (but inert, since _navigate
        // early-returns) on a single-image lightbox, looking broken.
        const multi = _images.length > 1;
        _$prevBtn.css('display', multi ? 'flex' : 'none');
        _$nextBtn.css('display', multi ? 'flex' : 'none');
        if (multi) _$counter.removeClass('hidden');
        else _$counter.addClass('hidden');
    }

    // Public API
    return {
        /**
         * Open the lightbox with an explicit list of image URLs.
         * @param {string[]} imageUrls
         * @param {number} [startIndex=0]
         */
        open: function(imageUrls, startIndex) {
            _images = (imageUrls && imageUrls.length) ? imageUrls.slice() : [];
            if (!_images.length) return;

            _currentIndex = Math.max(0, Math.min(startIndex || 0, _images.length - 1));

            // Save the currently focused element to restore on close
            _prevFocusedEl = document.activeElement;

            if (!_$overlay) {
                _buildDOM();
            }

            $(document).on('keydown', _boundKeyHandler);

            _showImage(_currentIndex);
            _updateNavigation();
            _$overlay.removeClass('hidden');
            _isOpen = true;
            document.body.style.overflow = 'hidden';

            // Focus the close button first for accessibility
            _$overlay.find('.ev-lightbox-close').focus();
        },

        /**
         * Open the lightbox from a clicked <img> element.
         * Automatically collects all chat images for navigation.
         * @param {HTMLImageElement} imgElement
         */
        openFromImage: function(imgElement) {
            const $clickedImg = $(imgElement);
            const collected = _collectChatImages($clickedImg);
            if (!collected) return;
            Lightbox.open(collected.urls, collected.index);
        },

        /**
         * Close the lightbox.
         */
        close: function() {
            if (!_isOpen) return;
            $(document).off('keydown', _boundKeyHandler);
            _$overlay.addClass('hidden');
            _isOpen = false;
            document.body.style.overflow = '';
            // Clear the src to stop any in-flight loads
            _$img.attr('src', '');
            _images = [];
            // Restore focus to the previously focused element
            if (_prevFocusedEl && typeof _prevFocusedEl.focus === 'function') {
                try { _prevFocusedEl.focus(); } catch(e) {}
            }
            _prevFocusedEl = null;
        },

        /**
         * @returns {boolean}
         */
        isOpen: function() {
            return _isOpen;
        },

        /**
         * Navigate by direction. Exposed for button click handlers.
         * @param {number} direction -1 for previous, +1 for next
         */
        _navigate: function(direction) {
            if (_images.length <= 1) return;
            var newIndex = _currentIndex + direction;
            if (newIndex < 0) newIndex = _images.length - 1;
            if (newIndex >= _images.length) newIndex = 0;
            _showImage(newIndex);
        }
    };
})();

export { Lightbox };
