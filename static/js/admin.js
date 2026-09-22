/**
 * IT Helpdesk Command Center - Admin Dashboard JavaScript
 * Handles real-time polling, Chart.js graphs, Tab switching, Search filtering, Modal dialogs & Excel exports.
 */

let CURRENT_ROLE = window.CURRENT_ROLE || '';
let allTickets = [];
let dbDepts = [];
let allITStaff = [];
let filteredTickets = [];
let charts = { line: null, dept: null, itKpi: null };
let currentPage = 1;
const rowsPerPage = 10;

function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    if (sidebar) sidebar.classList.toggle('-ml-64');
}

function toggleTokenVisibility() {
    const tokenInput = document.getElementById('cfgBotToken');
    const eyeIcon = document.getElementById('tokenEyeIcon');
    
    if (tokenInput && eyeIcon) {
        if (tokenInput.type === 'password') {
            tokenInput.type = 'text';
            eyeIcon.classList.remove('fa-eye');
            eyeIcon.classList.add('fa-eye-slash');
        } else {
            tokenInput.type = 'password';
            eyeIcon.classList.remove('fa-eye-slash');
            eyeIcon.classList.add('fa-eye');
        }
    }
}

function switchTab(tabId) {
    document.querySelectorAll('.admin-tab').forEach(el => el.classList.add('hidden'));
    
    const targetTab = document.getElementById('tab-' + tabId);
    if (targetTab) targetTab.classList.remove('hidden');
    
    document.querySelectorAll('.sidebar-item').forEach(el => el.classList.remove('active', 'bg-slate-800'));
    const activeBtn = document.getElementById('menu-' + tabId);
    if (activeBtn) activeBtn.classList.add('active');
    
    let titleText = tabId.toUpperCase();
    if (tabId === 'settings') titleText = 'QUẢN TRỊ HỆ THỐNG';
    if (tabId === 'depts') titleText = 'QUẢN LÝ PHÒNG BAN';
    const headerTitle = document.getElementById('header-title');
    if (headerTitle) headerTitle.innerText = titleText;
    
    const filters = document.getElementById('dashboard-filters');
    if (filters) filters.style.display = (tabId === 'dashboard') ? 'flex' : 'none';
    
    localStorage.setItem('activeTab', tabId);
}

window.onload = () => {
    try {
        allTickets = JSON.parse(document.getElementById('tickets-data')?.textContent || '[]');
        dbDepts = JSON.parse(document.getElementById('departments-data')?.textContent || '[]');
        allITStaff = JSON.parse(document.getElementById('it-staff-data')?.textContent || '[]');
    } catch(e) {}

    const searchInput = document.getElementById('searchInput');
    if (searchInput) searchInput.value = '';

    let savedTab = localStorage.getItem('activeTab') || 'dashboard';
    
    if (CURRENT_ROLE === 'admin') {
        if (savedTab === 'dashboard') savedTab = 'depts';
    }
    
    if (CURRENT_ROLE === 'manager') {
        savedTab = 'dashboard';
    }
    
    switchTab(savedTab);
    
    const ySel = document.getElementById('yearFilter');
    if (ySel) {
        const yrs = [...new Set(allTickets.map(t => t.created_at.substring(0, 4)))].filter(Boolean).sort().reverse();
        if (yrs.length === 0) yrs.push(new Date().getFullYear().toString());
        ySel.innerHTML = '<option value="ALL">Tất cả năm</option>';
        yrs.forEach(y => ySel.appendChild(new Option("Năm " + y, y)));
        ySel.value = 'ALL';
    }
    
    const dSel = document.getElementById('deptFilter');
    if (dSel) {
        dSel.innerHTML = '<option value="ALL">Tất cả phòng ban</option>';
        dbDepts.forEach(d => dSel.appendChild(new Option(d, d)));
    }
    
    const itSel = document.getElementById('itFilter');
    if (itSel) {
        itSel.innerHTML = '<option value="ALL">Tất cả IT</option>';
        const uniqueITs = [...new Set(allTickets.map(t => t.it_name).filter(Boolean))].sort();
        uniqueITs.forEach(it => itSel.appendChild(new Option(it, it)));
    }

    const monthFilter = document.getElementById('monthFilter');
    if (monthFilter) monthFilter.value = 'ALL';
    
    if (['superadmin', 'manager'].includes(CURRENT_ROLE)) {
        applyFilters();
    }

    startLiveClock();
};

