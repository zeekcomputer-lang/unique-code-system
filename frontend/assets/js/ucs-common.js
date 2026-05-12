/* =========================================================
 * Unique Code System — Common JS Utilities
 * Vanilla JS + Bootstrap 5.3 (jQuery 사용 금지)
 *
 * 모듈 구조 (전역 window.UCS 네임스페이스):
 *   UCS.api      : fetch 래퍼 (JSON 자동 처리, 에러 정규화)
 *   UCS.toast    : 우측 하단 Bootstrap Toast (가이드라인 §5.4)
 *   UCS.loading  : 폼 제출 로딩 상태 (§5.3)
 *   UCS.prefix   : Prefix 입력 강제 변환 (§5.1)
 *   UCS.format   : 날짜/시간 포맷 헬퍼
 * ========================================================= */
(function (global) {
  'use strict';

  /* ───────────────────────────── 설정 ───────────────────────────── */
  const DEFAULT_API_BASE =
    (location.port === '8000' || location.protocol === 'file:')
      ? '' // 동일 오리진(백엔드 직접 서빙)
      : 'http://localhost:8000';

  const config = {
    apiBase:
      (global.UCS_API_BASE !== undefined ? global.UCS_API_BASE : DEFAULT_API_BASE),
  };

  /* ───────────────────────────── API ────────────────────────────── */
  /**
   * fetch 래퍼.
   * @param {string} path      "/api/requests"
   * @param {object} [options] { method, body, query, headers }
   * @returns {Promise<any>}   JSON 응답 (성공 시), 실패 시 throw
   */
  async function request(path, options = {}) {
    const url = new URL(config.apiBase + path, location.href);
    if (options.query) {
      Object.entries(options.query).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== '') {
          url.searchParams.set(k, v);
        }
      });
    }

    const headers = Object.assign(
      { 'Accept': 'application/json' },
      options.headers || {},
    );
    const init = {
      method: options.method || 'GET',
      headers,
    };
    if (options.body !== undefined) {
      headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(options.body);
    }

    let res;
    try {
      res = await fetch(url.toString(), init);
    } catch (e) {
      throw new ApiError('네트워크 오류: 서버에 연결할 수 없습니다.', 0, null);
    }

    const text = await res.text();
    let data = null;
    if (text) {
      try { data = JSON.parse(text); } catch (_) { data = text; }
    }

    if (!res.ok) {
      const detail = (data && data.detail) || res.statusText || '요청 실패';
      const msg = typeof detail === 'string' ? detail : formatValidationError(detail);
      throw new ApiError(msg, res.status, data);
    }
    return data;
  }

  function formatValidationError(detail) {
    if (Array.isArray(detail)) {
      const first = detail[0] || {};
      const loc = (first.loc || []).slice(-1)[0] || 'field';
      return `${loc}: ${first.msg || '유효성 오류'}`;
    }
    return '유효성 오류';
  }

  class ApiError extends Error {
    constructor(message, status, payload) {
      super(message);
      this.name = 'ApiError';
      this.status = status;
      this.payload = payload;
    }
  }

  const api = {
    get:  (path, query)        => request(path, { method: 'GET', query }),
    post: (path, body)         => request(path, { method: 'POST', body }),
    put:  (path, body)         => request(path, { method: 'PUT', body }),
    del:  (path, query)        => request(path, { method: 'DELETE', query }),
    request,
    ApiError,
    setBase: (b) => { config.apiBase = b || ''; },
    getBase: () => config.apiBase,
  };

  /* ───────────────────────────── Toast (§5.4) ────────────────────── */
  function ensureToastContainer() {
    let el = document.querySelector('#ucsToastContainer');
    if (!el) {
      el = document.createElement('div');
      el.id = 'ucsToastContainer';
      el.className = 'ucs-toast-container';
      el.setAttribute('aria-live', 'polite');
      el.setAttribute('aria-atomic', 'true');
      document.body.appendChild(el);
    }
    return el;
  }

  const TOAST_PALETTE = {
    success: { bg: 'bg-success-subtle', text: 'text-success', icon: 'fa-circle-check' },
    danger:  { bg: 'bg-danger-subtle',  text: 'text-danger',  icon: 'fa-circle-xmark' },
    warning: { bg: 'bg-warning-subtle', text: 'text-warning', icon: 'fa-triangle-exclamation' },
    info:    { bg: 'bg-light',          text: 'text-dark',    icon: 'fa-circle-info' },
  };

  /**
   * @param {string} message
   * @param {'success'|'danger'|'warning'|'info'} [variant]
   * @param {number} [delay] ms
   */
  function showToast(message, variant = 'success', delay = 3000) {
    if (typeof bootstrap === 'undefined' || !bootstrap.Toast) {
      // Bootstrap 미로딩 시 폴백: console
      console[variant === 'danger' ? 'error' : 'log']('[UCS]', message);
      return;
    }
    const p = TOAST_PALETTE[variant] || TOAST_PALETTE.info;
    const el = document.createElement('div');
    el.className = `toast align-items-center border-0 shadow-sm ${p.bg} ${p.text}`;
    el.setAttribute('role', 'alert');
    el.setAttribute('aria-live', 'assertive');
    el.setAttribute('aria-atomic', 'true');
    el.innerHTML = `
      <div class="d-flex">
        <div class="toast-body d-flex align-items-center gap-2 fw-medium">
          <i class="fa-solid ${p.icon}"></i>
          <span></span>
        </div>
        <button type="button" class="btn-close me-2 m-auto"
                data-bs-dismiss="toast" aria-label="Close"></button>
      </div>`;
    // textContent로 안전 삽입 (XSS 방지)
    el.querySelector('.toast-body span').textContent = message;

    ensureToastContainer().appendChild(el);
    const t = new bootstrap.Toast(el, { delay });
    t.show();
    el.addEventListener('hidden.bs.toast', () => el.remove());
  }

  const toast = {
    success: (m, d) => showToast(m, 'success', d),
    danger:  (m, d) => showToast(m, 'danger',  d),
    warning: (m, d) => showToast(m, 'warning', d),
    info:    (m, d) => showToast(m, 'info',    d),
    show:    showToast,
  };

  /* ───────────────────────────── Loading (§5.3) ──────────────────── */
  /**
   * 폼 submit 버튼을 로딩 상태로 전환.
   * @param {HTMLButtonElement} btn
   * @returns {() => void} restore 함수
   */
  function startLoading(btn) {
    if (!btn) return () => {};
    const icon = btn.querySelector('i');
    const originalIconClass = icon ? icon.className : null;
    const originalDisabled = btn.disabled;

    if (icon) icon.className = 'fa-solid fa-circle-notch fa-spin';
    btn.disabled = true;
    btn.classList.add('disabled');

    return function restore() {
      if (icon && originalIconClass !== null) icon.className = originalIconClass;
      btn.disabled = originalDisabled;
      btn.classList.remove('disabled');
    };
  }

  const loading = { start: startLoading };

  /* ───────────────────────────── Prefix Input (§5.1) ─────────────── */
  /**
   * Prefix 입력 필드에 영문 강제 + 대문자 + 비허용 문자 즉시 제거.
   * @param {string} [selector] 기본 'input.ucs-input-code'
   */
  function bindPrefixInputs(selector = 'input.ucs-input-code') {
    document.querySelectorAll(selector).forEach((el) => {
      if (el.dataset.ucsPrefixBound === '1') return;
      el.dataset.ucsPrefixBound = '1';
      el.addEventListener('input', (e) => {
        const cleaned = (e.target.value || '').replace(/[^a-zA-Z]/g, '').toUpperCase();
        if (e.target.value !== cleaned) e.target.value = cleaned;
      });
    });
  }

  const prefix = { bind: bindPrefixInputs };

  /* ───────────────────────────── Format ──────────────────────────── */
  function formatDateTime(isoString) {
    if (!isoString) return '-';
    try {
      const d = new Date(isoString);
      if (isNaN(d.getTime())) return isoString;
      const pad = (n) => String(n).padStart(2, '0');
      return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ` +
             `${pad(d.getHours())}:${pad(d.getMinutes())}`;
    } catch (_) {
      return isoString;
    }
  }
  const format = { dateTime: formatDateTime };

  /* ───────────────────────────── Export ──────────────────────────── */
  global.UCS = { api, toast, loading, prefix, format, config };

  // DOM ready 시 자동 바인딩
  document.addEventListener('DOMContentLoaded', () => bindPrefixInputs());
})(window);
