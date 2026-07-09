# Task 16: 前端 — 登录注册 UI + 题库选择

## Context
This is Task 16 of 17 in a UGC question bank system. The project is a Flask + Vue + SQLite quiz system at `d:\期末冲刺刷题系统`. Tasks 1-15 are complete (151 tests pass). All backend APIs are ready: auth (register/login/me/logout), banks CRUD, CSV import, reports, subscriptions. This task adds the frontend UI.

**This is NOT TDD** — frontend changes are verified manually + regression test for API.

## Files
- Modify: `backend/static/js/app.js` — add auth state + CSRF + bank selection + update existing functions
- Modify: `backend/templates/index.html` — add login/register modal + bank selector UI + CSS
- Modify: `backend/static/sw.js` — version bump v8 → v9

## Current app.js Structure (1327 lines, Vue 3)
- Lines 1-4: createApp setup
- Lines 5-91: State declarations (activeTab, theme, questions, mistakes, etc.)
- Lines 93-158: localStorage persistence (saveState/loadState)
- Lines 160-208: Computed properties
- Lines 210-256: Utility functions
- Lines 258-325: Toast, loading, session ID, apiFetch, fetchWithLoading
- Lines 327-332: Theme switching
- Lines 334-359: Tab switching
- Lines 361-472: Filter functions
- Lines 474-537: Single mode (loadAllForSingleMode)
- Lines 539-557: Load more
- Lines 570-726: Answer submission (submitAnswer uses apiFetch)
- Lines 953-1012: Favorites (toggleFav uses fetchWithLoading)
- Lines 829-848: Reset stats (resetAllStats uses apiFetch)
- Lines 1249-1278: onMounted initialization
- Lines 1280-1325: Return statement (exposes state + methods to template)

### Key existing patterns:
- `apiFetch(url, options)` — wraps fetch with X-Session-Id header
- `fetchWithLoading(url, options)` — wraps fetchWithLoading with loading state
- State is declared with `ref()` and `reactive()`
- All state/methods must be in the `return` statement at the end

## Current index.html Structure
- Line 829: `<div id="app">`
- Lines 844-864: `<header class="app-header">` with h1 + theme toggle button
- Line 867: `<div class="main-content">` — main content area
- Lines 1538-1577: `<nav class="bottom-nav">` — bottom navigation tabs

## Step 1: Update app.js

### 1a: Add new reactive state (after line 91, after existing state declarations)

```javascript
// ========== 认证状态 ==========
const currentUser = ref(null);
const csrfToken = ref('');
const showLoginModal = ref(false);
const loginMode = ref('login');
const loginForm = reactive({ student_id: '', password: '', nickname: '' });
const loginError = ref('');

// ========== 题库状态 ==========
const currentBankId = ref(1);
const myBanks = ref([]);
const officialBanks = ref([]);
const subscribedBanks = ref([]);
const showBankSelector = ref(false);
```

### 1b: Add authFetch function (after apiFetch, around line 304)

```javascript
// ========== CSRF + 认证请求 ==========
async function authFetch(url, options = {}) {
  if (!options.headers) options.headers = {};
  if (csrfToken.value && options.method && options.method !== 'GET') {
    options.headers['X-CSRF-Token'] = csrfToken.value;
  }
  options.headers['X-Session-Id'] = sessionId;
  const resp = await fetch(url, options);
  if (resp.status === 401) {
    currentUser.value = null;
    csrfToken.value = '';
  }
  return resp;
}
```

### 1c: Add auth methods (after authFetch)

```javascript
async function checkAuth() {
  try {
    const resp = await fetch('/api/auth/me');
    if (resp.ok) {
      currentUser.value = await resp.json();
    }
  } catch (e) {}
}

async function submitLogin() {
  loginError.value = '';
  const url = loginMode.value === 'login' ? '/api/auth/login' : '/api/auth/register';
  const body = loginMode.value === 'login'
    ? { student_id: loginForm.student_id, password: loginForm.password }
    : { student_id: loginForm.student_id, password: loginForm.password, nickname: loginForm.nickname };
  const resp = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  const data = await resp.json();
  if (resp.ok) {
    currentUser.value = data;
    csrfToken.value = data.csrf_token;
    showLoginModal.value = false;
    loginForm.student_id = '';
    loginForm.password = '';
    loginForm.nickname = '';
    await loadMyBanks();
    await loadSubscribedBanks();
  } else {
    loginError.value = data.error || '操作失败';
  }
}

async function logout() {
  await authFetch('/api/auth/logout', { method: 'POST' });
  currentUser.value = null;
  csrfToken.value = '';
  currentBankId.value = 1;
  await loadAllForSingleMode();
}
```

### 1d: Add bank methods (after auth methods)