async function manualRefresh() {
    const icon = document.getElementById('refreshSpinIcon');
    if (icon) icon.classList.add('fa-spin');
    await fetchRealtimeData(true);
    if (icon) setTimeout(() => icon.classList.remove('fa-spin'), 500);
}

function startLiveClock() {
    let botTimeParts = window.BOT_TIME_PARTS || null;
    if (!botTimeParts) {
        try { botTimeParts = JSON.parse(document.getElementById('bot-time-data')?.textContent || 'null'); } catch(e) {}
    }
    if (!botTimeParts) return;
    
    let botClock = new Date(botTimeParts.year, botTimeParts.month, botTimeParts.day, botTimeParts.hour, botTimeParts.minute, botTimeParts.second);

    setInterval(() => {
        botClock.setSeconds(botClock.getSeconds() + 1);
        const dd = String(botClock.getDate()).padStart(2, '0');
        const mm = String(botClock.getMonth() + 1).padStart(2, '0');
        const yyyy = botClock.getFullYear();
        const hh = String(botClock.getHours()).padStart(2, '0');
        const min = String(botClock.getMinutes()).padStart(2, '0');
        const ss = String(botClock.getSeconds()).padStart(2, '0');
        const timeEl = document.getElementById('liveBotTime');
        if (timeEl) timeEl.innerText = `${hh}:${min}:${ss} - ${dd}/${mm}/${yyyy}`;
    }, 1000);
}

function syncLocalTime() {
    const now = new Date();
    now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
    const cfgTime = document.getElementById('cfgCustomTime');
    if (cfgTime) cfgTime.value = now.toISOString().slice(0, 16);
}

async function fetchRealtimeData(forceRefresh = false) {
    try {
        const res = await fetch('/api/data');
        const data = await res.json();
        if (data.it_staff) allITStaff = data.it_staff;
        if (forceRefresh || JSON.stringify(data.tickets) !== JSON.stringify(allTickets)) {
            allTickets = data.tickets; 
            if (['superadmin', 'manager'].includes(CURRENT_ROLE)) {
                applyFilters();
            }
        }
    } catch(e) {}
}

function applyFilters() {
    const ySel = document.getElementById('yearFilter');
    const mSel = document.getElementById('monthFilter');
    const dSel = document.getElementById('deptFilter');
    const itSel = document.getElementById('itFilter');
    const searchInput = document.getElementById('searchInput');

    const y = ySel ? ySel.value : 'ALL';
    const m = mSel ? mSel.value : 'ALL';
    const d = dSel ? dSel.value : 'ALL';
    const it = itSel ? itSel.value : 'ALL';
    const q = searchInput ? searchInput.value.toLowerCase().trim() : '';

    const kpiMonthText = document.getElementById('kpiMonthText');
    if (kpiMonthText) kpiMonthText.innerText = `(${d!=='ALL'?`[${d}] `:''}${y==='ALL'?'Toàn TG':(m==='ALL'?`Năm ${y}`:`T${m}/${y}`)})`;
    
    filteredTickets = allTickets.filter(t => {
        if (y !== 'ALL' && t.created_at.substring(0, 4) !== y) return false;
        if (m !== 'ALL' && t.created_at.substring(5, 7) !== m) return false;
        if (d !== 'ALL' && t.dept !== d) return false;
        
        if (it !== 'ALL' && t.it_name !== it && !(t.support_it_names && t.support_it_names.includes(it))) return false;
        
        if (q) {
            const searchStr = `#${t.id} ${t.user_name} ${t.issue} ${t.it_name || ''} ${t.support_it_names || ''}`.toLowerCase();
            if (!searchStr.includes(q)) return false;
        }
        
        return true;
    });
    currentPage = 1; updateKPIs(); renderTable(); drawCharts();
}

