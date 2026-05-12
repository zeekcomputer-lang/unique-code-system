/* =========================================================
 * dashboard.html 전용 로직
 * - /api/dashboard 단일 호출로 모든 카드/게이지 채움
 * - 수동/자동 새로고침 토글 (15초 간격)
 * ========================================================= */
(function () {
  'use strict';

  const $refreshNow = document.querySelector('#refreshNowBtn');
  const $autoBtn    = document.querySelector('#autoRefreshBtn');
  const $autoLabel  = document.querySelector('#autoRefreshLabel');
  const $last       = document.querySelector('#lastUpdated');
  const $usageBar   = document.querySelector('#usageBar');
  const $next       = document.querySelector('#nextPreview');
  const $redis      = document.querySelector('#redisBadge');

  let autoTimer = null;

  /* ───────── 렌더링 ───────── */
  function setAll(selector, value) {
    document.querySelectorAll(selector).forEach((el) => { el.textContent = value; });
  }

  function renderRedisBadge(ok) {
    if (ok) {
      $redis.className = 'badge rounded-1 px-2 py-1 fw-bold text-uppercase ' +
                         'bg-success-subtle text-success border border-success-subtle';
      $redis.textContent = 'ONLINE';
    } else {
      $redis.className = 'badge rounded-1 px-2 py-1 fw-bold text-uppercase ' +
                         'bg-danger-subtle text-danger border border-danger-subtle';
      $redis.textContent = 'OFFLINE';
    }
    $redis.style.fontSize = '11px';
    $redis.style.letterSpacing = '.04em';
  }

  function renderNextPreview(items) {
    $next.innerHTML = '';
    if (!items || !items.length) {
      $next.innerHTML = '<span class="text-muted small">발급 가능한 코드가 없습니다.</span>';
      return;
    }
    items.forEach((it) => {
      const chip = document.createElement('div');
      chip.className =
        'd-inline-flex align-items-center gap-2 px-3 py-2 rounded-3 ' +
        'bg-light border';
      chip.innerHTML = `
        <span class="badge rounded-1 bg-secondary-subtle text-secondary
                     border border-secondary-subtle fw-bold"
              style="font-size:10px; letter-spacing:.04em;">#${it.score}</span>
        <span class="ucs-code ucs-code-primary fs-6"></span>
      `;
      chip.querySelector('.ucs-code').textContent = it.code;
      $next.appendChild(chip);
    });
  }

  /* ───────── 로드 ───────── */
  async function loadDashboard() {
    const restore = UCS.loading.start($refreshNow);
    try {
      const d = await UCS.api.get('/api/dashboard');

      setAll('[data-k="total"]',     d.codes.total);
      setAll('[data-k="active"]',    d.codes.active);
      setAll('[data-k="waiting"]',   d.codes.waiting);
      setAll('[data-k="revoked"]',   d.codes.revoked);
      setAll('[data-k="remaining"]', d.codes.remaining_in_queue);
      setAll('[data-k="usage_pct"]', `${(d.codes.usage_pct ?? 0).toFixed(1)}%`);

      setAll('[data-k="req_pending"]',  d.requests.pending);
      setAll('[data-k="req_approved"]', d.requests.approved);
      setAll('[data-k="req_rejected"]', d.requests.rejected);

      // 사용률 게이지
      const pct = Math.max(0, Math.min(100, d.codes.usage_pct ?? 0));
      $usageBar.style.width = `${pct}%`;
      // 임계치별 색상 (Success/Warning/Danger)
      $usageBar.style.backgroundColor =
        pct >= 90 ? 'var(--ucs-danger)' :
        pct >= 70 ? 'var(--ucs-warning)' :
                    'var(--ucs-primary)';

      renderRedisBadge(d.redis_ok);
      renderNextPreview(d.next_preview);

      $last.textContent = `업데이트: ${UCS.format.dateTime(new Date().toISOString())}`;
    } catch (err) {
      UCS.toast.danger(`대시보드 조회 실패: ${err.message}`);
      renderRedisBadge(false);
    } finally {
      restore();
    }
  }

  /* ───────── 자동 새로고침 ───────── */
  function setAuto(on) {
    if (on) {
      if (!autoTimer) autoTimer = setInterval(loadDashboard, 15000);
      $autoBtn.classList.remove('btn-outline-secondary');
      $autoBtn.classList.add('btn-primary');
      $autoBtn.setAttribute('aria-pressed', 'true');
      $autoLabel.textContent = '자동: ON (15s)';
    } else {
      if (autoTimer) { clearInterval(autoTimer); autoTimer = null; }
      $autoBtn.classList.add('btn-outline-secondary');
      $autoBtn.classList.remove('btn-primary');
      $autoBtn.setAttribute('aria-pressed', 'false');
      $autoLabel.textContent = '자동 새로고침';
    }
  }

  $autoBtn.addEventListener('click', () => {
    setAuto($autoBtn.getAttribute('aria-pressed') !== 'true');
  });
  $refreshNow.addEventListener('click', loadDashboard);

  // 페이지 가시성에 따라 자동 갱신 일시정지 (백그라운드 탭 절약)
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      if (autoTimer) { clearInterval(autoTimer); autoTimer = null; }
    } else if ($autoBtn.getAttribute('aria-pressed') === 'true') {
      autoTimer = setInterval(loadDashboard, 15000);
      loadDashboard();
    }
  });

  document.addEventListener('DOMContentLoaded', loadDashboard);
})();
