(function () {
  function parseGallery(value) {
    if (!value) {
      return [];
    }
    try {
      var parsed = JSON.parse(value);
      return Array.isArray(parsed) ? parsed.filter(Boolean) : [];
    } catch (err) {
      console.warn('Unable to parse printer image gallery', err);
      return [];
    }
  }

  function uniqueSources(initial, gallery) {
    var seen = new Set();
    var sources = [];
    if (initial && !seen.has(initial)) {
      seen.add(initial);
      sources.push(initial);
    }
    gallery.forEach(function (url) {
      if (url && !seen.has(url)) {
        seen.add(url);
        sources.push(url);
      }
    });
    return sources;
  }

  function markBroken(img) {
    if (!img) return;
    var container = img.closest('.product-card__media');
    if (!container || container.dataset.state === 'broken') {
      return;
    }
    container.dataset.state = 'broken';
    container.classList.add('product-card__media--broken');
    img.setAttribute('aria-hidden', 'true');
    var label = document.createElement('span');
    label.className = 'product-card__media__fallback-label';
    label.textContent = 'Image unavailable';
    container.appendChild(label);
  }

  function attachHandlers(img) {
    var gallery = parseGallery(img.dataset.gallery);
    var fallback = img.dataset.fallback || '';
    var sources = uniqueSources(img.getAttribute('src'), gallery);
    var index = 0;
    var fallbackUsed = false;

    function tryNext() {
      if (index < sources.length - 1) {
        index += 1;
        var nextSrc = sources[index];
        if (img.getAttribute('src') !== nextSrc) {
          img.setAttribute('src', nextSrc);
        }
        return;
      }
      if (!fallbackUsed && fallback) {
        fallbackUsed = true;
        if (img.getAttribute('src') !== fallback) {
          img.setAttribute('src', fallback);
        }
        return;
      }
      markBroken(img);
      img.removeEventListener('error', onError);
    }

    function onError() {
      tryNext();
    }

    img.addEventListener('error', onError);

    if (!img.getAttribute('src') && sources.length > 0) {
      img.setAttribute('src', sources[0]);
    }
  }

  function init() {
    document.querySelectorAll('.product-card__media img').forEach(function (img) {
      if (img.dataset.imageRecoveryAttached === '1') {
        return;
      }
      img.dataset.imageRecoveryAttached = '1';
      attachHandlers(img);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