function updateKPIs() {
    let newT = 0, procT = 0, doneT = 0;
    filteredTickets.forEach(t => {
        if (t.status === 'Mới') newT++;
        else if (t.status === 'Đang xử lý') procT++;
        else if (t.status === 'Hoàn thành') doneT++;
    });
    const kpiTotal = document.getElementById('kpiTotal');
    if (kpiTotal) {
        kpiTotal.innerText = filteredTickets.length;
        document.getElementById('kpiNew').innerText = newT;
        document.getElementById('kpiPending').innerText = procT;
        document.getElementById('kpiCompleted').innerText = doneT;
    }
}

function changePage(dir) {
    const total = Math.ceil(filteredTickets.length / rowsPerPage);
    currentPage += dir;
    if (currentPage < 1) currentPage = 1; if (currentPage > total) currentPage = total; if (total === 0) currentPage = 1;
    renderTable();
}

function renderStars(rating) {
    if (!rating) return '<span class="text-slate-300 italic text-[10px]">Chưa đánh giá</span>';
    let stars = '';
    for (let i = 1; i <= 5; i++) stars += `<i class="fa-solid fa-star ${i <= rating ? 'star-filled' : 'star-empty'} text-[10px]"></i>`;
    return stars;
}

function renderTable() {
    const tbody = document.getElementById('ticketTableBody');
    if (!tbody) return;
    const noData = document.getElementById('noDataMsg');
    tbody.innerHTML = '';
    const tRows = filteredTickets.length;
    if (tRows === 0) {
        if (noData) noData.classList.remove('hidden');
        ['pageStart','pageEnd','pageTotal'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.innerText = '0';
        });
        return;
    }
    if (noData) noData.classList.add('hidden');
    const start = (currentPage - 1) * rowsPerPage;
    const end = Math.min(start + rowsPerPage, tRows);
    
    const pStart = document.getElementById('pageStart');
    const pEnd = document.getElementById('pageEnd');
    const pTotal = document.getElementById('pageTotal');
    const pInd = document.getElementById('pageIndicator');
    
    if (pStart) pStart.innerText = start + 1;
    if (pEnd) pEnd.innerText = end;
    if (pTotal) pTotal.innerText = tRows;
    if (pInd) pInd.innerText = `Trang ${currentPage} / ${Math.ceil(tRows / rowsPerPage)}`;

    filteredTickets.slice(start, end).forEach(t => {
        let sKey = t.status.substring(0, 4);
        let mainItStr = t.it_name ? `<span class="text-[10px] font-black bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded shadow-sm">C: ${t.it_name}</span>` : '<span class="text-[10px] font-bold text-slate-400 border border-slate-200 px-2 py-0.5 rounded-full bg-slate-50">Chờ nhận</span>';
        let supItStr = t.support_it_names ? `<br><span class="text-[9px] font-bold text-emerald-600 mt-1 inline-block bg-emerald-50 px-1.5 rounded">H/t: ${t.support_it_names}</span>` : '';
        
        let actionBtns = '';
        if (CURRENT_ROLE !== 'manager') {
            actionBtns = `
                <div class="hidden group-hover:flex justify-end gap-2 animate-fadeIn">
                    <button onclick="openEditTicket(${t.id})" class="px-2 py-1 bg-slate-100 text-indigo-600 rounded hover:bg-indigo-100 transition" title="Sửa Ticket"><i class="fa-solid fa-pen"></i></button>
                    <button onclick="deleteTicket(${t.id})" class="px-2 py-1 bg-slate-100 text-rose-500 rounded hover:bg-rose-100 transition" title="Xóa Ticket"><i class="fa-solid fa-trash"></i></button>
                </div>`;
        }

        let timeStr = `<span class="text-[10px] text-slate-400 font-bold block mb-1 group-hover:hidden">Tạo: ${t.created_at.substring(8, 16)}${t.completed_at ? `<br><span class="text-emerald-600 font-black">Xong: ${t.completed_at.substring(8, 16)}</span>` : ''}</span>`;

        tbody.innerHTML += `
            <tr class="hover:bg-slate-50 transition-colors group">
                <td class="p-4 font-bold text-indigo-600">#${t.id}</td>
                <td class="p-4"><b>${t.user_name}</b><br><small class="text-slate-400 uppercase text-[9px] font-bold">${t.dept}</small></td>
                <td class="p-4 text-slate-500 text-xs italic max-w-xs truncate" title="${t.issue}">${t.issue}</td>
                <td class="p-4 text-center"><span class="status-badge status-${sKey}">${t.status}</span></td>
                <td class="p-4 text-center leading-tight">${mainItStr}${supItStr}</td>
                <td class="p-4 text-center">${renderStars(t.rating)}</td>
                <td class="p-4 text-right">
                    ${timeStr}
                    ${actionBtns}
                </td>
            </tr>`;
    });
}