```javascript
async function loadMyBanks() {
  if (!currentUser.value) { myBanks.value = []; return; }
  const resp = await fetch('/api/banks?scope=mine');
  if (resp.ok) myBanks.value = (await resp.json()).banks;
}

async function loadOfficialBanks() {
  const resp = await fetch('/api/banks?scope=official');
  if (resp.ok) officialBanks.value = (await resp.json()).banks;
}

async function loadSubscribedBanks() {
  if (!currentUser.value) { subscribedBanks.value = []; return; }
  const resp = await fetch('/api/banks?scope=subscribed');
  if (resp.ok) subscribedBanks.value = (await resp.json()).banks;
}

async function selectBank(bankId) {
  currentBankId.value = bankId;
  showBankSelector.value = false;
  await loadAllForSingleMode();
  if (currentUser.value) {
    const resp = await fetch(`/api/banks/${bankId}/progress`);
    if (resp.ok) {
      const progress = await resp.json();
      doneSet.value = new Set(progress.done_question_ids);
    }
  }
}

async function createBank() {
  const name = prompt('题库名称:');
  if (!name) return;
  const resp = await authFetch('/api/banks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, course: 'custom' })
  });
  if (resp.ok) {
    await loadMyBanks();
    const bank = await resp.json();
    await selectBank(bank.id);
  }
}
```

### 1e: Update loadAllForSingleMode to include bank_id

In the `loadAllForSingleMode` function, add `bank_id` to the URLSearchParams:
```javascript
// Add this line after the existing params.set() calls:
params.set('bank_id', currentBankId.value);
```

Also update `loadQuestions` to include bank_id:
```javascript
// In loadQuestions, add:
if (currentBankId.value) params.set('bank_id', currentBankId.value);
```

### 1f: Update onMounted to call checkAuth and loadOfficialBanks

In the onMounted function, add these calls:
```javascript
checkAuth();
loadOfficialBanks();
```

### 1g: Update return statement

Add these to the return statement:
```javascript
// 认证 & 题库
currentUser, csrfToken, showLoginModal, loginMode, loginForm, loginError,
currentBankId, myBanks, officialBanks, subscribedBanks, showBankSelector,
authFetch, checkAuth, submitLogin, logout,
loadMyBanks, loadOfficialBanks, loadSubscribedBanks, selectBank, createBank,
```

## Step 2: Update index.html

### 2a: Add auth area in header (after the h1, before theme toggle)

```html
<div class="nav-auth-area">
  <div v-if="!currentUser" @click="showLoginModal = true; loginMode = 'login'" class="nav-auth-btn">登录 / 注册</div>
  <div v-else class="nav-user-info">
    <span class="user-name">{{ currentUser.nickname }}</span>
    <button @click="logout" class="logout-btn">退出</button>
  </div>
</div>
```

### 2b: Add bank selector (in the main content area, before the quiz content)

```html
<div class="bank-selector-bar">
  <div class="bank-selector" @click="showBankSelector = !showBankSelector">
    <span>{{ currentBankId === 1 ? '官方题库' : (myBanks.find(b => b.id === currentBankId)?.name || subscribedBanks.find(b => b.id === currentBankId)?.name || '选择题库') }}</span>
    <span class="arrow">▼</span>
  </div>
  <div v-if="showBankSelector" class="bank-dropdown" @click.self="showBankSelector = false">
    <div class="bank-group">
      <div class="bank-group-title">官方题库</div>
      <div v-for="b in officialBanks" :key="b.id" @click="selectBank(b.id)" class="bank-item" :class="{ active: currentBankId === b.id }">
        {{ b.name }} ({{ b.question_count }}题)
      </div>
    </div>
    <div v-if="currentUser" class="bank-group">
      <div class="bank-group-title">我的题库 <button @click.stop="createBank" class="add-bank-btn">+ 新建</button></div>
      <div v-for="b in myBanks" :key="b.id" @click="selectBank(b.id)" class="bank-item" :class="{ active: currentBankId === b.id }">
        {{ b.name }} ({{ b.question_count }}题)
      </div>
    </div>
    <div v-if="currentUser && subscribedBanks.length" class="bank-group">
      <div class="bank-group-title">已订阅</div>
      <div v-for="b in subscribedBanks" :key="b.id" @click="selectBank(b.id)" class="bank-item" :class="{ active: currentBankId === b.id }">
        {{ b.name }} ({{ b.question_count }}题)
      </div>
    </div>
  </div>
</div>
```

### 2c: Add login/register modal (at the end of the #app div, before the closing </div>)

