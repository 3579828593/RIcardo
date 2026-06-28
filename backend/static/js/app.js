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
    const singleMode = ref(false);
    const currentIndex = ref(0);
    const allQuestions = ref([]);
    const courseCounts = ref({});

    // Anki 复习模式
    const reviewMode = ref(false);
    const reviewQueue = ref([]);
    const reviewIndex = ref(0);

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
          currentIndex: currentIndex.value,
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
        if (state.currentIndex) currentIndex.value = state.currentIndex;
      } catch(e) { /* 解析失败忽略 */ }
    }
    // 用 watch 自动保存
    watch([userAnswers, results, showExplanations], saveState, { deep: true });
    watch([page, mode, activeTab, selectedTypes, selectedCourse, () => filter.chapter, () => filter.keyword, singleMode, currentIndex], saveState, { deep: true });

    // ========== 计算属性 ==========
    const themeLabel = computed(() => theme.value === 'dark' ? 'LIGHT' : 'DARK');

    const progressPercent = computed(() => {
      if (!stats.value.total_questions) return 0;
      return Math.min(100, ((stats.value.answered_questions || 0) / stats.value.total_questions) * 100);
    });

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

    // 单题模式：当前题目
    const currentQuestion = computed(() => {
      if (!singleMode.value) return null;
      return allQuestions.value[currentIndex.value] || null;
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

    // 带加载状态的 fetch 封装
    const fetchWithLoading = async (url, options) => {
      startLoading();
      try {
        const res = await fetch(url, options);
        const data = await res.json();
        finishLoading();
        return data;
      } catch (err) {
        finishLoading();
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
    const switchTab = (tab) => {
      if (activeTab.value === tab && tab !== 'quiz') return; // 避免重复刷新
      activeTab.value = tab;
      if (tab === 'quiz') return; // 刷题页不自动刷新
      if (tab === 'stats') loadStats();
      if (tab === 'mistakes') { mistakePage.value = 1; loadMistakes(1); }
      if (tab === 'favorites') { favPage.value = 1; loadFavorites(1); }
      // 不再强制滚动到顶部
    };

    // ========== 筛选相关 ==========
    const onFilterChange = () => {
      if (singleMode.value) {
        loadAllForSingleMode();
      } else if (mode.value === 'normal') {
        loadQuestions(1);
      } else {
        loadRandom();
      }
    };

    const switchMode = (newMode) => {
      if (mode.value === newMode) return;
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
      currentIndex.value = 0;
      loadAllForSingleMode();
    };

    const exitSingleMode = () => {
      singleMode.value = false;
      loadQuestions(1);
    };

    const nextQuestion = () => {
      if (currentIndex.value < allQuestions.value.length - 1) {
        currentIndex.value++;
      } else {
        showToast('已经是最后一题了', 'info');
      }
    };

    const prevQuestion = () => {
      if (currentIndex.value > 0) {
        currentIndex.value--;
      }
    };

    const loadAllForSingleMode = async () => {
      try {
        const params = new URLSearchParams({ page: 1, page_size: 500 });
        if (selectedCourse.value) params.set('course', selectedCourse.value);
        if (selectedTypes.value.length > 0) params.set('type', selectedTypes.value.join(','));
        if (filter.chapter) params.set('chapter', filter.chapter);
        if (filter.keyword) params.set('keyword', filter.keyword);
        const res = await fetch('/api/questions?' + params);
        const data = await res.json();
        allQuestions.value = data.items || [];
        prepareQuestionState(allQuestions.value);
        currentIndex.value = 0;
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
        const res = await fetch('/api/questions?' + params);
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
        const res = await fetch('/api/stats');
        const data = await res.json();
        if (data.course_distribution) {
          courseCounts.value = data.course_distribution;
        }
      } catch(e) {}
    };

    // ========== 选项交互 ==========
    const selectOption = (q, key) => {
      if (results[q.id]) return; // 已提交则不可再选
      userAnswers[q.id] = key;
    };

    const toggleMultipleOption = (q, key) => {
      if (results[q.id]) return;
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

      // 静默提交，不显示加载条
      try {
        const res = await fetch('/api/submit', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question_id: q.id, answer: ans })
        });
        const data = await res.json();
        results[q.id] = data;
        if (data.correct) {
          showToast('回答正确!', 'success');
        } else {
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
      } catch (e) {
        // silently handle
      }
    };

    const loadStatsSilent = async () => {
      try {
        const res = await fetch('/api/stats');
        stats.value = await res.json();
      } catch(e) {}
    };

    // ========== 清除答题记录 ==========
    const clearProgress = () => {
      if (!confirm('确定要清除所有答题记录吗？此操作不可撤销。')) return;
      Object.keys(userAnswers).forEach(k => delete userAnswers[k]);
      Object.keys(results).forEach(k => delete results[k]);
      Object.keys(showExplanations).forEach(k => delete showExplanations[k]);
      localStorage.removeItem(STORAGE_KEY);
      page.value = 1;
      loadQuestions(1);
      showToast('答题记录已清除', 'info');
    };

    // ========== 继续上次练习 ==========
    const continueLastPractice = () => {
      // 从 localStorage 恢复上次的页码和位置
      try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (!raw) {
          showToast('没有之前的练习记录', 'info');
          return;
        }
        const state = JSON.parse(raw);
        if (state.singleMode && state.currentIndex !== undefined) {
          // 单题模式恢复
          singleMode.value = true;
          loadAllForSingleMode().then(() => {
            currentIndex.value = Math.min(state.currentIndex, allQuestions.value.length - 1);
            showToast(`继续第 ${currentIndex.value + 1} 题`, 'info');
          });
        } else if (state.page) {
          // 列表模式恢复
          singleMode.value = false;
          loadQuestions(state.page).then(() => {
            showToast(`继续第 ${state.page} 页`, 'info');
          });
        } else {
          showToast('没有未完成的练习', 'info');
        }
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
        const res = await fetch('/api/reset_stats', { method: 'POST' });
        const data = await res.json();
        if (data.ok) {
          // 同时清除本地记录
          Object.keys(userAnswers).forEach(k => delete userAnswers[k]);
          Object.keys(results).forEach(k => delete results[k]);
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
        const res = await fetch('/api/mistakes?page=1&page_size=100');
        const data = await res.json();
        if (!data.items || data.items.length === 0) {
          showToast('暂无错题', 'info');
          return;
        }
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
        const res = await fetch('/api/mistakes?page=1&page_size=100');
        const data = await res.json();
        if (!data.items || data.items.length === 0) {
          showToast('暂无错题可复习', 'info');
          return;
        }
        reviewQueue.value = data.items;
        reviewIndex.value = 0;
        reviewMode.value = true;
        singleMode.value = true;
        allQuestions.value = data.items;
        currentIndex.value = 0;
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
      } else if (rating === 'fuzzy') {
        showToast('标记为模糊', 'info');
        reviewIndex.value++;
      } else if (rating === 'mastered') {
        // 从队列移除
        reviewQueue.value.splice(reviewIndex.value, 1);
        showToast('已掌握！', 'success');
      }

      if (reviewQueue.value.length === 0 || reviewIndex.value >= reviewQueue.value.length) {
        if (reviewQueue.value.length === 0) {
          showToast('全部错题已复习完！', 'success');
          reviewMode.value = false;
          singleMode.value = false;
          loadQuestions(1);
        } else {
          reviewIndex.value = 0;
        }
      } else {
        currentIndex.value = reviewIndex.value;
      }
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
        const data = await fetch('/api/chapters');
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

          // 设置筛选为该题所属课程和题型
          selectedCourse.value = data.course || '';
          selectedTypes.value = data.type ? [data.type] : [];
          filter.chapter = '';
          filter.keyword = '';
          showMoreFilter.value = false;
          mode.value = 'normal';

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
      // 并行加载首屏数据（不互相依赖的请求同时发出）
      loadChapters();
      loadCourseCounts();
      loadQuestions(page.value);
      loadStats();
      loadMistakes(1);
      loadFavorites(1);
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
      mistakePage, mistakeTotalPages, favPage, favTotalPages,
      filter, chapters,
      // 单题模式 & Chip 状态
      singleMode, currentIndex, allQuestions, courseCounts,
      selectedTypes, selectedCourse,
      currentQuestion, hasMore,
      reviewMode, reviewQueue, reviewIndex, reviewQuestion,

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