function formatDateTimeLocal(dateStr) {
    if (!dateStr) return '';
    const d = new Date(dateStr.replace(' ', 'T'));
    if (isNaN(d.getTime())) return '';
    d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
    return d.toISOString().slice(0, 16);
}

function getNowLocalIso() {
    const d = new Date();
    d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
    return d.toISOString().slice(0, 16);
}

function openEditTicket(id) {
    const t = allTickets.find(x => x.id === id);
    if (!t) return;
    document.getElementById('editTid').innerText = t.id;
    document.getElementById('editIssue').value = t.issue;
    document.getElementById('editStatus').value = t.status;
    document.getElementById('editSupNames').value = t.support_it_names || '';
    
    document.getElementById('editCreatedAt').value = formatDateTimeLocal(t.created_at);
    document.getElementById('editCompletedAt').value = formatDateTimeLocal(t.completed_at);
    
    const sel = document.getElementById('editMainIt');
    sel.innerHTML = '<option value="">-- Trống --</option>';
    
    if (allITStaff && allITStaff.length > 0) {
        allITStaff.forEach(it => {
            sel.appendChild(new Option(it.it_real_name, it.it_id));
        });
    } else {
        const itItems = document.querySelectorAll('.it-item');
        itItems.forEach(item => {
            const it_id = item.getAttribute('data-id');
            const name = item.getAttribute('data-name');
            if (it_id && name) {
                sel.appendChild(new Option(name, it_id));
            }
        });
    }

    if (t.it_id) {
        sel.value = t.it_id;
    } else if (t.it_name) {
        for (let i = 0; i < sel.options.length; i++) {
            if (sel.options[i].text === t.it_name) {
                sel.selectedIndex = i;
                break;
            }
        }
    } else {
        sel.value = '';
    }
    
    const modal = document.getElementById('editTicketModal');
    const content = document.getElementById('modalContent');
    if (modal && content) {
        modal.classList.remove('hidden');
        setTimeout(() => { content.classList.remove('scale-95', 'opacity-0'); }, 10);
    }
}

function closeModal() { 
    const modal = document.getElementById('editTicketModal');
    const content = document.getElementById('modalContent');
    if (modal && content) {
        content.classList.add('scale-95', 'opacity-0');
        setTimeout(() => { modal.classList.add('hidden'); }, 300);
    }
}

async function submitEditTicket() {
    const id = document.getElementById('editTid').innerText;
    const itSel = document.getElementById('editMainIt');
    const data = {
        id: parseInt(id),
        issue: document.getElementById('editIssue').value,
        status: document.getElementById('editStatus').value,
        it_id: itSel.value ? parseInt(itSel.value) : null,
        it_name: itSel.value ? itSel.options[itSel.selectedIndex].text : null,
        support_it_names: document.getElementById('editSupNames').value,
        created_at: document.getElementById('editCreatedAt').value,
        completed_at: document.getElementById('editCompletedAt').value
    };
    const res = await fetch('/api/update_ticket', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)});
    const resData = await res.json();
    if (!resData.success) alert(resData.error);
    closeModal(); fetchRealtimeData();
}