```html
<div v-if="showLoginModal" class="modal-overlay" @click.self="showLoginModal = false">
  <div class="modal-content">
    <h3>{{ loginMode === 'login' ? '登录' : '注册' }}</h3>
    <div v-if="loginError" class="error-msg">{{ loginError }}</div>
    <input v-model="loginForm.student_id" placeholder="学号" class="form-input" @keyup.enter="submitLogin">
    <input v-model="loginForm.password" type="password" placeholder="密码" class="form-input" @keyup.enter="submitLogin">
    <input v-if="loginMode === 'register'" v-model="loginForm.nickname" placeholder="昵称" class="form-input" @keyup.enter="submitLogin">
    <button @click="submitLogin" class="form-btn">{{ loginMode === 'login' ? '登录' : '注册' }}</button>
    <div @click="loginMode = loginMode === 'login' ? 'register' : 'login'" class="switch-mode">
      {{ loginMode === 'login' ? '没有账号？去注册' : '已有账号？去登录' }}
    </div>
  </div>
</div>
```

### 2d: Add CSS styles (in the existing `<style>` section)

Add these styles for the new UI elements. Use the existing CSS variable system (var(--bg), var(--text), etc.) for theme consistency:

```css
/* Auth Area */
.nav-auth-area { margin-left: auto; display: flex; align-items: center; gap: 8px; }
.nav-auth-btn { padding: 6px 14px; border-radius: 20px; background: var(--accent, #4a90d9); color: #fff; cursor: pointer; font-size: 13px; white-space: nowrap; }
.nav-user-info { display: flex; align-items: center; gap: 8px; }
.user-name { font-size: 13px; color: var(--text, #333); }
.logout-btn { padding: 4px 10px; border-radius: 12px; background: transparent; border: 1px solid var(--border, #ddd); color: var(--text, #333); cursor: pointer; font-size: 12px; }

/* Bank Selector */
.bank-selector-bar { position: relative; margin-bottom: 12px; }
.bank-selector { display: inline-flex; align-items: center; gap: 6px; padding: 6px 14px; border-radius: 20px; background: var(--card-bg, #fff); border: 1px solid var(--border, #ddd); cursor: pointer; font-size: 13px; color: var(--text, #333); }
.bank-selector .arrow { font-size: 10px; }
.bank-dropdown { position: absolute; top: 100%; left: 0; margin-top: 4px; background: var(--card-bg, #fff); border: 1px solid var(--border, #ddd); border-radius: 12px; box-shadow: 0 4px 16px rgba(0,0,0,0.12); min-width: 240px; max-height: 360px; overflow-y: auto; z-index: 100; }
.bank-group { padding: 8px 0; border-bottom: 1px solid var(--border, #eee); }
.bank-group:last-child { border-bottom: none; }
.bank-group-title { padding: 4px 14px; font-size: 11px; color: var(--text-secondary, #999); font-weight: 600; display: flex; justify-content: space-between; align-items: center; }
.add-bank-btn { font-size: 11px; padding: 2px 8px; border-radius: 10px; border: none; background: var(--accent, #4a90d9); color: #fff; cursor: pointer; }
.bank-item { padding: 8px 14px; cursor: pointer; font-size: 13px; color: var(--text, #333); }
.bank-item:hover { background: var(--hover-bg, rgba(0,0,0,0.04)); }
.bank-item.active { color: var(--accent, #4a90d9); font-weight: 600; }

/* Modal */
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-content { background: var(--card-bg, #fff); border-radius: 16px; padding: 28px; width: 90%; max-width: 340px; box-shadow: 0 8px 32px rgba(0,0,0,0.2); }
.modal-content h3 { margin: 0 0 16px; font-size: 18px; color: var(--text, #333); text-align: center; }
.error-msg { padding: 8px 12px; border-radius: 8px; background: #fee; color: #c33; font-size: 13px; margin-bottom: 12px; }
.form-input { width: 100%; padding: 10px 14px; border-radius: 10px; border: 1px solid var(--border, #ddd); background: var(--bg, #f5f5f5); color: var(--text, #333); font-size: 14px; margin-bottom: 10px; box-sizing: border-box; }
.form-input:focus { outline: none; border-color: var(--accent, #4a90d9); }
.form-btn { width: 100%; padding: 10px; border-radius: 10px; border: none; background: var(--accent, #4a90d9); color: #fff; font-size: 14px; cursor: pointer; }
.switch-mode { text-align: center; margin-top: 12px; font-size: 13px; color: var(--accent, #4a90d9); cursor: pointer; }
```

## Step 3: Update sw.js

Change `CACHE_VERSION` from `v8` to `v9` (line 3 and line 11).

## Step 4: Run regression tests

Run: `cd d:\期末冲刺刷题系统\backend && python -m pytest tests/ -v --ignore=tests/e2e --tb=short`
Expected: 151 tests pass (no regression — frontend changes don't affect API tests)

## Step 5: Commit

```bash
cd d:\期末冲刺刷题系统
git add backend/static/js/app.js backend/templates/index.html backend/static/sw.js
git commit -m "feat: 前端 — 登录注册 UI + 题库选择 + 进度同步"
```
