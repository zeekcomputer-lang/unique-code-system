/* =========================================================
 * admin.html 전용 로직
 *
 * - PENDING 의뢰 승인 → /api/codes/issue/{req_id}
 * - 전체 코드 테이블 (필터/검색)
 * - 강제 수기 채번 → /api/codes/force
 * - 파기 → /api/codes/revoke/{code} (§5.5 모달 필수 노출)
 * - Stat strip 자동 동기화
 * ========================================================= */
(function () {
  'use strict';

  /* ─────────────────────────── 상태 ─────────────────────────── */
  let allCodes = [];   // GET /api/codes 캐시
  let pending  = [];   // GET /api/requests?status=PENDING 캐시

  /* ─────────────────────────── Util ─────────────────────────── */
  function statusBadge(status) {
    const map = {
      ACTIVE:   { cls: 'bg-success-subtle text-success border border-success-subtle' },
      WAITING:  { cls: 'bg-secondary-subtle text-secondary border border-secondary-subtle' },
      REVOKED:  { cls: 'bg-danger-subtle text-danger border border-danger-subtle' },
      PENDING:  { cls: 'bg-warning-subtle text-warning border border-warning-subtle' },
      APPROVED: { cls: 'bg-success-subtle text-success border border-success-subtle' },
      REJECTED: { cls: 'bg-danger-subtle text-danger border border-danger-subtle' },
    };
    const v = map[status] || { cls: 'bg-secondary-subtle text-secondary border border-secondary-subtle' };
    const el = document.createElement('span');
    el.className = `badge rounded-1 px-2 py-1 fw-bold text-uppercase ${v.cls}`;
    el.style.fontSize = '11px';
    el.style.letterSpacing = '.04em';
    el.textContent = status;
    return el;
  }

  function codeSpan(text, primary = false) {
    const s = document.createElement('span');
    s.className = primary ? 'ucs-code ucs-code-primary' : 'ucs-code';
    s.textContent = text || '—';
    return s;
  }

  function setText(sel, value) {
    const el = document.querySelector(sel);
    if (el) el.textContent = value;
  }

  /* ─────────────────────────── Stat Strip ───────────────────── */
  async function loadStats() {
    try {
      const d = await UCS.api.get('/api/dashboard');
      setText('[data-stat="pending"]',   d.requests.pending);
      setText('[data-stat="active"]',    d.codes.active);
      setText('[data-stat="remaining"]', d.codes.remaining_in_queue);
      setText('[data-stat="revoked"]',   d.codes.revoked);
    } catch (err) {
      console.warn('stat load failed', err);
    }
  }

  /* ─────────────────────────── PENDING 의뢰 ─────────────────── */
  const $pendingTbody = document.querySelector('#pendingTbody');
  const $pendingCount = document.querySelector('#pendingCount');
  const $refreshPending = document.querySelector('#refreshPendingBtn');

  function renderPendingEmpty(msg = '대기 중인 의뢰가 없습니다.') {
    $pendingTbody.innerHTML = '';
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td colspan="6" class="text-center text-muted py-5">
        <i class="fa-solid fa-inbox fa-2x mb-2 d-block"></i>${msg}
      </td>`;
    $pendingTbody.appendChild(tr);
  }

  function renderPendingRow(rec) {
    const tr = document.createElement('tr');

    const tdId = document.createElement('td');
    tdId.className = 'px-3 py-2';
    tdId.appendChild(codeSpan(rec.id, true));
    tr.appendChild(tdId);

    const tdReq = document.createElement('td');
    tdReq.className = 'px-3 py-2 fw-medium';
    tdReq.textContent = rec.requester;
    tr.appendChild(tdReq);

    const tdReason = document.createElement('td');
    tdReason.className = 'px-3 py-2 text-muted small';
    tdReason.style.maxWidth = '320px';
    tdReason.style.whiteSpace = 'nowrap';
    tdReason.style.overflow = 'hidden';
    tdReason.style.textOverflow = 'ellipsis';
    tdReason.title = rec.reason || '';
    tdReason.textContent = rec.reason || '';
    tr.appendChild(tdReason);

    const tdPrefix = document.createElement('td');
    tdPrefix.className = 'px-3 py-2';
    if (rec.desired_prefix) tdPrefix.appendChild(codeSpan(rec.desired_prefix));
    else tdPrefix.innerHTML = '<span class="text-muted small">—</span>';
    tr.appendChild(tdPrefix);

    const tdDate = document.createElement('td');
    tdDate.className = 'px-3 py-2 text-muted small';
    tdDate.textContent = UCS.format.dateTime(rec.created_at);
    tr.appendChild(tdDate);

    const tdAct = document.createElement('td');
    tdAct.className = 'px-3 py-2 text-end';
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'btn btn-primary btn-sm fw-bold px-3 d-inline-flex align-items-center gap-2';
    btn.innerHTML = '<i class="fa-solid fa-circle-check"></i> 승인 · 발급';
    btn.addEventListener('click', () => openIssueModal(rec));
    tdAct.appendChild(btn);
    tr.appendChild(tdAct);

    return tr;
  }

  async function loadPending() {
    const restore = UCS.loading.start($refreshPending);
    try {
      pending = await UCS.api.get('/api/requests', { status: 'PENDING' });
      $pendingCount.textContent = `(${pending.length})`;
      if (!pending.length) { renderPendingEmpty(); return; }
      $pendingTbody.innerHTML = '';
      pending.forEach((r) => $pendingTbody.appendChild(renderPendingRow(r)));
    } catch (err) {
      UCS.toast.danger(`PENDING 조회 실패: ${err.message}`);
      renderPendingEmpty('목록을 불러오지 못했습니다.');
    } finally {
      restore();
    }
  }

  /* ─────────────────────────── 전체 코드 테이블 ─────────────── */
  const $codeTbody       = document.querySelector('#codeTbody');
  const $codeCount       = document.querySelector('#codeCount');
  const $codeStatusFilter= document.querySelector('#codeStatusFilter');
  const $codeSearch      = document.querySelector('#codeSearch');
  const $refreshCodes    = document.querySelector('#refreshCodesBtn');

  function renderCodesEmpty(msg = '표시할 코드가 없습니다.') {
    $codeTbody.innerHTML = '';
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td colspan="8" class="text-center text-muted py-5">
        <i class="fa-solid fa-table fa-2x mb-2 d-block"></i>${msg}
      </td>`;
    $codeTbody.appendChild(tr);
  }

  function renderCodeRow(rec) {
    const tr = document.createElement('tr');
    if (rec.status === 'REVOKED') tr.classList.add('ucs-row-revoked');

    // #
    const tdSeq = document.createElement('td');
    tdSeq.className = 'px-3 py-2 text-muted small';
    tdSeq.textContent = rec.score;
    tr.appendChild(tdSeq);

    // Base
    const tdBase = document.createElement('td');
    tdBase.className = 'px-3 py-2';
    tdBase.appendChild(codeSpan(rec.code, rec.status === 'ACTIVE'));
    tr.appendChild(tdBase);

    // Full
    const tdFull = document.createElement('td');
    tdFull.className = 'px-3 py-2';
    if (rec.full_code) tdFull.appendChild(codeSpan(rec.full_code, true));
    else tdFull.innerHTML = '<span class="text-muted small">—</span>';
    tr.appendChild(tdFull);

    // Prefix
    const tdPfx = document.createElement('td');
    tdPfx.className = 'px-3 py-2';
    if (rec.prefix) tdPfx.appendChild(codeSpan(rec.prefix));
    else tdPfx.innerHTML = '<span class="text-muted small">—</span>';
    tr.appendChild(tdPfx);

    // Status (+ FORCE 표시)
    const tdStat = document.createElement('td');
    tdStat.className = 'px-3 py-2';
    tdStat.appendChild(statusBadge(rec.status));
    if (rec.force_issued) {
      const f = document.createElement('span');
      f.className = 'badge rounded-1 px-2 py-1 fw-bold text-uppercase ms-1 ' +
                    'bg-danger-subtle text-danger border border-danger-subtle';
      f.style.fontSize = '10px';
      f.textContent = 'FORCE';
      tdStat.appendChild(f);
    }
    tr.appendChild(tdStat);

    // Request
    const tdReq = document.createElement('td');
    tdReq.className = 'px-3 py-2';
    if (rec.request_id) tdReq.appendChild(codeSpan(rec.request_id));
    else tdReq.innerHTML = '<span class="text-muted small">—</span>';
    tr.appendChild(tdReq);

    // 발급일시
    const tdDate = document.createElement('td');
    tdDate.className = 'px-3 py-2 text-muted small';
    tdDate.textContent = rec.issued_at ? UCS.format.dateTime(rec.issued_at) : '—';
    tr.appendChild(tdDate);

    // 액션
    const tdAct = document.createElement('td');
    tdAct.className = 'px-3 py-2 text-end';
    if (rec.status === 'ACTIVE') {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'btn btn-outline-danger btn-sm fw-bold text-uppercase px-3 py-1';
      btn.innerHTML = '파기';
      btn.addEventListener('click', () => openRevokeModal(rec));
      tdAct.appendChild(btn);
    } else {
      tdAct.innerHTML = '<span class="text-muted small">—</span>';
    }
    tr.appendChild(tdAct);

    return tr;
  }

  function applyCodeFilters(list) {
    const status = $codeStatusFilter.value;
    const q = ($codeSearch.value || '').trim().toUpperCase();
    return list.filter((r) => {
      if (status && r.status !== status) return false;
      if (!q) return true;
      const hay = [r.code, r.full_code, r.prefix].filter(Boolean).join(' ').toUpperCase();
      return hay.includes(q);
    });
  }

  function renderCodes() {
    const list = applyCodeFilters(allCodes);
    $codeCount.textContent = `(${list.length} / ${allCodes.length})`;
    if (!list.length) { renderCodesEmpty(); return; }
    const frag = document.createDocumentFragment();
    list.forEach((r) => frag.appendChild(renderCodeRow(r)));
    $codeTbody.innerHTML = '';
    $codeTbody.appendChild(frag);
  }

  async function loadCodes() {
    const restore = UCS.loading.start($refreshCodes);
    try {
      allCodes = await UCS.api.get('/api/codes');
      renderCodes();
    } catch (err) {
      UCS.toast.danger(`코드 목록 조회 실패: ${err.message}`);
      renderCodesEmpty('목록을 불러오지 못했습니다.');
    } finally {
      restore();
    }
  }

  $codeStatusFilter.addEventListener('change', renderCodes);
  $codeSearch.addEventListener('input', renderCodes);
  $refreshCodes.addEventListener('click', loadCodes);
  $refreshPending.addEventListener('click', loadPending);

  /* ─────────────────────────── 의뢰 승인 모달 ───────────────── */
  const issueModalEl = document.querySelector('#ucsIssueModal');
  const issueModal   = () => bootstrap.Modal.getOrCreateInstance(issueModalEl);

  const $issReqId     = document.querySelector('#issReqId');
  const $issRequester = document.querySelector('#issRequester');
  const $issReason    = document.querySelector('#issReason');
  const $issDesired   = document.querySelector('#issDesired');
  const $issPrefix    = document.querySelector('#issPrefix');
  const $issIssuedTo  = document.querySelector('#issIssuedTo');
  const $issApprover  = document.querySelector('#issApprover');
  const $issPreview   = document.querySelector('#issPreview');
  const $issNextBase  = document.querySelector('#issNextBase');
  const $issConfirm   = document.querySelector('#issConfirmBtn');

  let currentReq = null;
  let nextBaseCode = '??';

  async function refreshNextBase() {
    try {
      const r = await UCS.api.get('/api/codes/peek', { n: 1 });
      nextBaseCode = (r.next && r.next[0] && r.next[0].code) || '??';
    } catch (_) {
      nextBaseCode = '??';
    }
  }

  function updateIssuePreview() {
    const p = ($issPrefix.value || '').toUpperCase();
    $issPreview.textContent = `${p || '---'}-${nextBaseCode}`;
    $issNextBase.textContent = nextBaseCode;
  }

  $issPrefix.addEventListener('input', updateIssuePreview);

  async function openIssueModal(req) {
    currentReq = req;
    $issReqId.textContent     = req.id;
    $issRequester.textContent = req.requester;
    $issReason.textContent    = req.reason || '—';
    $issDesired.textContent   = req.desired_prefix || '—';
    $issPrefix.value     = req.desired_prefix || '';
    $issIssuedTo.value   = '';
    $issApprover.value   = '';
    await refreshNextBase();
    updateIssuePreview();
    issueModal().show();
    setTimeout(() => $issPrefix.focus(), 250);
  }

  $issConfirm.addEventListener('click', async () => {
    const prefix = ($issPrefix.value || '').trim().toUpperCase();
    if (!/^[A-Z]{1,16}$/.test(prefix)) {
      UCS.toast.warning('Prefix는 영문 1~16자여야 합니다.');
      $issPrefix.focus();
      return;
    }
    if (!currentReq) return;

    const restore = UCS.loading.start($issConfirm);
    try {
      const res = await UCS.api.post(`/api/codes/issue/${currentReq.id}`, {
        prefix,
        issued_to: $issIssuedTo.value.trim() || null,
        approver:  $issApprover.value.trim() || null,
      });
      UCS.toast.success(`발급 완료 · ${res.full_code}`);
      issueModal().hide();
      // 새로고침
      await Promise.all([loadPending(), loadCodes(), loadStats(), refreshNextBase()]);
    } catch (err) {
      UCS.toast.danger(`발급 실패: ${err.message}`);
    } finally {
      restore();
    }
  });

  /* ─────────────────────────── 강제 수기 채번 모달 ──────────── */
  const forceModalEl = document.querySelector('#ucsForceModal');
  const forceModal   = () => bootstrap.Modal.getOrCreateInstance(forceModalEl);

  const $frcBase     = document.querySelector('#frcBase');
  const $frcPrefix   = document.querySelector('#frcPrefix');
  const $frcReason   = document.querySelector('#frcReason');
  const $frcApprover = document.querySelector('#frcApprover');
  const $frcPreview  = document.querySelector('#frcPreview');
  const $frcConfirm  = document.querySelector('#frcConfirmBtn');

  // base는 영문 또는 숫자 2자리 → custom 변환 (Prefix와 규칙이 다름)
  $frcBase.addEventListener('input', (e) => {
    const cleaned = (e.target.value || '')
      .replace(/[^A-Za-z0-9]/g, '')
      .toUpperCase()
      .slice(0, 2);
    if (e.target.value !== cleaned) e.target.value = cleaned;
    updateForcePreview();
  });
  $frcPrefix.addEventListener('input', updateForcePreview);

  function updateForcePreview() {
    const p = ($frcPrefix.value || '').toUpperCase() || '---';
    const b = ($frcBase.value   || '').toUpperCase() || 'XX';
    $frcPreview.textContent = `${p}-${b}`;
  }

  document.querySelector('#forceIssueOpenBtn').addEventListener('click', () => {
    $frcBase.value = '';
    $frcPrefix.value = '';
    $frcReason.value = '';
    $frcApprover.value = '';
    updateForcePreview();
    forceModal().show();
    setTimeout(() => $frcBase.focus(), 250);
  });

  $frcConfirm.addEventListener('click', async () => {
    const base   = ($frcBase.value   || '').trim().toUpperCase();
    const prefix = ($frcPrefix.value || '').trim().toUpperCase();
    if (base.length !== 2) {
      UCS.toast.warning('Base 코드는 2자리여야 합니다.');
      $frcBase.focus(); return;
    }
    if (!/^[A-Z]{1,16}$/.test(prefix)) {
      UCS.toast.warning('Prefix는 영문 1~16자여야 합니다.');
      $frcPrefix.focus(); return;
    }

    const restore = UCS.loading.start($frcConfirm);
    try {
      const res = await UCS.api.post('/api/codes/force', {
        base_code: base,
        prefix,
        reason:    $frcReason.value.trim() || null,
        approver:  $frcApprover.value.trim() || null,
      });
      UCS.toast.success(`강제 발급 완료 · ${res.full_code}`);
      forceModal().hide();
      await Promise.all([loadCodes(), loadStats(), refreshNextBase()]);
    } catch (err) {
      UCS.toast.danger(`강제 발급 실패: ${err.message}`);
    } finally {
      restore();
    }
  });

  /* ─────────────────────────── 파기 모달 (§5.5) ─────────────── */
  const revokeModalEl = document.querySelector('#ucsRevokeModal');
  const revokeModal   = () => bootstrap.Modal.getOrCreateInstance(revokeModalEl);

  const $rvkCode    = document.querySelector('#ucsRevokeCode');
  const $rvkConfirm = document.querySelector('#ucsRevokeConfirmBtn');
  let pendingRevoke = null;

  function openRevokeModal(rec) {
    pendingRevoke = rec;
    $rvkCode.textContent = rec.full_code || rec.code;
    revokeModal().show();
  }

  $rvkConfirm.addEventListener('click', async () => {
    if (!pendingRevoke) return;
    const code = pendingRevoke.code;          // base code 사용 (full도 허용되지만 명확)
    const restore = UCS.loading.start($rvkConfirm);
    try {
      const res = await UCS.api.post(`/api/codes/revoke/${encodeURIComponent(code)}`);
      UCS.toast.success(
        `파기 완료 · ${pendingRevoke.full_code || code} → score ${res.score} 제자리 복귀`
      );
      revokeModal().hide();
      pendingRevoke = null;
      await Promise.all([loadCodes(), loadStats(), refreshNextBase()]);
    } catch (err) {
      UCS.toast.danger(`파기 실패: ${err.message}`);
    } finally {
      restore();
    }
  });

  /* ─────────────────────────── 초기 로드 ────────────────────── */
  document.addEventListener('DOMContentLoaded', async () => {
    UCS.prefix.bind();
    await Promise.all([loadStats(), loadPending(), loadCodes(), refreshNextBase()]);
  });
})();