function openAddTicketModal() {
    document.getElementById('addTicketUserName').value = '';
    document.getElementById('addTicketDept').value = '';
    document.getElementById('addTicketIssue').value = '';
    document.getElementById('addTicketStatus').value = 'Hoàn thành';
    document.getElementById('addTicketRating').value = '5';
    
    const nowIso = getNowLocalIso();
    document.getElementById('addTicketCreatedAt').value = nowIso;
    document.getElementById('addTicketCompletedAt').value = nowIso;
    
    const datalist = document.getElementById('deptsList');
    datalist.innerHTML = '';
    if (dbDepts && dbDepts.length > 0) {
        dbDepts.forEach(d => {
            const opt = document.createElement('option');
            opt.value = typeof d === 'string' ? d : d.name;
            datalist.appendChild(opt);
        });
    }
    
    const itSel = document.getElementById('addTicketItId');
    itSel.innerHTML = '<option value="">-- Chọn IT Phụ Trách --</option>';
    if (allITStaff && allITStaff.length > 0) {
        allITStaff.forEach(it => {
            itSel.appendChild(new Option(it.it_real_name, it.it_id));
        });
    }
    
    const modal = document.getElementById('addTicketModal');
    const content = document.getElementById('addTicketModalContent');
    if (modal && content) {
        modal.classList.remove('hidden');
        setTimeout(() => { content.classList.remove('scale-95', 'opacity-0'); }, 10);
    }
}

function closeAddTicketModal() {
    const modal = document.getElementById('addTicketModal');
    const content = document.getElementById('addTicketModalContent');
    if (modal && content) {
        content.classList.add('scale-95', 'opacity-0');
        setTimeout(() => { modal.classList.add('hidden'); }, 300);
    }
}

async function submitAddTicket() {
    const userName = document.getElementById('addTicketUserName').value.trim();
    const dept = document.getElementById('addTicketDept').value.trim();
    const issue = document.getElementById('addTicketIssue').value.trim();
    const itId = document.getElementById('addTicketItId').value;
    const status = document.getElementById('addTicketStatus').value;
    const rating = document.getElementById('addTicketRating').value;

    if (!userName || !dept || !issue) {
        alert("⚠️ Vui lòng điền đầy đủ Tên người yêu cầu, Phòng ban và Nội dung sự cố!");
        return;
    }

    const data = {
        user_name: userName,
        dept: dept,
        issue: issue,
        it_id: itId ? parseInt(itId) : null,
        status: status,
        rating: parseInt(rating),
        created_at: document.getElementById('addTicketCreatedAt').value,
        completed_at: document.getElementById('addTicketCompletedAt').value
    };

    const res = await fetch('/api/create_ticket', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data)
    });
    const resData = await res.json();
    if (!resData.success) {
        alert("❌ Lỗi: " + resData.error);
        return;
    }
    
    closeAddTicketModal();
    fetchRealtimeData(true);
}

async function deleteTicket(id) {
    if (confirm("Xóa sự cố #"+id+"? Cảnh báo: Việc này sẽ không thể hoàn tác!")) {
        const res = await fetch('/api/delete_ticket/'+id, {method: 'POST'});
        const resData = await res.json();
        if (!resData.success) alert(resData.error);
        fetchRealtimeData();
    }
}

function filterDeptsTable() {
    const q = (document.getElementById('deptSearchInput').value || '').toLowerCase().trim();
    document.querySelectorAll('#deptsTableBody .dept-row').forEach(row => {
        const name = row.querySelector('.dept-name').innerText.toLowerCase();
        row.style.display = name.includes(q) ? '' : 'none';
    });
}

function filterITList() {
    const q = (document.getElementById('itSearchInput').value || '').toLowerCase().trim();
    document.querySelectorAll('#itListContainer .it-item').forEach(item => {
        const name = (item.dataset.name || '').toLowerCase();
        const phone = (item.dataset.phone || '').toLowerCase();
        const id = (item.dataset.id || '').toString();
        item.style.display = (name.includes(q) || phone.includes(q) || id.includes(q)) ? 'flex' : 'none';
    });
}

function filterUserList() {
    const q = (document.getElementById('userSearchInput').value || '').toLowerCase().trim();
    document.querySelectorAll('#userListContainer .user-item').forEach(item => {
        const name = (item.dataset.name || '').toLowerCase();
        const dept = (item.dataset.dept || '').toLowerCase();
        const id = (item.dataset.id || '').toString();
        item.style.display = (name.includes(q) || dept.includes(q) || id.includes(q)) ? 'flex' : 'none';
    });
}

