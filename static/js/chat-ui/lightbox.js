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
        // Overlay backdrop
        _$overlay = $('<div>')
            .addClass('ev-lightbox-overlay fixed inset-0 z-[9999] bg-black/90 hidden flex flex-col items-center justify-center');

        // Close button (X)
        const $closeBtn = $('<button>')
            .addClass('ev-lightbox-close absolute top-4 right-4 z-20 w-12 h-12 flex items-center justify-center rounded-full bg-white/10 hover:bg-white/20 text-white cursor-pointer transition-colors duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-white/70')
            .attr('aria-label', 'Close lightbox')
            .attr('type', 'button')
            .html('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>')
            .on('click', function() { Lightbox.close(); });

        // Previous button
        _$prevBtn = $('<button>')
            .addClass('ev-lightbox-prev absolute left-2 md:left-4 top-1/2 -translate-y-1/2 z-20 w-10 h-10 md:w-12 md:h-12 flex items-center justify-center rounded-full bg-white/10 hover:bg-white/20 text-white cursor-pointer transition-colors duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-white/70')
            .attr('aria-label', 'Previous image')
            .attr('type', 'button')
            .html('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>')
            .on('click', function(e) { e.stopPropagation(); Lightbox._navigate(-1); });

        // Next button
        _$nextBtn = $('<button>')
            .addClass('ev-lightbox-next absolute right-2 md:right-4 top-1/2 -translate-y-1/2 z-20 w-10 h-10 md:w-12 md:h-12 flex items-center justify-center rounded-full bg-white/10 hover:bg-white/20 text-white cursor-pointer transition-colors duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-white/70')
            .attr('aria-label', 'Next image')
            .attr('type', 'button')
            .html('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>')
            .on('click', function(e) { e.stopPropagation(); Lightbox._navigate(1); });

        // Image element (lazy-loaded — src set when showing)
        _$img = $('<img>')
            .addClass('ev-lightbox-img max-w-[90vw] max-h-[90vh] object-contain select-none')
            .attr('draggable', 'false')
            .attr('alt', '')
            .on('load', function() {
                // Fade in effect
                $(this).css('opacity', '1');
            });

        // Counter indicator
        _$counter = $('<span>')
            .addClass('ev-lightbox-counter absolute bottom-4 left-1/2 -translate-x-1/2 z-20 text-white/80 text-sm font-mono bg-black/50 backdrop-blur-sm px-3 py-1 rounded-full');

        // Hide counter if only 1 image
        _$counter.attr('data-count', '0');

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

        // Focus trap: cycle between close, prev, next buttons
        function _trapFocus(shiftKey) {
            const focusable = [];
            const $closeBtn = _$overlay.find('.ev-lightbox-close');
            if ($closeBtn.length) focusable.push($closeBtn[0]);
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

        _$overlay.append($closeBtn, _$prevBtn, _$nextBtn, _$img, _$counter);
        $('body').append(_$overlay);
    }

    function _showImage(index) {
        _currentIndex = index;
        _$img.css('opacity', '0');
        // Lazy-load: set src only when the image becomes visible
        _$img.attr('src', _images[index]);
        _$counter.text((index + 1) + ' / ' + _images.length);
    }

    function _updateNavigation() {
        if (_images.length <= 1) {
            _$prevBtn.addClass('hidden');
            _$nextBtn.addClass('hidden');
            _$counter.addClass('hidden');
        } else {
            _$prevBtn.removeClass('hidden');
            _$nextBtn.removeClass('hidden');
            _$counter.removeClass('hidden');
        }
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
