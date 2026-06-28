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

    const filter = reactive({ course: '', type: '', chapter: '', keyword: '' });
    const chapters = ref([]);

    // ========== 计算属性 ==========
    const themeLabel = computed(() => theme.value === 'dark' ? '切换到亮色模式' : '切换到暗色模式');

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
      if (Array.isArray(answer)) return answer.includes(key);
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
      window.scrollTo({ top: 0, behavior: 'smooth' });
    };

    // ========== 筛选相关 ==========
    const onFilterChange = () => {
      loadChapters(); // 课程变化时刷新章节列表
      if (mode.value === 'normal') {
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

    const loadQuestions = async (p = 1) => {
      page.value = p;
      const params = new URLSearchParams({ page: p, page_size: 20 });
      if (filter.course) params.set('course', filter.course);
      if (filter.type) params.set('type', filter.type);
      if (filter.chapter) params.set('chapter', filter.chapter);
      if (filter.keyword) params.set('keyword', filter.keyword);
      const data = await fetchWithLoading('/api/questions?' + params);
      questions.value = data.items || [];
      prepareQuestionState(questions.value);
      totalPages.value = Math.ceil(data.total / data.page_size) || 1;
    };

    const loadRandom = async () => {
      const params = new URLSearchParams({ limit: 20 });
      if (filter.course) params.set('course', filter.course);
      if (filter.type) params.set('type', filter.type);
      if (filter.chapter) params.set('chapter', filter.chapter);
      const data = await fetchWithLoading('/api/questions/random?' + params);
      questions.value = data.items || [];
      prepareQuestionState(questions.value);
      totalPages.value = 1;
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
      setTimeout(() => { submitLock.value = false; }, 1500);
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
      } else {
        if (!ans || (typeof ans === 'string' && ans.trim() === '')) {
          showToast('请输入答案', 'error');
          return;
        }
      }

      const data = await fetchWithLoading('/api/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question_id: q.id, answer: ans })
      });

      results[q.id] = data;
      if (data.correct) {
        showToast('回答正确!', 'success');
      } else {
        showToast('回答错误', 'error');
      }

      // 刷新统计
      loadStats();
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
          if (filter.course && result[filter.course]) {
            chapters.value = result[filter.course];
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
          filter.course = data.course || '';
          filter.type = data.type || '';
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
    const handleKeydown = (e) => {
      if (activeTab.value !== 'quiz') return;
      // 只处理刷题页
      const q = questions.value[0]; // 当前页第一题（主要操作目标）
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
      loadChapters();
      loadQuestions(1);
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
      typeLabel, courseLabel, formatAnswer, barWidth, showToast
    };
  }
}).mount('#app');