function openEditITModal(btn, argName, argPhone) {
    let id, name, phone;
    if (typeof btn === 'object' && btn !== null) {
        const item = btn.closest('.it-item');
        id = item.dataset.id;
        name = item.dataset.name;
        phone = item.dataset.phone;
    } else {
        id = btn; name = argName; phone = argPhone;
    }
    document.getElementById('editITId').value = id;
    document.getElementById('editITIdDisplay').innerText = id;
    document.getElementById('editITName').value = name;
    document.getElementById('editITPhone').value = phone;

    const modal = document.getElementById('editITModal');
    const content = document.getElementById('editITModalContent');
    if (modal && content) {
        modal.classList.remove('hidden');
        setTimeout(() => { content.classList.remove('scale-95', 'opacity-0'); }, 10);
    }
}

function closeEditITModal() {
    const modal = document.getElementById('editITModal');
    const content = document.getElementById('editITModalContent');
    if (modal && content) {
        content.classList.add('scale-95', 'opacity-0');
        setTimeout(() => { modal.classList.add('hidden'); }, 300);
    }
}

async function submitEditIT() {
    const id = parseInt(document.getElementById('editITId').value);
    const name = document.getElementById('editITName').value.trim();
    const phone = document.getElementById('editITPhone').value.trim();

    if (!name) return alert("Vui lòng nhập tên IT!");

    const res = await fetch('/api/update_it', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({id, name, phone})
    });
    const resData = await res.json();
    if (resData.success) {
        alert("✅ Đã cập nhật thông tin IT!");
        closeEditITModal();
        location.reload();
    } else {
        alert("❌ Lỗi: " + resData.error);
    }
}

function openEditUserModal(btn, argName, argDept) {
    let id, name, currentDept;
    if (typeof btn === 'object' && btn !== null) {
        const item = btn.closest('.user-item');
        id = item.dataset.id;
        name = item.dataset.name;
        currentDept = item.dataset.dept;
    } else {
        id = btn; name = argName; currentDept = argDept;
    }
    document.getElementById('editUserId').value = id;
    document.getElementById('editUserIdDisplay').value = id;
    document.getElementById('editUserName').value = name;

    const deptSel = document.getElementById('editUserDept');
    deptSel.innerHTML = '';
    
    let matchFound = false;
    dbDepts.forEach(d => {
        const opt = new Option(d, d);
        if (d === currentDept) matchFound = true;
        deptSel.appendChild(opt);
    });
    if (!matchFound && currentDept) {
        deptSel.appendChild(new Option(currentDept, currentDept));
    }
    deptSel.value = currentDept;

    const modal = document.getElementById('editUserModal');
    const content = document.getElementById('editUserModalContent');
    if (modal && content) {
        modal.classList.remove('hidden');
        setTimeout(() => { content.classList.remove('scale-95', 'opacity-0'); }, 10);
    }
}

function closeEditUserModal() {
    const modal = document.getElementById('editUserModal');
    const content = document.getElementById('editUserModalContent');
    if (modal && content) {
        content.classList.add('scale-95', 'opacity-0');
        setTimeout(() => { modal.classList.add('hidden'); }, 300);
    }
}

async function submitEditUser() {
    const id = parseInt(document.getElementById('editUserId').value);
    const name = document.getElementById('editUserName').value.trim();
    const dept = document.getElementById('editUserDept').value.trim();

    if (!name) return alert("Vui lòng nhập tên Khách hàng!");

    const res = await fetch('/api/update_user', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({id, name, dept})
    });
    const resData = await res.json();
    if (resData.success) {
        alert("✅ Đã cập nhật thông tin Khách hàng!");
        closeEditUserModal();
        location.reload();
    } else {
        alert("❌ Lỗi: " + resData.error);
    }
}

async function deleteIT(btn) {
    const id = (typeof btn === 'object' && btn !== null) ? (btn.dataset.id || btn.closest('.it-item').dataset.id) : btn;
    if (confirm("⚠️ Chắc chắn xóa IT này khỏi danh sách? Lịch sử công việc cũ sẽ vẫn được giữ trong Ticket.")) {
        const res = await fetch('/api/delete_it/'+id, {method: 'POST'});
        const resData = await res.json();
        if (resData.success) location.reload(); else alert(resData.error);
    }
}

