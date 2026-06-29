const { createApp, ref, reactive, computed, onMounted, watch, nextTick } = Vue;

createApp({
  setup() {
    // ========== 状态 ==========
    const activeTab = ref('quiz');
    function getInitialTheme() {
      const stored = localStorage.getItem('theme');
      if (stored) return stored;
      // 检测系统暗色模式偏好
      if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
        return 'dark';
      }
      return 'light';
    }
    const theme = ref(getInitialTheme());
    const questions = ref([]);
    const mistakes = ref([]);
    const favorites = ref([]);
    const stats = ref({});
    const page = ref(1);
    const totalPages = ref(1);
    const mode = ref('normal');
    const userAnswers = reactive({});
    const results = reactive({});
    const showExplanations = reactive({});
    const favIds = ref(new Set());
    const loading = ref(false);
    const loadingDone = ref(false);
    // R3: 按 Tab 的加载标记，避免跨 Tab 串台（quiz 加载时切到收藏，收藏空状态被隐藏）
    const tabLoading = reactive({ quiz: false, stats: false, mistakes: false, favorites: false });
    const loadingKey = ref(0);
    const toasts = ref([]);
    const submitLock = ref(false);
    const showMoreFilter = ref(false);

    // 错题分页
    const mistakePage = ref(1);
    const mistakeTotalPages = ref(1);

    // 收藏分页
    const favPage = ref(1);
    const favTotalPages = ref(1);

    const filter = reactive({ chapter: '', keyword: '' });
    const chapters = ref([]);
    const selectedCourse = ref('');
    const selectedTypes = ref([]);

    // 单题模式状态
    const singleMode = ref(true); // 单题流为默认
    const cursor = ref(0);        // 全局游标（当前在题目列表中的位置）
    const allQuestions = ref([]);
    const courseCounts = ref({});
    // 已做题号集合（持久化到 localStorage）
    const doneSet = ref(new Set());
    // 兼容 index.html 仍引用 currentIndex（后续 HTML 改为 cursor 后可移除）
    const currentIndex = computed(() => cursor.value);

    // Anki 复习模式
    const reviewMode = ref(false);
    const reviewQueue = ref([]);
    const reviewIndex = ref(0);

    // ========== 触觉反馈 ==========
    const haptic = {
      light: () => { if (navigator.vibrate) navigator.vibrate(10); },
      medium: () => { if (navigator.vibrate) navigator.vibrate(25); },
      heavy: () => { if (navigator.vibrate) navigator.vibrate([50, 30, 50]); },
      success: () => { if (navigator.vibrate) navigator.vibrate([15, 50, 15]); },
      error: () => { if (navigator.vibrate) navigator.vibrate([80, 50, 80]); },
    };

    // ========== 连击系统 ==========
    const streak = ref(0);
    const showCombo = ref(false);
    let comboTimeout = null;

    // ========== localStorage 持久化 ==========
    const STORAGE_KEY = 'quiz_state_v1';
    function saveState() {
      try {
        const state = {
          userAnswers: Object.fromEntries(Object.entries(userAnswers)),
          results: Object.fromEntries(Object.entries(results)),
          showExplanations: Object.fromEntries(Object.entries(showExplanations)),
          page: page.value,
          selectedTypes: selectedTypes.value,
          selectedCourse: selectedCourse.value,
          filter: { chapter: filter.chapter, keyword: filter.keyword },
          mode: mode.value,
          activeTab: activeTab.value,
          singleMode: singleMode.value,
          cursor: cursor.value,
          doneSet: Array.from(doneSet.value),
          mistakePage: mistakePage.value,
          favPage: favPage.value,
          reviewMode: reviewMode.value,
          reviewIndex: reviewIndex.value,
          showMoreFilter: showMoreFilter.value,
          scrollMemory: { ...scrollMemory },
          // R1: 持久化单题会话题目（精简字段，限500题防 localStorage 爆）
          allQuestions: singleMode.value ? allQuestions.value.slice(0, 500).map(q => ({
            id: q.id, stem: q.stem, type: q.type, options: q.options,
            answer: q.answer, explanation: q.explanation, knowledge: q.knowledge,
            chapter: q.chapter, course: q.course
          })) : [],
        };
        localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
      } catch(e) { /* localStorage 满了就忽略 */ }
    }
    function loadState() {
      try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (!raw) return;
        const state = JSON.parse(raw);
        if (state.userAnswers) Object.assign(userAnswers, state.userAnswers);
        if (state.results) Object.assign(results, state.results);
        if (state.showExplanations) Object.assign(showExplanations, state.showExplanations);
        if (state.page) page.value = state.page;
        if (state.selectedTypes) selectedTypes.value = state.selectedTypes;
        if (state.selectedCourse !== undefined) selectedCourse.value = state.selectedCourse;
        if (state.filter) Object.assign(filter, state.filter);
        if (state.mode) mode.value = state.mode;
        if (state.activeTab) activeTab.value = state.activeTab;
        if (state.singleMode) singleMode.value = state.singleMode;
        if (state.cursor !== undefined) cursor.value = state.cursor;
        else if (state.currentIndex !== undefined) cursor.value = state.currentIndex; // 兼容旧持久化数据
        if (state.doneSet) doneSet.value = new Set(state.doneSet);
        if (state.mistakePage) mistakePage.value = state.mistakePage;
        if (state.favPage) favPage.value = state.favPage;
        if (state.reviewMode !== undefined) reviewMode.value = state.reviewMode;
        if (state.reviewIndex !== undefined) reviewIndex.value = state.reviewIndex;
        if (state.showMoreFilter !== undefined) showMoreFilter.value = state.showMoreFilter;
        if (state.scrollMemory) Object.assign(scrollMemory, state.scrollMemory);
        // R1: 恢复单题会话题目
        if (state.allQuestions && Array.isArray(state.allQuestions) && state.allQuestions.length) {
          allQuestions.value = state.allQuestions;
        }
      } catch(e) { /* 解析失败忽略 */ }
    }
    // 用 watch 自动保存
    watch([userAnswers, results, showExplanations], saveState, { deep: true });
    watch([page, mode, activeTab, selectedTypes, selectedCourse, () => filter.chapter, () => filter.keyword, singleMode, cursor, doneSet, mistakePage, favPage, reviewMode, reviewIndex, showMoreFilter], saveState, { deep: true });

    // ========== 计算属性 ==========
    const themeLabel = computed(() => theme.value === 'dark' ? 'LIGHT' : 'DARK');

    // 单题模式进度：基于 doneSet 与 allQuestions（当前筛选集）
    // 只统计在当前 allQuestions 中且在 doneSet 中的题数，避免筛选后溢出
    const singleDoneCount = computed(() => {
      if (!allQuestions.value.length) return 0;
      return allQuestions.value.filter(q => doneSet.value.has(q.id)).length;
    });
    const progressPercent = computed(() => {
      if (singleMode.value) {
        // 单题模式：基于当前筛选集
        if (!allQuestions.value.length) return 0;
        return Math.round((singleDoneCount.value / allQuestions.value.length) * 100);
      }
      // 列表模式：基于服务端统计
      const answered = stats.value.answered_questions || 0;
      const total = stats.value.total_questions || 0;
      if (!total) return 0;
      return Math.round((answered / total) * 100);
    });
    const doneCount = computed(() => singleMode.value ? singleDoneCount.value : (stats.value.answered_questions || 0));
    const totalCount = computed(() => singleMode.value ? allQuestions.value.length : (stats.value.total_questions || 0));

    const maxTypeCount = computed(() => {
      if (!stats.value.type_distribution) return 1;
      return Math.max(1, ...Object.values(stats.value.type_distribution));
    });

    const maxCourseCount = computed(() => {
      if (!stats.value.course_distribution) return 1;
      return Math.max(1, ...Object.values(stats.value.course_distribution));
    });

    // 分页器：生成可见页码数组
    const visiblePages = computed(() => buildVisiblePages(page.value, totalPages.value));
    const mistakeVisiblePages = computed(() => buildVisiblePages(mistakePage.value, mistakeTotalPages.value));
    const favVisiblePages = computed(() => buildVisiblePages(favPage.value, favTotalPages.value));

    // 单题模式：当前题目（基于全局游标 cursor）
    const currentQuestion = computed(() => {
      if (singleMode.value && allQuestions.value.length > 0) {
        return allQuestions.value[cursor.value] || null;
      }
      return null;
    });

    // 加载更多：是否还有更多
    const hasMore = computed(() => page.value < totalPages.value);

    // ========== 工具函数 ==========
    const typeLabel = (t) => {
      const map = { single: '单选', multiple: '多选', true_false: '判断', fill_blank: '填空', short_answer: '简答' };
      return map[t] || t;
    };

    const courseLabel = (c) => {
      const map = { weather: '天气分析', english: '大学英语' };
      return map[c] || c;
    };

    const formatAnswer = (ans) => {
      if (Array.isArray(ans)) return ans.join(', ');
      return ans;
    };

    const isCorrectOption = (q, key) => {
      const answer = q.answer;
      if (Array.isArray(answer)) {
        if (answer.includes(key)) return true;
        // 判断题：答案可能存的是选项文本而非 key
        const optionText = q.options ? q.options[key] : null;
        if (optionText) return answer.some(a => String(a).trim() === String(optionText).trim());
        return false;
      }
      return answer === key;
    };

    const barWidth = (count, max) => {
      if (max <= 0) return '0%';
      return Math.max(2, (count / max) * 100) + '%';
    };

    function buildVisiblePages(current, total) {
      if (total <= 7) {
        return Array.from({ length: total }, (_, i) => i + 1);
      }
      const pages = [];
      pages.push(1);
      if (current > 3) pages.push('...');
      const start = Math.max(2, current - 1);
      const end = Math.min(total - 1, current + 1);
      for (let i = start; i <= end; i++) pages.push(i);
      if (current < total - 2) pages.push('...');
      pages.push(total);
      return pages;
    }

    // ========== Toast 通知 ==========
    let toastIdCounter = 0;
    const showToast = (message, type = 'info') => {
      const id = ++toastIdCounter;
      toasts.value.push({ id, message, type, leaving: false });
      setTimeout(() => {
        const t = toasts.value.find(t => t.id === id);
        if (t) t.leaving = true;
        setTimeout(() => {
          toasts.value = toasts.value.filter(t => t.id !== id);
        }, 300);
      }, 2700);
    };

    // ========== 加载状态管理 ==========
    const startLoading = () => {
      loading.value = true;
      loadingDone.value = false;
      loadingKey.value++;
    };

    const finishLoading = () => {
      loading.value = false;
      nextTick(() => { loadingDone.value = true; });
      setTimeout(() => { loadingDone.value = false; }, 300);
    };

    // ========== Session ID（用户数据隔离）==========
    // 每个浏览器生成唯一 ID，不同设备/浏览器数据互不干扰
    const SESSION_KEY = 'quiz_session_id';
    function getSessionId() {
      let sid = localStorage.getItem(SESSION_KEY);
      if (!sid) {
        // 生成随机 ID: 时间戳 + 随机数
        sid = 's_' + Date.now().toString(36) + '_' + Math.random().toString(36).substr(2, 12);
        localStorage.setItem(SESSION_KEY, sid);
      }
      return sid;
    }
    const sessionId = getSessionId();

    // 统一 API 请求封装：自动带上 X-Session-Id
    async function apiFetch(url, options = {}) {
      options.headers = options.headers || {};
      options.headers['X-Session-Id'] = sessionId;
      return fetch(url, options);
    }

    // 带加载状态的 fetch 封装（R3: 额外标记当前 Tab 的加载态）
    const fetchWithLoading = async (url, options = {}) => {
      const tab = activeTab.value || 'quiz';
      startLoading();
      tabLoading[tab] = true;
      try {
        options.headers = options.headers || {};
        options.headers['X-Session-Id'] = sessionId;
        const res = await fetch(url, options);
        const data = await res.json();
        finishLoading();
        tabLoading[tab] = false;
        return data;
      } catch (err) {
        finishLoading();
        tabLoading[tab] = false;
        showToast('网络请求失败，请稍后重试', 'error');
        throw err;
      }
    };

    // ========== 主题切换 ==========
    const toggleTheme = () => {
      theme.value = theme.value === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', theme.value);
      localStorage.setItem('theme', theme.value);
    };

    // ========== Tab 切换 ==========
    // R2: 各 Tab 独立滚动位置记忆，切走保存、切回恢复
    const scrollMemory = {};
    const saveScroll = () => { scrollMemory[activeTab.value] = window.scrollY || 0; };

    const switchTab = (tab) => {
      if (activeTab.value === tab && tab !== 'quiz') return; // 避免重复刷新
      saveScroll();                       // 离开当前 Tab 前先存位置
      haptic.light();
      activeTab.value = tab;
      if (tab === 'quiz') {
        nextTick(() => window.scrollTo({ top: scrollMemory['quiz'] || 0 }));
        return;
      }
      if (tab === 'stats') loadStats();
      if (tab === 'mistakes') { loadMistakes(mistakePage.value); }
      if (tab === 'favorites') { loadFavorites(favPage.value); }
      nextTick(() => window.scrollTo({ top: scrollMemory[tab] || 0 }));
    };

    // ========== 筛选相关 ==========
    const onFilterChange = () => {
      if (singleMode.value) {
        loadAllForSingleMode().then(() => {
          // 筛选改变后重置游标到第一个未答题（doneSet 保留，已做的题仍标记为已做）
          let idx = 0;
          while (idx < allQuestions.value.length && doneSet.value.has(allQuestions.value[idx].id)) {
            idx++;
          }
          cursor.value = idx < allQuestions.value.length ? idx : 0;
        });
      } else if (mode.value === 'normal') {
        loadQuestions(1);
      } else {
        loadRandom();
      }
    };

    const switchMode = (newMode) => {
      // R4-A: 统一加载入口，退出单题模式不再在模板里另调一次
      if (singleMode.value) singleMode.value = false;
      if (mode.value === newMode && newMode === 'normal') {
        // 已在 normal 且非单题：刷新列表
        loadQuestions(1);
        return;
      }
      mode.value = newMode;
      if (newMode === 'normal') {
        loadQuestions(1);
      } else {
        loadRandom();
      }
    };

    // ========== 题目加载 ==========
    const prepareQuestionState = (items) => {
      items.forEach(q => {
        if (q.type === 'multiple' && !Array.isArray(userAnswers[q.id])) {
          userAnswers[q.id] = [];
        }
      });
    };

    // ========== 填空题多空辅助 ==========
    const getFillBlanks = (q) => {
      // 检测题干中有多少个填空位置
      const stem = q.stem || '';
      const matches = stem.match(/_{2,}|（\s*）|\(\s*\)/g) || [];
      // 如果无法从题干检测，用答案数量
      if (matches.length === 0 && Array.isArray(q.answer)) return q.answer.slice(0, 1);
      return matches.length > 0 ? new Array(matches.length) : new Array(1);
    };
    const setFillBlankAnswer = (q, idx, value) => {
      if (!Array.isArray(userAnswers[q.id])) {
        userAnswers[q.id] = [];
      }
      // 确保数组长度足够
      while (userAnswers[q.id].length <= idx) userAnswers[q.id].push('');
      userAnswers[q.id][idx] = value;
    };

    const loadQuestions = async (p = 1) => {
      page.value = p;
      const params = new URLSearchParams({ page: p, page_size: 20 });
      if (selectedCourse.value) params.set('course', selectedCourse.value);
      if (selectedTypes.value.length > 0) params.set('type', selectedTypes.value.join(','));
      if (filter.chapter) params.set('chapter', filter.chapter);
      if (filter.keyword) params.set('keyword', filter.keyword);
      const data = await fetchWithLoading('/api/questions?' + params);
      questions.value = data.items || [];
      prepareQuestionState(questions.value);
      totalPages.value = Math.ceil(data.total / data.page_size) || 1;
      window.scrollTo({ top: 0, behavior: 'smooth' });
      haptic.light();
    };

    const loadRandom = async () => {
      const params = new URLSearchParams({ limit: 20 });
      if (selectedCourse.value) params.set('course', selectedCourse.value);
      if (selectedTypes.value.length > 0) params.set('type', selectedTypes.value.join(','));
      if (filter.chapter) params.set('chapter', filter.chapter);
      const data = await fetchWithLoading('/api/questions/random?' + params);
      questions.value = data.items || [];
      prepareQuestionState(questions.value);
      totalPages.value = 1;
      window.scrollTo({ top: 0, behavior: 'smooth' });
    };

    // ========== Filter Chip 切换 ==========
    const toggleTypeChip = (type) => {
      const idx = selectedTypes.value.indexOf(type);
      if (idx >= 0) {
        selectedTypes.value.splice(idx, 1);
      } else {
        selectedTypes.value.push(type);
      }
      onFilterChange();
    };

    const isTypeSelected = (type) => selectedTypes.value.includes(type);

    const selectCourse = (course) => {
      if (selectedCourse.value === course) {
        selectedCourse.value = ''; // 再点一次取消
      } else {
        selectedCourse.value = course;
      }
      loadChapters();
      onFilterChange();
    };

    const isCourseSelected = (course) => selectedCourse.value === course;

    // ========== 单题模式 ==========
    const enterSingleMode = () => {
      singleMode.value = true;
      cursor.value = 0;
      loadAllForSingleMode();
    };

    const exitSingleMode = () => {
      // R4-A: 仅切标志，加载责任统一交给 switchMode（避免双加载）
      singleMode.value = false;
    };

    const nextQuestion = () => {
      let next = cursor.value + 1;
      // 跳过已做的题
      while (next < allQuestions.value.length && doneSet.value.has(allQuestions.value[next].id)) {
        next++;
      }
      if (next < allQuestions.value.length) {
        cursor.value = next;
      } else {
        // 检查是否全部做完
        const allDone = allQuestions.value.every(q => doneSet.value.has(q.id));
        if (allDone) {
          showToast('已完成全部题目！', 'success');
        }
      }
    };

    const prevQuestion = () => {
      if (cursor.value > 0) {
        cursor.value--;
      }
    };

    const loadAllForSingleMode = async () => {
      try {
        const savedIndex = cursor.value;
        const params = new URLSearchParams({ page: 1, page_size: 500 });
        if (selectedCourse.value) params.set('course', selectedCourse.value);
        if (selectedTypes.value.length > 0) params.set('type', selectedTypes.value.join(','));
        if (filter.chapter) params.set('chapter', filter.chapter);
        if (filter.keyword) params.set('keyword', filter.keyword);
        const res = await apiFetch('/api/questions?' + params);
        const data = await res.json();
        allQuestions.value = data.items || [];
        prepareQuestionState(allQuestions.value);
        // 恢复之前保存的游标，不超出范围
        cursor.value = Math.min(savedIndex, allQuestions.value.length - 1);
        if (cursor.value < 0) cursor.value = 0;
      } catch(e) {
        showToast('加载题目失败', 'error');
      }
    };

    // ========== 加载更多 ==========
    const loadMore = async () => {
      if (page.value >= totalPages.value) return;
      const nextPage = page.value + 1;
      const params = new URLSearchParams({ page: nextPage, page_size: 20 });
      if (selectedCourse.value) params.set('course', selectedCourse.value);
      if (selectedTypes.value.length > 0) params.set('type', selectedTypes.value.join(','));
      if (filter.chapter) params.set('chapter', filter.chapter);
      if (filter.keyword) params.set('keyword', filter.keyword);
      try {
        const res = await apiFetch('/api/questions?' + params);
        const data = await res.json();
        questions.value = [...questions.value, ...(data.items || [])];
        prepareQuestionState(questions.value);
        page.value = nextPage;
      } catch(e) {
        showToast('加载更多失败', 'error');
      }
    };

    // ========== 课程数量加载 ==========
    const loadCourseCounts = async () => {
      try {
        const res = await apiFetch('/api/stats');
        const data = await res.json();
        if (data.course_distribution) {
          courseCounts.value = data.course_distribution;
        }
      } catch(e) {}
    };

    // ========== 选项交互 ==========
    const selectOption = (q, key) => {
      if (results[q.id]) return; // 已提交则不可再选
      haptic.light();
      userAnswers[q.id] = key;
    };

    const toggleMultipleOption = (q, key) => {
      if (results[q.id]) return;
      haptic.light();
      if (!Array.isArray(userAnswers[q.id])) {
        userAnswers[q.id] = [];
      }
      const idx = userAnswers[q.id].indexOf(key);
      if (idx >= 0) {
        userAnswers[q.id].splice(idx, 1);
      } else {
        userAnswers[q.id].push(key);
      }
    };

    // ========== 离线答题队列 ==========
    const OFFLINE_QUEUE_KEY = 'quiz_offline_queue';
    const getOfflineQueue = () => {
      try { return JSON.parse(localStorage.getItem(OFFLINE_QUEUE_KEY) || '[]'); }
      catch { return []; }
    };
    const saveOfflineQueue = (queue) => {
      localStorage.setItem(OFFLINE_QUEUE_KEY, JSON.stringify(queue));
    };
    // 本地判对错（题目已含 q.answer）
    const checkAnswerLocally = (q, ans) => {
      const correctAns = q.answer;
      if (Array.isArray(correctAns)) {
        const sortedAns = Array.isArray(ans) ? [...ans].sort() : [ans];
        const sortedCorrect = [...correctAns].sort();
        return JSON.stringify(sortedAns) === JSON.stringify(sortedCorrect);
      }
      return String(ans).trim() === String(correctAns).trim();
    };
    // 联网后同步离线队列
    const syncOfflineQueue = async () => {
      const queue = getOfflineQueue();
      if (!queue.length) return;
      let synced = 0;
      for (const item of queue) {
        try {
          await apiFetch('/api/submit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question_id: item.qid, answer: item.ans })
          });
          synced++;
        } catch (e) { break; } // 网络又断了，停止同步
      }
      if (synced > 0) {
        saveOfflineQueue(queue.slice(synced));
        showToast(`已同步 ${synced} 条离线答题记录`, 'success');
        loadStatsSilent();
      }
    };
    // 监听网络恢复
    window.addEventListener('online', () => {
      syncOfflineQueue();
    });

    // ========== 提交答案 ==========
    const submitAnswer = async (q) => {
      if (submitLock.value) return;
      submitLock.value = true;
      setTimeout(() => { submitLock.value = false; }, 800);
      let ans = userAnswers[q.id];
      if (q.type === 'multiple') {
        if (!Array.isArray(ans) || ans.length === 0) {
          showToast('请至少选择一个选项', 'error');
          return;
        }
        ans = [...ans].sort();
      } else if (q.type === 'single' || q.type === 'true_false') {
        if (!ans) {
          showToast('请先选择答案', 'error');
          return;
        }
      } else if (q.type === 'fill_blank') {
        ans = userAnswers[q.id];
        if (Array.isArray(ans)) {
          if (ans.length === 0 || ans.every(a => !a || !a.trim())) {
            showToast('请输入答案', 'error');
            return;
          }
        } else if (!ans || (typeof ans === 'string' && ans.trim() === '')) {
          showToast('请输入答案', 'error');
          return;
        }
      } else {
        if (!ans || (typeof ans === 'string' && ans.trim() === '')) {
          showToast('请输入答案', 'error');
          return;
        }
      }

      // 提交答案（支持离线）
      try {
        if (!navigator.onLine) {
          // 离线模式：本地判对错，暂存队列
          const isCorrect = checkAnswerLocally(q, ans);
          results[q.id] = {
            correct: isCorrect,
            correct_answer: q.answer,
            explanation: q.explanation || '',
            knowledge: q.knowledge || '',
          };
          doneSet.value.add(q.id);
          // 暂存到离线队列
          const queue = getOfflineQueue();
          queue.push({ qid: q.id, ans: ans });
          saveOfflineQueue(queue);
          if (isCorrect) {
            streak.value++;
            haptic.success();
            showToast('回答正确! (离线暂存)', 'success');
          } else {
            streak.value = 0;
            haptic.error();
            showToast('回答错误 (离线暂存)', 'error');
          }
          return;
        }
        const res = await apiFetch('/api/submit', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question_id: q.id, answer: ans })
        });
        const data = await res.json();
        results[q.id] = data;
        doneSet.value.add(q.id);
        if (data.correct) {
          streak.value++;
          haptic.success();
          if (streak.value >= 3) {
            showCombo.value = true;
            clearTimeout(comboTimeout);
            comboTimeout = setTimeout(() => { showCombo.value = false; }, 2000);
          }
          showToast('回答正确!', 'success');
        } else {
          streak.value = 0;
          showCombo.value = false;
          haptic.error();
          showToast('回答错误', 'error');
        }
        // 延迟刷新统计（不显示加载条）
        setTimeout(() => loadStatsSilent(), 500);
      } catch (err) {
        showToast('网络请求失败', 'error');
      }
    };

    // ========== 解析显隐 ==========
    const toggleExplanation = (qid) => {
      showExplanations[qid] = !showExplanations[qid];
    };

    // ========== 统计 ==========
    const loadStats = async () => {
      try {
        const data = await fetchWithLoading('/api/stats');
        stats.value = data;
        // 从服务端恢复 doneSet（合并本地+服务端，解决换设备进度丢失）
        syncDoneSetFromServer(data);
      } catch (e) {
        // silently handle
      }
    };

    const loadStatsSilent = async () => {
      try {
        const res = await apiFetch('/api/stats');
        const data = await res.json();
        stats.value = data;
        syncDoneSetFromServer(data);
      } catch(e) {}
    };

    // 从服务端 answered_question_ids 恢复 doneSet（并集合并）
    const syncDoneSetFromServer = (data) => {
      if (!data || !Array.isArray(data.answered_question_ids)) return;
      const serverIds = data.answered_question_ids;
      const localSet = doneSet.value;
      let changed = false;
      serverIds.forEach(id => {
        if (!localSet.has(id)) {
          localSet.add(id);
          changed = true;
        }
      });
      if (changed) {
        doneSet.value = new Set(localSet);  // 触发响应式更新
        saveState();
      }
    };

    // ========== 清除答题记录 ==========
    const clearProgress = () => {
      if (!confirm('确定要清除所有答题记录吗？此操作不可撤销。')) return;
      Object.keys(userAnswers).forEach(k => delete userAnswers[k]);
      Object.keys(results).forEach(k => delete results[k]);
      Object.keys(showExplanations).forEach(k => delete showExplanations[k]);
      doneSet.value = new Set();
      cursor.value = 0;
      allQuestions.value = [];
      reviewMode.value = false;
      reviewQueue.value = [];
      reviewIndex.value = 0;
      localStorage.removeItem(STORAGE_KEY);
      localStorage.removeItem(OFFLINE_QUEUE_KEY);
      page.value = 1;
      singleMode.value = true;
      loadAllForSingleMode();
      showToast('答题记录已清除', 'info');
    };

    // ========== 继续上次练习 ==========
    const continueLastPractice = () => {
      // 跳到第一个未答题（不再恢复"第X页"）
      try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (!raw) {
          showToast('没有之前的练习记录', 'info');
          return;
        }
        singleMode.value = true;
        loadAllForSingleMode().then(() => {
          // 从 cursor=0 开始找第一个不在 doneSet 中的题目
          let idx = 0;
          while (idx < allQuestions.value.length && doneSet.value.has(allQuestions.value[idx].id)) {
            idx++;
          }
          if (idx < allQuestions.value.length) {
            cursor.value = idx;
            showToast(`继续第 ${idx + 1} 题`, 'info');
          } else {
            // 全部做完
            cursor.value = Math.max(0, allQuestions.value.length - 1);
            showToast('已完成全部题目！', 'success');
          }
        });
      } catch(e) {
        showToast('恢复失败', 'error');
      }
    };

    // 计算未答题数
    const unansweredCount = computed(() => {
      if (!questions.value.length) return 0;
      return questions.value.filter(q => !results[q.id]).length;
    });

    // ========== 清除后端全部答题记录 ==========
    const resetAllStats = async () => {
      if (!confirm('确定要清除所有后端答题记录吗？这将重置统计数据。')) return;
      try {
        const res = await apiFetch('/api/reset_stats', { method: 'POST' });
        const data = await res.json();
        if (data.ok) {
          // 同时清除本地记录
          Object.keys(userAnswers).forEach(k => delete userAnswers[k]);
          Object.keys(results).forEach(k => delete results[k]);
          doneSet.value = new Set();
          cursor.value = 0;
          localStorage.removeItem(STORAGE_KEY);
          loadStats();
          loadQuestions(1);
          showToast('所有答题记录已清除', 'success');
        }
      } catch(e) {
        showToast('清除失败', 'error');
      }
    };

    // ========== 错题 ==========
    const loadMistakes = async (p = 1) => {
      mistakePage.value = p;
      try {
        const data = await fetchWithLoading('/api/mistakes?page=' + p + '&page_size=20');
        mistakes.value = data.items || [];
        mistakeTotalPages.value = Math.ceil(data.total / 20) || 1;
      } catch (e) {
        // silently handle
      }
    };

    // 只刷错题
    const practiceMistakes = async () => {
      try {
        // 加载所有错题
        const res = await apiFetch('/api/mistakes?page=1&page_size=100');
        const data = await res.json();
        if (!data.items || data.items.length === 0) {
          showToast('暂无错题', 'info');
          return;
        }
        // R4-C: 显式设 normal 模式，确保"加载更多"按钮与模式高亮正确
        mode.value = 'normal';
        singleMode.value = false;
        questions.value = data.items;
        prepareQuestionState(questions.value);
        totalPages.value = 1;
        page.value = 1;
        activeTab.value = 'quiz';
        window.scrollTo({ top: 0, behavior: 'smooth' });
        showToast(`已加载 ${data.items.length} 道错题`, 'info');
      } catch(e) {
        showToast('加载错题失败', 'error');
      }
    };

    // ========== Anki 错题复习模式 ==========
    const startReview = async () => {
      try {
        const res = await apiFetch('/api/mistakes?page=1&page_size=100');
        const data = await res.json();
        if (!data.items || data.items.length === 0) {
          showToast('暂无错题可复习', 'info');
          return;
        }
        reviewQueue.value = [...data.items];  // 独立副本，避免与 allQuestions 共享引用
        reviewIndex.value = 0;
        reviewMode.value = true;
        singleMode.value = true;
        allQuestions.value = [...data.items];  // 独立副本
        cursor.value = 0;
        prepareQuestionState(allQuestions.value);
        activeTab.value = 'quiz';
        showToast(`开始复习 ${data.items.length} 道错题`, 'info');
      } catch(e) {
        showToast('加载错题失败', 'error');
      }
    };

    const reviewQuestion = computed(() => {
      if (!reviewMode.value) return null;
      return reviewQueue.value[reviewIndex.value] || null;
    });

    const rateReview = (rating) => {
      // rating: 'again' | 'fuzzy' | 'mastered'
      if (rating === 'again') {
        // 把当前题移到队列末尾
        const q = reviewQueue.value.splice(reviewIndex.value, 1)[0];
        reviewQueue.value.push(q);
        showToast('稍后再练', 'info');
        // 同步 allQuestions 以保持 currentQuestion 正确
        allQuestions.value = [...reviewQueue.value];
      } else if (rating === 'fuzzy') {
        showToast('标记为模糊', 'info');
        reviewIndex.value++;
      } else if (rating === 'mastered') {
        // 从队列移除
        reviewQueue.value.splice(reviewIndex.value, 1);
        allQuestions.value = [...reviewQueue.value];
        showToast('已掌握！', 'success');
      }

      if (reviewQueue.value.length === 0 || reviewIndex.value >= reviewQueue.value.length) {
        if (reviewQueue.value.length === 0) {
          showToast('全部错题已复习完！', 'success');
          reviewMode.value = false;
          singleMode.value = false;
          loadAllForSingleMode();
        } else {
          reviewIndex.value = 0;
        }
      }
      cursor.value = reviewIndex.value;
    };

    const exitReview = () => {
      reviewMode.value = false;
      singleMode.value = false;
      loadQuestions(1);
    };

    // ========== 收藏 ==========
    const loadFavorites = async (p = 1) => {
      favPage.value = p;
      try {
        const data = await fetchWithLoading('/api/favorites?page=' + p + '&page_size=20');
        favorites.value = data.items || [];
        favIds.value = new Set(data.items.map(q => q.id));
        favTotalPages.value = Math.ceil(data.total / 20) || 1;
      } catch (e) {
        // silently handle
      }
    };

    const loadChapters = async () => {
      try {
        const data = await apiFetch('/api/chapters');
        const result = await data.json();
        // 如果有指定课程的筛选，用对应课程章节，否则合并所有
        if (typeof result === 'object' && !Array.isArray(result)) {
          if (selectedCourse.value && result[selectedCourse.value]) {
            chapters.value = result[selectedCourse.value];
          } else {
            // 合并所有课程的章节
            const allChapters = new Set();
            Object.values(result).forEach(chs => {
              if (Array.isArray(chs)) chs.forEach(c => allChapters.add(c));
            });
            chapters.value = Array.from(allChapters).sort((a, b) => a - b);
          }
        }
      } catch (e) {
        // fallback
        chapters.value = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
      }
    };

    const isFav = (id) => favIds.value.has(id);

    const toggleFav = async (q) => {
      haptic.medium();
      const wasFav = isFav(q.id);
      const method = wasFav ? 'DELETE' : 'POST';
      try {
        await fetchWithLoading('/api/favorites/' + q.id, {
          method,
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({})
        });
        if (wasFav) {
          showToast('已取消收藏', 'info');
        } else {
          showToast('已收藏', 'success');
        }
        // 刷新收藏列表和统计
        await loadFavorites(favPage.value);
        await loadStats();
      } catch (e) {
        // toast already shown by fetchWithLoading
      }
    };

    // ========== 重做题目（从错题/收藏跳转到刷题页） ==========
    const redoQuestion = async (q) => {
      // 先获取该题目详情，然后跳到刷题页
      try {
        const data = await fetchWithLoading('/api/questions/' + q.id);
        if (data) {
          // 清除该题的已有答案和结果
          delete userAnswers[q.id];
          delete results[q.id];
          delete showExplanations[q.id];

          // 将该题置入当前题目列表（仅此一题）
          questions.value = [data];
          prepareQuestionState(questions.value);
          totalPages.value = 1;
          page.value = 1;

          // R4-B: 仅重置页码，保留所有筛选条件
          mode.value = 'normal';
          singleMode.value = false;

          // 切换到刷题页
          activeTab.value = 'quiz';
          window.scrollTo({ top: 0, behavior: 'smooth' });

          showToast('已跳转到题目 #' + q.id, 'info');
        }
      } catch (e) {
        // toast already shown
      }
    };

    // 键盘快捷键
    // 获取当前可见区域最近的未提交题目作为焦点
    const getFocusedQuestion = () => {
      const cards = document.querySelectorAll('.question-card');
      if (!cards.length) return null;
      const viewMid = window.innerHeight / 2;
      let bestCard = null;
      let bestDist = Infinity;
      for (const card of cards) {
        const rect = card.getBoundingClientRect();
        const cardMid = rect.top + rect.height / 2;
        const dist = Math.abs(cardMid - viewMid);
        if (dist < bestDist) {
          bestDist = dist;
          bestCard = card;
        }
      }
      if (!bestCard) return null;
      const cardIndex = Array.from(cards).indexOf(bestCard);
      return questions.value[cardIndex] || null;
    };

    const handleKeydown = (e) => {
      if (activeTab.value !== 'quiz') return;
      const q = getFocusedQuestion();
      if (!q || results[q.id]) return; // 已提交的不处理

      const key = e.key;
      // 数字键 1-9 选择选项
      if (/^[1-9]$/.test(key)) {
        const optionKeys = Object.keys(q.options || {});
        const idx = parseInt(key) - 1;
        if (idx < optionKeys.length) {
          const optionKey = optionKeys[idx];
          if (q.type === 'multiple') {
            toggleMultipleOption(q, optionKey);
          } else {
            selectOption(q, optionKey);
          }
          return;
        }
      }
      // A-Z 字母键选择选项
      if (/^[a-zA-Z]$/.test(key)) {
        const optionKey = key.toUpperCase();
        if (q.options && q.options[optionKey] !== undefined) {
          if (q.type === 'multiple') {
            toggleMultipleOption(q, optionKey);
          } else {
            selectOption(q, optionKey);
          }
          return;
        }
      }
      // Enter 提交
      if (key === 'Enter') {
        e.preventDefault();
        submitAnswer(q);
        return;
      }
    };

    // ========== 初始化 ==========
    onMounted(() => {
      document.documentElement.setAttribute('data-theme', theme.value);
      window.addEventListener('keydown', handleKeydown);
      loadState(); // 恢复之前的状态
      // 单题流为默认：allQuestions 为空时自动加载单题模式题目
      if (allQuestions.value.length === 0) {
        loadAllForSingleMode();
      } else if (!singleMode.value) {
        // 已退出单题流（列表模式）才加载列表
        loadQuestions(page.value);
      }
      // 并行加载首屏数据（不互相依赖的请求同时发出）
      loadChapters();
      loadCourseCounts();
      loadStats();
      // 如果在线且有离线队列，自动同步
      if (navigator.onLine) syncOfflineQueue();
      loadMistakes(mistakePage.value);
      loadFavorites(favPage.value);
      // 监听系统主题变化
      const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
      mediaQuery.addEventListener('change', (e) => {
        // 仅在用户未手动设置过主题时跟随系统
        if (!localStorage.getItem('theme')) {
          theme.value = e.matches ? 'dark' : 'light';
          document.documentElement.setAttribute('data-theme', theme.value);
        }
      });
    });

    return {
      // 状态
      activeTab, theme, questions, mistakes, favorites, stats,
      page, totalPages, mode,
      userAnswers, results, showExplanations, favIds,
      loading, loadingDone, loadingKey, toasts, showMoreFilter,
      // R3: 按 Tab 加载标记
      tabLoading, isLoading: (tab) => tabLoading[tab] || false,
      mistakePage, mistakeTotalPages, favPage, favTotalPages,
      filter, chapters,
      // 单题模式 & Chip 状态
      singleMode, cursor, currentIndex, allQuestions, courseCounts,
      selectedTypes, selectedCourse,
      currentQuestion, hasMore,
      // 刷题进度（基于 doneSet）
      doneSet, doneCount, totalCount,
      reviewMode, reviewQueue, reviewIndex, reviewQuestion,
      streak, showCombo,

      // 计算属性
      themeLabel, progressPercent, maxTypeCount, maxCourseCount,
      visiblePages, mistakeVisiblePages, favVisiblePages,

      // 方法
      toggleTheme, switchTab, onFilterChange, switchMode,
      loadQuestions, loadRandom,
      selectOption, toggleMultipleOption, submitAnswer,
      toggleExplanation, isCorrectOption,
      loadStats, loadMistakes, loadFavorites,
      isFav, toggleFav, redoQuestion,
      typeLabel, courseLabel, formatAnswer, barWidth, showToast,
      clearProgress, getFillBlanks, setFillBlankAnswer, practiceMistakes,
      continueLastPractice, unansweredCount,
      resetAllStats,
      // Chip & 单题模式方法
      toggleTypeChip, selectCourse, isTypeSelected, isCourseSelected,
      enterSingleMode, exitSingleMode, nextQuestion, prevQuestion,
      loadMore, loadCourseCounts,
      startReview, rateReview, exitReview,
    };
  }
}).mount('#app');

// Vue 挂载后移除骨架屏（Vue 3 mount 不清空原有子元素，骨架屏需手动移除）
var __sk = document.getElementById('app-skeleton');
if (__sk) {
  __sk.style.opacity = '0';
  setTimeout(function() { __sk.remove(); }, 300);
}
