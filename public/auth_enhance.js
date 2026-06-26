(function () {
  'use strict';

  /* ═══════════════════════════════════════════════════════════════════
     SECTION 1 – Login page: brand logo + register link
  ═══════════════════════════════════════════════════════════════════ */

  function injectLoginStyles() {
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

  function tryEnhanceLogin() {
    var form = document.querySelector('form');
    if (!form) return;
    var submitBtn = form.querySelector('button[type="submit"]');
    if (!submitBtn) return;
    if (document.getElementById('ra-brand')) return;

    injectLoginStyles();

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

    var regLink = document.createElement('div');
    regLink.id = 'ra-reg-link';
    regLink.innerHTML = "Don't have an account? <a href=\"/public/register.html\">Create one</a>";

    var btnWrapper = submitBtn.closest('div') || submitBtn.parentElement;
    btnWrapper.parentNode.insertBefore(regLink, btnWrapper.nextSibling);
  }

  /* ═══════════════════════════════════════════════════════════════════
     SECTION 2 – Chat page: custom mic button with silence detection
  ═══════════════════════════════════════════════════════════════════ */

  var SILENCE_AVG_THRESHOLD = 12;   // avg frequency energy (0-255); below = silence
  var SILENCE_STOP_MS       = 5000; // auto-stop after 5 s of continuous silence

  var _rec       = false;
  var _mr        = null;
  var _chunks    = [];
  var _actx      = null;
  var _analyser  = null;
  var _stream    = null;
  var _silStart  = null;
  var _raf       = null;
  var _micBtn    = null;
  var _indicator = null;
  var _toastEl   = null;

  function injectVoiceStyles() {
    if (document.getElementById('ra-voice-styles')) return;
    var s = document.createElement('style');
    s.id = 'ra-voice-styles';
    s.textContent =
      /* --- mic button --- */
      '#ra-mic-btn{display:flex;align-items:center;justify-content:center;' +
      'width:34px;height:34px;border-radius:50%;border:none;background:transparent;' +
      'cursor:pointer;color:#94a3b8;transition:color .2s,background .2s;flex-shrink:0}' +
      '#ra-mic-btn:hover{color:#38bdf8;background:rgba(56,189,248,.12)}' +
      '#ra-mic-btn.ra-on{color:#ef4444;background:rgba(239,68,68,.12);' +
      'animation:ra-pulse 1s ease-in-out infinite}' +
      '@keyframes ra-pulse{' +
        '0%,100%{transform:scale(1);box-shadow:0 0 0 0 rgba(239,68,68,.4)}' +
        '50%{transform:scale(1.12);box-shadow:0 0 0 9px rgba(239,68,68,0)}' +
      '}' +
      /* --- listening indicator --- */
      '#ra-indicator{position:fixed;bottom:88px;left:50%;transform:translateX(-50%);' +
      'display:none;align-items:center;gap:6px;padding:7px 16px;' +
      'background:rgba(15,23,42,.93);border:1px solid rgba(239,68,68,.3);' +
      'border-radius:24px;font:500 12px/1 Arial,sans-serif;color:#fca5a5;' +
      'backdrop-filter:blur(8px);z-index:9999;white-space:nowrap}' +
      '#ra-indicator.ra-on{display:flex}' +
      /* --- spark dots inside the indicator --- */
      '.ra-sp{width:7px;height:7px;border-radius:50%;background:#ef4444;' +
      'animation:ra-spark 1.1s ease-in-out infinite}' +
      '.ra-sp:nth-child(2){animation-delay:.18s}' +
      '.ra-sp:nth-child(3){animation-delay:.36s}' +
      '@keyframes ra-spark{' +
        '0%,80%,100%{transform:translateY(0);opacity:1}' +
        '40%{transform:translateY(-6px);opacity:.7}' +
      '}';
    document.head.appendChild(s);
  }

  function micIcon() {
    return (
      '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"' +
      ' fill="none" stroke="currentColor" stroke-width="2"' +
      ' stroke-linecap="round" stroke-linejoin="round">' +
      '<path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>' +
      '<path d="M19 10v2a7 7 0 0 1-14 0v-2"/>' +
      '<line x1="12" y1="19" x2="12" y2="23"/>' +
      '<line x1="8" y1="23" x2="16" y2="23"/>' +
      '</svg>'
    );
  }

  function setIndicator(on, label) {
    if (!_indicator) return;
    if (on) {
      _indicator.innerHTML =
        '<div class="ra-sp"></div><div class="ra-sp"></div><div class="ra-sp"></div>' +
        '<span>' + (label || 'Listening…') + '</span>';
      _indicator.classList.add('ra-on');
    } else {
      _indicator.classList.remove('ra-on');
    }
  }

  function showToast(msg) {
    if (_toastEl) _toastEl.remove();
    _toastEl = document.createElement('div');
    _toastEl.style.cssText =
      'position:fixed;bottom:80px;left:50%;transform:translateX(-50%);' +
      'background:#1e293b;color:#94a3b8;padding:8px 18px;border-radius:8px;' +
      'font:13px Arial,sans-serif;z-index:10000;white-space:nowrap;' +
      'border:1px solid #334155;';
    _toastEl.textContent = msg;
    document.body.appendChild(_toastEl);
    setTimeout(function () { if (_toastEl) { _toastEl.remove(); _toastEl = null; } }, 3500);
  }

  function fillChatInput(text) {
    var ta = document.querySelector('textarea');
    if (!ta) return;
    // Use React's native setter so the controlled component updates
    var setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set;
    setter.call(ta, text);
    ta.dispatchEvent(new Event('input', { bubbles: true }));
    ta.dispatchEvent(new Event('change', { bubbles: true }));
    ta.focus();
  }

  function releaseResources() {
    if (_raf)    { cancelAnimationFrame(_raf); _raf = null; }
    if (_actx)   { try { _actx.close(); } catch (e) {} _actx = null; }
    if (_stream) { _stream.getTracks().forEach(function (t) { t.stop(); }); _stream = null; }
    _analyser = null;
    _silStart = null;
  }

  function stopRecording() {
    if (!_rec) return;
    _rec = false;
    releaseResources();
    if (_micBtn) { _micBtn.classList.remove('ra-on'); _micBtn.title = 'Click to speak'; }
    setIndicator(true, 'Transcribing…');
    if (_mr && _mr.state !== 'inactive') _mr.stop();
  }

  function startRecording() {
    navigator.mediaDevices.getUserMedia({ audio: true, video: false })
      .then(function (stream) {
        _stream   = stream;
        _actx     = new (window.AudioContext || window.webkitAudioContext)();
        var src   = _actx.createMediaStreamSource(_stream);
        _analyser = _actx.createAnalyser();
        _analyser.fftSize = 256;
        src.connect(_analyser);

        _chunks = [];
        var mime = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', '']
          .find(function (m) { return m === '' || MediaRecorder.isTypeSupported(m); });

        _mr = new MediaRecorder(_stream, mime ? { mimeType: mime } : undefined);
        _mr.ondataavailable = function (e) {
          if (e.data && e.data.size > 0) _chunks.push(e.data);
        };
        _mr.onstop = function () {
          var blob = new Blob(_chunks, { type: _mr.mimeType || 'audio/webm' });
          _chunks  = [];
          if (blob.size < 500) {
            setIndicator(false);
            showToast("Didn't catch anything — try again.");
            return;
          }
          doTranscribe(blob);
        };

        _mr.start(100);
        _rec = true;
        if (_micBtn) { _micBtn.classList.add('ra-on'); _micBtn.title = 'Click to stop'; }
        setIndicator(true, 'Listening… (auto-stops after 5 s silence)');

        // Silence detection
        var data = new Uint8Array(_analyser.frequencyBinCount);
        (function tick() {
          if (!_rec) return;
          _analyser.getByteFrequencyData(data);
          var sum = 0;
          for (var i = 0; i < data.length; i++) sum += data[i];
          var avg = sum / data.length;

          if (avg < SILENCE_AVG_THRESHOLD) {
            if (!_silStart) _silStart = Date.now();
            else if (Date.now() - _silStart >= SILENCE_STOP_MS) { stopRecording(); return; }
          } else {
            _silStart = null;
          }
          _raf = requestAnimationFrame(tick);
        }());
      })
      .catch(function () {
        showToast('Microphone access denied — please allow it in your browser and try again.');
      });
  }

  function doTranscribe(blob) {
    var fd = new FormData();
    fd.append('audio', blob, 'recording.webm');
    fetch('/api/transcribe', { method: 'POST', body: fd })
      .then(function (r) { return r.json(); })
      .then(function (json) {
        setIndicator(false);
        var txt = (json.text || '').trim();
        if (!txt) { showToast("Couldn't make that out — try speaking louder."); return; }
        fillChatInput(txt);
      })
      .catch(function () {
        setIndicator(false);
        showToast('Transcription failed — check your connection and try again.');
      });
  }

  function tryInjectMic() {
    if (document.getElementById('ra-mic-btn')) return;

    // Only active on the chat page (a textarea must be present)
    var ta = document.querySelector('textarea');
    if (!ta) return;

    injectVoiceStyles();

    // Remove any stale indicator from a previous SPA navigation
    var old = document.getElementById('ra-indicator');
    if (old) old.remove();

    // Floating listening indicator (fixed position, above the composer)
    _indicator = document.createElement('div');
    _indicator.id = 'ra-indicator';
    document.body.appendChild(_indicator);

    // Hide Chainlit's native audio button (wave/voice icon)
    var nativeAudio =
      document.querySelector('[data-testid="audio-input"]') ||
      document.querySelector('[aria-label="Voice input"]') ||
      document.querySelector('[aria-label="Record voice message"]');
    if (nativeAudio) nativeAudio.style.display = 'none';

    // Create mic button
    _micBtn           = document.createElement('button');
    _micBtn.id        = 'ra-mic-btn';
    _micBtn.type      = 'button';
    _micBtn.title     = 'Click to speak';
    _micBtn.innerHTML = micIcon();
    _micBtn.addEventListener('click', function () {
      _rec ? stopRecording() : startRecording();
    });

    // Insert before Chainlit's send button
    var sendBtn =
      document.querySelector('button[data-testid="send-button"]') ||
      document.querySelector('button[type="submit"]');

    if (sendBtn && sendBtn.parentElement) {
      sendBtn.parentElement.insertBefore(_micBtn, sendBtn);
    } else {
      ta.parentElement && ta.parentElement.appendChild(_micBtn);
    }
  }

  /* ── Boot ─────────────────────────────────────────────────────────────── */

  var _obs = new MutationObserver(function () {
    tryEnhanceLogin();
    tryInjectMic();
  });
  _obs.observe(document.documentElement, { childList: true, subtree: true });

  tryEnhanceLogin();
  tryInjectMic();
  setTimeout(tryEnhanceLogin, 400);
  setTimeout(tryEnhanceLogin, 1200);
  setTimeout(tryInjectMic, 800);
  setTimeout(tryInjectMic, 2000);
  setTimeout(tryInjectMic, 4000);
})();
