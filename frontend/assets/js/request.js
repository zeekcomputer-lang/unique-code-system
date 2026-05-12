/* =========================================================
 * request.html 전용 로직
 * - 의뢰 폼 제출 (§5.3 로딩 / §5.4 Toast)
 * - 의뢰 목록 조회/필터
 * - 실시간 미리보기 (§5.2)
 * ========================================================= */
(function () {
  'use strict';

  /* ───────── DOM 참조 ───────── */
  const $form        = document.querySelector('#requestForm');
  const $requester   = document.querySelector('#reqRequester');
  const $reason      = document.querySelector('#reqReason');
  const $prefix      = document.querySelector('#reqPrefix');
  const $note        = document.querySelector('#reqNote');
  const $preview     = document.querySelector('#reqPreview');
  const $submitBtn   = document.querySelector('#submitBtn');
  const $resetBtn    = document.querySelector('#resetBtn');

  const $tbody       = document.querySelector('#reqTableBody');
  const $countLabel  = document.querySelector('#reqCount');
  const $statusSel   = document.querySelector('#statusFilter');
  const $refreshBtn  = document.querySelector('#refreshListBtn');

  /* ───────── 미리보기 (§5.2) ───────── */
  function renderPreview() {
    const requester = ($requester.value || '').trim() || '[의뢰자]';
    const pfx = ($prefix.value || '').toUpperCase() || '[PREFIX]';
    $preview.textContent = `${requester} · ${pfx}`;
  }
  [$requester, $prefix].forEach((el) => el.addEventListener('input', renderPreview));

  /* ───────── 상태 뱃지 렌더링 ───────── */
  function statusBadge(status) {
    const map = {
      PENDING:  { cls: 'bg-warning-subtle text-warning border border-warning-subtle',     label: 'PENDING'  },
      APPROVED: { cls: 'bg-success-subtle text-success border border-success-subtle',     label: 'APPROVED' },
      REJECTED: { cls: 'bg-danger-subtle text-danger border border-danger-subtle',        label: 'REJECTED' },
    };
    const v = map[status] || { cls: 'bg-secondary-subtle text-secondary border border-secondary-subtle', label: status };
    const span = document.createElement('span');
    span.className =
      `badge rounded-1 px-2 py-1 fw-bold text-uppercase ${v.cls}`;
    span.style.fontSize = '11px';
    span.style.letterSpacing = '.04em';
    span.textContent = v.label;
    return span;
  }

  /* ───────── 목록 렌더링 ───────── */
  function renderEmpty(message = '의뢰가 없습니다.') {
    $tbody.innerHTML = '';
    const tr = document.createElement('tr');
    const td = document.createElement('td');
    td.colSpan = 6;
    td.className = 'text-center text-muted py-5';
    td.innerHTML = `<i class="fa-solid fa-inbox fa-2x mb-2 d-block"></i>${message}`;
    tr.appendChild(td);
    $tbody.appendChild(tr);
  }

  function renderRow(rec) {
    const tr = document.createElement('tr');

    // ID
    const tdId = document.createElement('td');
    tdId.className = 'px-3 py-2';
    const idSpan = document.createElement('span');
    idSpan.className = 'ucs-code ucs-code-primary';
    idSpan.textContent = rec.id;
    tdId.appendChild(idSpan);
    tr.appendChild(tdId);

    // 의뢰자
    const tdReq = document.createElement('td');
    tdReq.className = 'px-3 py-2 fw-medium';
    tdReq.textContent = rec.requester;
    tr.appendChild(tdReq);

    // 사유
    const tdReason = document.createElement('td');
    tdReason.className = 'px-3 py-2 text-muted small';
    tdReason.style.maxWidth = '240px';
    tdReason.style.whiteSpace = 'nowrap';
    tdReason.style.overflow = 'hidden';
    tdReason.style.textOverflow = 'ellipsis';
    tdReason.title = rec.reason || '';
    tdReason.textContent = rec.reason || '';
    tr.appendChild(tdReason);

    // 상태
    const tdStatus = document.createElement('td');
    tdStatus.className = 'px-3 py-2';
    tdStatus.appendChild(statusBadge(rec.status));
    tr.appendChild(tdStatus);

    // 발급 코드
    const tdCode = document.createElement('td');
    tdCode.className = 'px-3 py-2';
    if (rec.issued_full_code) {
      const c = document.createElement('span');
      c.className = 'ucs-code ucs-code-primary';
      c.textContent = rec.issued_full_code;
      tdCode.appendChild(c);
    } else {
      tdCode.innerHTML = '<span class="text-muted small">—</span>';
    }
    tr.appendChild(tdCode);

    // 접수일시
    const tdDate = document.createElement('td');
    tdDate.className = 'px-3 py-2 text-muted small';
    tdDate.textContent = UCS.format.dateTime(rec.created_at);
    tr.appendChild(tdDate);

    return tr;
  }

  async function loadList() {
    const restore = UCS.loading.start($refreshBtn);
    try {
      const status = $statusSel.value;
      const list = await UCS.api.get('/api/requests', status ? { status } : undefined);

      $countLabel.textContent = `(${list.length})`;

      if (!list.length) {
        renderEmpty(status ? `${status} 상태인 의뢰가 없습니다.` : '의뢰가 없습니다.');
        return;
      }
      $tbody.innerHTML = '';
      list.forEach((rec) => $tbody.appendChild(renderRow(rec)));
    } catch (err) {
      UCS.toast.danger(`목록 조회 실패: ${err.message}`);
      renderEmpty('목록을 불러오지 못했습니다.');
    } finally {
      restore();
    }
  }

  /* ───────── 폼 제출 (§5.3 / §5.4) ───────── */
  $form.addEventListener('submit', async (e) => {
    e.preventDefault();

    // 클라이언트 검증
    const requester = $requester.value.trim();
    const reason    = $reason.value.trim();
    if (!requester) {
      UCS.toast.warning('의뢰자를 입력하세요.');
      $requester.focus();
      return;
    }
    if (!reason) {
      UCS.toast.warning('사유를 입력하세요.');
      $reason.focus();
      return;
    }

    const payload = {
      requester,
      reason,
      desired_prefix: $prefix.value.trim() || null,
      note: $note.value.trim() || null,
    };

    const restore = UCS.loading.start($submitBtn);
    try {
      const rec = await UCS.api.post('/api/requests', payload);
      UCS.toast.success(`의뢰 접수 완료 · ${rec.id}`);
      $form.reset();
      renderPreview();
      // 최신 목록 갱신 (상태 필터가 PENDING 외이면 그대로 적용)
      await loadList();
    } catch (err) {
      UCS.toast.danger(`의뢰 접수 실패: ${err.message}`);
    } finally {
      restore();
    }
  });

  $resetBtn.addEventListener('click', () => {
    // form.reset 이후 미리보기 동기화
    setTimeout(renderPreview, 0);
  });

  $statusSel.addEventListener('change', loadList);
  $refreshBtn.addEventListener('click', loadList);

  /* ───────── 초기화 ───────── */
  document.addEventListener('DOMContentLoaded', () => {
    UCS.prefix.bind(); // 안전망 (common.js가 이미 바인딩하지만 한 번 더)
    renderPreview();
    loadList();
  });
})();
