(function () {
  'use strict';

  var isRegister = false;

  // Update a React-controlled input's value so React state stays in sync.
  function setInputValue(input, value) {
    var nativeSet = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    nativeSet.call(input, value);
    // Make React think the value changed by resetting its internal tracker
    var tracker = input._valueTracker;
    if (tracker) tracker.setValue('');
    input.dispatchEvent(new Event('input', { bubbles: true }));
  }

  function injectStyles() {
    if (document.getElementById('ra-styles')) return;
    var style = document.createElement('style');
    style.id = 'ra-styles';
    style.textContent =
      '#ra-brand{text-align:center;padding:22px 0 4px}' +
      '#ra-brand svg{display:block;margin:0 auto 10px}' +
      '#ra-brand .ra-name{color:#fff;font:700 22px/1.2 Arial,sans-serif;letter-spacing:.4px}' +
      '#ra-brand .ra-tag{color:#64748b;font:12px/1.5 Arial,sans-serif;margin-top:5px}' +
      '#ra-switch{text-align:center;margin-top:14px;font:13px Arial,sans-serif;color:#94a3b8}' +
      '#ra-switch a{color:#38bdf8;text-decoration:none;font-weight:500}' +
      '#ra-switch a:hover{text-decoration:underline}';
    document.head.appendChild(style);
  }

  function tryEnhance() {
    var form = document.querySelector('form');
    if (!form) return;

    var submitBtn = form.querySelector('button[type="submit"]');
    if (!submitBtn) return;

    // Already enhanced this form
    if (document.getElementById('ra-brand')) return;

    injectStyles();
    isRegister = false;

    // ── Brand block above the login card ──────────────────────────────────
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

    var container = form.parentElement;
    container.insertBefore(brand, container.firstChild);

    // ── Sign In / Register toggle below the submit button ─────────────────
    var switchArea = document.createElement('div');
    switchArea.id = 'ra-switch';
    switchArea.innerHTML = 'New here? <a id="ra-toggle" href="#">Create an account</a>';

    var btnWrapper = submitBtn.closest('div') || submitBtn.parentElement;
    btnWrapper.parentNode.insertBefore(switchArea, btnWrapper.nextSibling);

    document.getElementById('ra-toggle').addEventListener('click', function (e) {
      e.preventDefault();
      isRegister = !isRegister;
      if (isRegister) {
        submitBtn.textContent = 'Create Account';
        this.textContent = 'Sign in instead';
        this.previousSibling.textContent = 'Already have an account? ';
      } else {
        submitBtn.textContent = 'Sign In';
        this.textContent = 'Create an account';
        this.previousSibling.textContent = 'New here? ';
      }
    });

    // ── Intercept submit to encode register intent in password field ───────
    // Runs in capture phase so our listener fires before React's click handler.
    // setInputValue triggers a synchronous React state update so the new value
    // reaches the server when Chainlit POSTs the credentials.
    submitBtn.addEventListener('click', function () {
      if (!isRegister) return;
      var pw = form.querySelector('input[type="password"]');
      if (pw && !pw.value.startsWith('__reg__:')) {
        setInputValue(pw, '__reg__:' + pw.value);
      }
    }, true);
  }

  // Watch for the React-rendered login form to appear
  var observer = new MutationObserver(tryEnhance);
  observer.observe(document.documentElement, { childList: true, subtree: true });

  tryEnhance();
  setTimeout(tryEnhance, 400);
  setTimeout(tryEnhance, 1200);
})();