async function deleteUser(btn) {
    const id = (typeof btn === 'object' && btn !== null) ? (btn.dataset.id || btn.closest('.user-item').dataset.id) : btn;
    if (confirm("⚠️ Chắc chắn xóa Khách hàng này?")) {
        const res = await fetch('/api/delete_user/'+id, {method: 'POST'});
        const resData = await res.json();
        if (resData.success) location.reload(); else alert(resData.error);
    }
}

function drawCharts() {
    Object.values(charts).forEach(c => { if (c) c.destroy() });
    
    const deptChartEl = document.getElementById('deptChart');
    if (!deptChartEl) return;
    
    const data = filteredTickets;
    const ySel = document.getElementById('yearFilter');
    const mSel = document.getElementById('monthFilter');
    const y = ySel ? ySel.value : 'ALL';
    const m = mSel ? mSel.value : 'ALL';

    const dC = {}; data.forEach(t => dC[t.dept] = (dC[t.dept] || 0) + 1);
    charts.dept = new Chart(deptChartEl, {
        type: 'doughnut', data: { labels: Object.keys(dC), datasets: [{ data: Object.values(dC), backgroundColor: ['#4f46e5', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981'], borderWidth: 0 }] },
        options: { responsive: true, maintainAspectRatio: false, cutout: '75%', plugins: { legend: { display: false } } }
    });

    let labels = []; let counts = [];
    if (y === 'ALL') {
        const chartTitle = document.getElementById('chartTitleTime');
        if (chartTitle) chartTitle.innerText = "LƯU LƯỢNG THEO NĂM";
        labels = [...new Set(allTickets.map(t => t.created_at.substring(0, 4)))].sort();
        if (labels.length === 0) labels = [new Date().getFullYear().toString()];
        counts = labels.map(yr => data.filter(t => t.created_at.startsWith(yr)).length);
    } else if (m === 'ALL') {
        const chartTitle = document.getElementById('chartTitleTime');
        if (chartTitle) chartTitle.innerText = "LƯU LƯỢNG NĂM " + y;
        labels = ['T1','T2','T3','T4','T5','T6','T7','T8','T9','T10','T11','T12'];
        counts = Array(12).fill(0);
        data.forEach(t => counts[parseInt(t.created_at.substring(5,7))-1]++);
    } else {
        const chartTitle = document.getElementById('chartTitleTime');
        if (chartTitle) chartTitle.innerText = `LƯU LƯỢNG THÁNG ${m}/${y}`;
        const daysInMonth = new Date(y, m, 0).getDate();
        labels = Array.from({length: daysInMonth}, (_, i) => (i + 1).toString());
        counts = Array(daysInMonth).fill(0);
        data.forEach(t => {
            const dIdx = parseInt(t.created_at.substring(8, 10)) - 1;
            if (dIdx >= 0 && dIdx < daysInMonth) counts[dIdx]++;
        });
    }
    const ctxL = document.getElementById('lineChart')?.getContext('2d');
    if (ctxL) {
        let grad = ctxL.createLinearGradient(0,0,0,300); grad.addColorStop(0, 'rgba(79, 70, 229, 0.2)'); grad.addColorStop(1, 'rgba(79, 70, 229, 0)');
        charts.line = new Chart(ctxL, {
            type: 'line', data: { labels: labels, datasets: [{ label: 'Số sự cố', data: counts, borderColor: '#4f46e5', backgroundColor: grad, fill: true, tension: 0.4, borderWidth: 3, pointRadius: 3 }] },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { grid: { display: false } }, y: { beginAtZero: true, ticks: { stepSize: 1 } } } }
        });
    }

    const iC = {}; 
    data.forEach(t => { 
        if (t.it_name) iC[t.it_name] = (iC[t.it_name] || 0) + 1; 
        if (t.support_it_names) {
            t.support_it_names.split(',').forEach(s_name => {
                let name = s_name.trim();
                if (name) iC[name] = (iC[name] || 0) + 1;
            });
        }
    });
    const itKpiEl = document.getElementById('itKpiChart');
    if (itKpiEl) {
        charts.itKpi = new Chart(itKpiEl, {
            type: 'bar', data: { labels: Object.keys(iC), datasets: [{ data: Object.values(iC), backgroundColor: '#4f46e5', borderRadius: 8, barThickness: 20 }] },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } } }
        });
    }
}

