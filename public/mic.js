(function () {
  'use strict';

  /* ── Load mic.css ──────────────────────────────────────────────────── */
  (function loadStyles() {
    if (document.getElementById('ra-mic-css-link')) return;
    var link = document.createElement('link');
    link.id = 'ra-mic-css-link';
    link.rel = 'stylesheet';
    link.href = '/public/mic.css';
    document.head.appendChild(link);
  }());

  /* ── Config ────────────────────────────────────────────────────────── */
  var SILENCE_AVG_THRESHOLD = 12;
  var SILENCE_STOP_MS = 5000;

  /* ── State ─────────────────────────────────────────────────────────── */
  var _rec = false;
  var _busy = false;
  var _mr = null;
  var _chunks = [];
  var _actx = null;
  var _analyser = null;
  var _stream = null;
  var _silStart = null;
  var _raf = null;
  var _micBtn = null;
  var _indicator = null;

  /* ── Icons ─────────────────────────────────────────────────────────── */
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

  function stopIcon() {
    return (
      '<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24"' +
      ' fill="currentColor">' +
      '<rect x="3" y="3" width="18" height="18" rx="3"/>' +
      '</svg>'
    );
  }

  /* ── UI helpers ────────────────────────────────────────────────────── */
  function positionIndicator() {
    if (!_indicator) return;
    var composer =
      document.getElementById('message-composer') ||
      document.querySelector('[id*="composer"]') ||
      document.querySelector('[class*="composer"]') ||
      (function () {
        var ta = document.querySelector('textarea');
        if (!ta) return null;
        var node = ta.parentElement;
        while (node && node !== document.body) {
          var r = node.getBoundingClientRect();
          if (r.width > 300 && r.height > 50) return node;
          node = node.parentElement;
        }
        return null;
      }());
    if (composer) {
      var rect = composer.getBoundingClientRect();
      _indicator.style.bottom = (window.innerHeight - rect.top + 8) + 'px';
      _indicator.style.left = (rect.left + rect.width / 2) + 'px';
      _indicator.style.transform = 'translateX(-50%)';
    }
  }

  function setIndicator(state, label) {
    if (!_indicator) return;
    _indicator.classList.remove('ra-on', 'ra-busy');
    if (!state) return;
    positionIndicator();
    if (state === 'listening') {
      _indicator.innerHTML =
        '<div class="ra-sp"></div><div class="ra-sp"></div><div class="ra-sp"></div>' +
        '<span>' + (label || 'Listening… auto-stops after 5 s silence') + '</span>';
      _indicator.classList.add('ra-on');
    } else if (state === 'transcribing') {
      _indicator.innerHTML = '<span>' + (label || 'Transcribing…') + '</span>';
      _indicator.classList.add('ra-on', 'ra-busy');
    }
  }

  function showToast(msg) {
    var old = document.getElementById('ra-toast');
    if (old) old.remove();
    var el = document.createElement('div');
    el.id = 'ra-toast';
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(function () {
      var t = document.getElementById('ra-toast');
      if (t) t.remove();
    }, 3500);
  }

  /* ── Submit transcribed text to LLM ───────────────────────────────── */
  function submitToLLM(text) {
    var ta = document.querySelector('textarea');
    if (!ta) { showToast('Could not find the chat input — please try again.'); return; }

    var setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set;
    setter.call(ta, text);
    ta.dispatchEvent(new Event('input', { bubbles: true }));
    ta.dispatchEvent(new Event('change', { bubbles: true }));

    function trySend(attemptsLeft) {
      var btn =
        document.querySelector('button[data-testid="send-button"]') ||
        document.querySelector('button[aria-label="Send message"]') ||
        (function () {
          var btns = document.querySelectorAll('button[type="submit"]');
          return btns[btns.length - 1] || null;
        }());
      if (btn && !btn.disabled) {
        btn.click();
      } else if (attemptsLeft > 0) {
        setTimeout(function () { trySend(attemptsLeft - 1); }, 100);
      }
    }
    setTimeout(function () { trySend(8); }, 80);
  }

  /* ── Recording lifecycle ───────────────────────────────────────────── */
  function releaseResources() {
    if (_raf)    { cancelAnimationFrame(_raf); _raf = null; }
    if (_actx)   { try { _actx.close(); } catch (e) {} _actx = null; }
    if (_stream) { _stream.getTracks().forEach(function (t) { t.stop(); }); _stream = null; }
    _analyser = null;
    _silStart = null;
  }

  function resetMicBtn() {
    _busy = false;
    setIndicator(null);
    if (_micBtn) {
      _micBtn.innerHTML = micIcon();
      _micBtn.classList.remove('ra-recording');
      _micBtn.disabled = false;
      _micBtn.title = 'Click to speak';
    }
  }

  function stopRecording() {
    if (!_rec) return;
    _rec = false;
    _busy = true;
    releaseResources();
    if (_micBtn) {
      _micBtn.innerHTML = micIcon();
      _micBtn.classList.remove('ra-recording');
      _micBtn.disabled = true;
      _micBtn.title = 'Transcribing…';
    }
    setIndicator('transcribing');
    if (_mr && _mr.state !== 'inactive') _mr.stop();
  }

  function doTranscribe(blob) {
    var fd = new FormData();
    fd.append('audio', blob, 'recording.webm');
    fetch('/api/transcribe', { method: 'POST', body: fd })
      .then(function (r) { return r.json(); })
      .then(function (json) {
        var txt = (json.text || '').trim();
        resetMicBtn();
        if (!txt) { showToast("Couldn't make that out — try speaking louder."); return; }
        submitToLLM(txt);
      })
      .catch(function () {
        resetMicBtn();
        showToast('Transcription failed — check your connection and try again.');
      });
  }

  function startRecording() {
    if (_busy) return;
    navigator.mediaDevices.getUserMedia({ audio: true, video: false })
      .then(function (stream) {
        _stream = stream;
        _actx = new (window.AudioContext || window.webkitAudioContext)();
        var src = _actx.createMediaStreamSource(_stream);
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
          _chunks = [];
          if (blob.size < 500) { resetMicBtn(); showToast("Didn't catch anything — try again."); return; }
          doTranscribe(blob);
        };

        _mr.start(100);
        _rec = true;

        if (_micBtn) {
          _micBtn.innerHTML = stopIcon();
          _micBtn.classList.add('ra-recording');
          _micBtn.disabled = false;
          _micBtn.title = 'Click to stop recording';
        }
        setIndicator('listening');

        // Silence detection
        var data = new Uint8Array(_analyser.frequencyBinCount);
        (function tick() {
          if (!_rec) return;
          _analyser.getByteFrequencyData(data);
          var sum = 0;
          for (var i = 0; i < data.length; i++) sum += data[i];
          if (sum / data.length < SILENCE_AVG_THRESHOLD) {
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

  /* ── Inject mic button directly adjacent to send button ───────────── */
  function findSendBtn() {
    return (
      document.querySelector('#chat-submit') ||
      document.querySelector('button[data-testid="send-button"]') ||
      document.querySelector('button[aria-label="Send message"]') ||
      document.querySelector('button[aria-label*="send" i]') ||
      (function () {
        // Last resort: rightmost button near the textarea
        var ta = document.querySelector('textarea');
        if (!ta) return null;
        var root = ta.parentElement;
        while (root && root !== document.body) {
          var btns = Array.from(root.querySelectorAll('button'));
          if (btns.length >= 2) {
            return btns.reduce(function (best, b) {
              var box = b.getBoundingClientRect();
              var bestBox = best.getBoundingClientRect();
              return box.right > bestBox.right ? b : best;
            });
          }
          root = root.parentElement;
        }
        return null;
      }())
    );
  }

  function tryInjectMic() {
    if (document.getElementById('ra-mic-btn')) return;

    var ta = document.querySelector('textarea');
    if (!ta) return;

    var sendBtn = findSendBtn();
    if (!sendBtn || !sendBtn.parentElement) return;

    // Status indicator (fixed floating pill)
    var oldInd = document.getElementById('ra-indicator');
    if (oldInd) oldInd.remove();
    _indicator = document.createElement('div');
    _indicator.id = 'ra-indicator';
    document.body.appendChild(_indicator);

    // Mic button
    _micBtn = document.createElement('button');
    _micBtn.id = 'ra-mic-btn';
    _micBtn.type = 'button';
    _micBtn.title = 'Click to speak';
    _micBtn.setAttribute('aria-label', 'Voice input');
    _micBtn.innerHTML = micIcon();
    _micBtn.addEventListener('click', function () {
      if (_busy) return;
      _rec ? stopRecording() : startRecording();
    });

    // Place mic button immediately to the left of the send button
    sendBtn.parentElement.insertBefore(_micBtn, sendBtn);
  }

  /* ── Watch for SPA navigation re-rendering the composer ───────────── */
  window.addEventListener('resize', function () { positionIndicator(); });

  var _obs = new MutationObserver(function () { tryInjectMic(); });
  _obs.observe(document.documentElement, { childList: true, subtree: true });

  tryInjectMic();
  setTimeout(tryInjectMic, 800);
  setTimeout(tryInjectMic, 2000);
  setTimeout(tryInjectMic, 4000);
}());
