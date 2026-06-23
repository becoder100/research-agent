(function () {
  'use strict';

  function injectStyles() {
    if (document.getElementById('ra-styles')) return;
    var s = document.createElement('style');
    s.id = 'ra-styles';
    s.textContent =
      '#ra-brand{text-align:center;padding:22px 0 4px}' +
      '#ra-brand svg{display:block;margin:0 auto 10px}' +
      '#ra-brand .ra-name{color:#fff;font:700 22px/1.2 Arial,sans-serif;letter-spacing:.4px}' +
      '#ra-brand .ra-tag{color:#64748b;font:12px/1.5 Arial,sans-serif;margin-top:5px}' +
      '#ra-reg-link{text-align:center;margin-top:14px;font:13px Arial,sans-serif;color:#94a3b8}' +
      '#ra-reg-link a{color:#38bdf8;text-decoration:none;font-weight:500}' +
      '#ra-reg-link a:hover{text-decoration:underline}';
    document.head.appendChild(s);
  }

  function tryEnhance() {
    var form = document.querySelector('form');
    if (!form) return;
    var submitBtn = form.querySelector('button[type="submit"]');
    if (!submitBtn) return;
    if (document.getElementById('ra-brand')) return; // already done

    injectStyles();

    // ── Logo + app name above the login card ──────────────────────────────
    var brand = document.createElement('div');
    brand.id = 'ra-brand';
    brand.innerHTML =
      '<svg width="56" height="56" viewBox="0 0 120 120" xmlns="http://www.w3.org/2000/svg">' +
        '<rect width="120" height="120" rx="20" fill="#0f172a"/>' +
        '<circle cx="50" cy="50" r="26" fill="none" stroke="#38bdf8" stroke-width="5.5"/>' +
        '<line x1="68" y1="68" x2="90" y2="90" stroke="#38bdf8" stroke-width="5.5" stroke-linecap="round"/>' +
        '<circle cx="50" cy="40" r="4" fill="#38bdf8"/>' +
        '<circle cx="38" cy="50" r="4" fill="#38bdf8"/>' +
        '<circle cx="50" cy="60" r="4" fill="#38bdf8"/>' +
        '<circle cx="62" cy="50" r="4" fill="#38bdf8"/>' +
        '<line x1="50" y1="40" x2="38" y2="50" stroke="#38bdf8" stroke-width="1.8" opacity=".55"/>' +
        '<line x1="38" y1="50" x2="50" y2="60" stroke="#38bdf8" stroke-width="1.8" opacity=".55"/>' +
        '<line x1="50" y1="60" x2="62" y2="50" stroke="#38bdf8" stroke-width="1.8" opacity=".55"/>' +
        '<line x1="62" y1="50" x2="50" y2="40" stroke="#38bdf8" stroke-width="1.8" opacity=".55"/>' +
      '</svg>' +
      '<div class="ra-name">Research Agent</div>' +
      '<div class="ra-tag">Multi-Source AI Research Assistant</div>';

    form.parentElement.insertBefore(brand, form.parentElement.firstChild);

    // ── "Don't have an account?" link below the Sign In button ───────────
    var regLink = document.createElement('div');
    regLink.id = 'ra-reg-link';
    regLink.innerHTML = "Don't have an account? <a href=\"/public/register.html\">Create one</a>";

    var btnWrapper = submitBtn.closest('div') || submitBtn.parentElement;
    btnWrapper.parentNode.insertBefore(regLink, btnWrapper.nextSibling);
  }

  var obs = new MutationObserver(tryEnhance);
  obs.observe(document.documentElement, { childList: true, subtree: true });
  tryEnhance();
  setTimeout(tryEnhance, 400);
  setTimeout(tryEnhance, 1200);
})();
