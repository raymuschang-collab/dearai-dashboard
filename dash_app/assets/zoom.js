// Inline lightbox — clicking a `.zoomable` element opens a fullscreen
// overlay rendering the same image (or video iframe) at max viewport size.
// Click outside the media or press Escape to close. No new tabs, no Drive
// redirect.
//
// Each `.zoomable` element should expose:
//   data-src   — image URL (or video preview URL for `data-kind="video"`)
//   data-kind  — "image" (default) or "video"
//   data-href  — optional fallback URL (Drive view) shown as a small
//                "Open in Drive" link in the corner of the lightbox.
//
// Lightbox is created lazily on first click and reused thereafter.

(function () {
  function createLightbox() {
    if (document.getElementById('zoom-lightbox')) {
      return document.getElementById('zoom-lightbox');
    }
    const lb = document.createElement('div');
    lb.id = 'zoom-lightbox';
    lb.className = 'zoom-lightbox';
    lb.innerHTML = `
      <img class="zoom-img" alt="" />
      <iframe class="zoom-iframe" allow="autoplay" allowfullscreen></iframe>
      <a class="zoom-href" target="_blank" rel="noopener">Open in Drive ↗</a>
      <div class="zoom-hint">click outside · esc to close</div>
    `;
    lb.addEventListener('click', function (e) {
      // Close only if the click is on the overlay itself, not on media.
      if (e.target === lb) closeLightbox();
    });
    document.body.appendChild(lb);
    return lb;
  }

  function openLightbox(src, kind, href) {
    const lb = createLightbox();
    const img = lb.querySelector('.zoom-img');
    const iframe = lb.querySelector('.zoom-iframe');
    const hrefLink = lb.querySelector('.zoom-href');
    if (kind === 'video') {
      img.style.display = 'none';
      iframe.src = src;
      iframe.style.display = 'block';
    } else {
      iframe.src = '';
      iframe.style.display = 'none';
      img.src = src;
      img.style.display = 'block';
    }
    if (href) {
      hrefLink.href = href;
      hrefLink.style.display = 'inline-block';
    } else {
      hrefLink.style.display = 'none';
    }
    lb.classList.add('open');
  }

  function closeLightbox() {
    const lb = document.getElementById('zoom-lightbox');
    if (!lb) return;
    lb.classList.remove('open');
    // unload iframe to stop video playback
    const iframe = lb.querySelector('.zoom-iframe');
    if (iframe) iframe.src = '';
  }

  // Single delegated click listener — handles Dash re-renders for free.
  document.addEventListener('click', function (e) {
    // ignore clicks inside the lightbox itself
    if (e.target.closest('.zoom-lightbox')) return;
    const z = e.target.closest('.zoomable');
    if (!z) return;
    e.preventDefault();
    const src = z.dataset.src || (z.querySelector('img') && z.querySelector('img').src) || '';
    const kind = z.dataset.kind || 'image';
    const href = z.dataset.href || '';
    if (!src) return;
    openLightbox(src, kind, href);
  }, true);

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeLightbox();
  });
})();