async function saveBotSettings() {
    const token = document.getElementById('cfgBotToken').value;
    const groupId = document.getElementById('cfgGroupId').value;
    const customTime = document.getElementById('cfgCustomTime').value;
    
    if (!token || !groupId) return alert("Vui lòng điền đầy đủ Token và ID Nhóm!");

    try {
        const res = await fetch('/api/save_settings', { 
            method: 'POST', 
            headers: {'Content-Type': 'application/json'}, 
            body: JSON.stringify({
                bot_token: token, 
                group_id: groupId,
                custom_time: customTime
            }) 
        });
        const data = await res.json(); 
        if (data.success) {
            alert("✅ Lưu cấu hình thành công!");
            location.reload();
        } else {
            alert("❌ Lỗi: " + data.error);
        }
    } catch(e) { alert("Lỗi kết nối tới máy chủ!"); }
}

async function resetAdminPassword(username) {
    const newPwd = prompt(`Nhập mật khẩu mới cho [${username}]:`);
    if (!newPwd) return; 
    try {
        const res = await fetch('/api/admin_reset_password', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({username: username, new_password: newPwd}) });
        const data = await res.json(); if (data.success) alert(`✅ Đã đổi mật khẩu cho [${username}]!`); else alert("❌ " + data.error);
    } catch(e) { alert("Lỗi kết nối!"); }
}

async function deleteAdmin(id, username) {
    if (!confirm(`⚠️ Bạn có chắc chắn muốn xóa vĩnh viễn tài khoản [${username}] không?`)) return;
    try {
        const res = await fetch(`/api/delete_admin/${id}`, {method: 'POST'});
        const data = await res.json(); if (data.success) location.reload(); else alert("❌ " + data.error);
    } catch(e) { alert("Lỗi kết nối!"); }
}

async function addAdmin() {
    const u = document.getElementById('newAdminUser').value; 
    const p = document.getElementById('newAdminPwd').value;
    const r = document.getElementById('newAdminRole').value;
    if (!u || !p) return alert("Vui lòng nhập đủ thông tin!");
    try {
        const res = await fetch('/api/add_admin', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({username: u.trim(), password: p, role: r}) });
        const data = await res.json(); if (data.success) location.reload(); else alert("❌ " + data.error);
    } catch(e) { alert("Lỗi kết nối!"); }
}

async function addDept() {
    const name = prompt("Tên phòng:"); if (!name) return;
    try {
        const res = await fetch('/api/add_department', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({dept_name: name.trim()}) });
        const data = await res.json(); if (data.success) location.reload(); else alert(data.error);
    } catch(e) { alert("Lỗi kết nối!"); }
}

async function deleteDept(id, name) {
    if (!confirm(`⚠️ Xóa vĩnh viễn phòng [${name}]?`)) return;
    await fetch(`/api/delete_department/${id}`, {method: 'POST'}); location.reload();
}

function exportExcel() {
    if (filteredTickets.length === 0) return alert("Không có dữ liệu!");
    
    const ws = XLSX.utils.json_to_sheet(filteredTickets.map(t => ({ 
        "Mã": "#" + t.id, 
        "Khách": t.user_name, 
        "Phòng": t.dept, 
        "Lỗi": t.issue, 
        "Trạng thái": t.status, 
        "IT Chính": t.it_name || "Chờ nhận", 
        "IT Hỗ Trợ": t.support_it_names || "",
        "Đánh giá": t.rating || 0, 
        "Thời gian tạo": t.created_at,
        "Thời gian xong": t.completed_at || "Chưa xong"
    })));
    
    const wb = XLSX.utils.book_new(); XLSX.utils.book_append_sheet(wb, ws, "Data");
    XLSX.writeFile(wb, "IT_Helpdesk_Report.xlsx");
}
