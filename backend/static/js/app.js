const { createApp, ref, reactive, computed, onMounted } = Vue;

createApp({
  setup() {
    const showTab = ref('quiz');
    const theme = ref(localStorage.getItem('theme') || 'light');
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

    const filter = reactive({ course: '', type: '', chapter: '', keyword: '' });
    const chapters = ref([1,2,3,4,5,6,7,8,9,10]);

    const themeLabel = computed(() => theme.value === 'dark' ? '浅色' : '深色');

    const typeLabel = (t) => {
      const map = { single: '单选', multiple: '多选', true_false: '判断', fill_blank: '填空', short_answer: '简答' };
      return map[t] || t;
    };

    const formatAnswer = (ans) => {
      if (Array.isArray(ans)) return ans.join(', ');
      return ans;
    };

    const prepareQuestionState = (items) => {
      items.forEach(q => {
        if (q.type === 'multiple' && !Array.isArray(userAnswers[q.id])) {
          userAnswers[q.id] = [];
        }
      });
    };

    const toggleTheme = () => {
      theme.value = theme.value === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', theme.value);
      localStorage.setItem('theme', theme.value);
    };

    const loadQuestions = async (p = 1) => {
      page.value = p;
      const params = new URLSearchParams({ page: p, page_size: 20 });
      if (filter.course) params.set('course', filter.course);
      if (filter.type) params.set('type', filter.type);
      if (filter.chapter) params.set('chapter', filter.chapter);
      if (filter.keyword) params.set('keyword', filter.keyword);
      const res = await fetch('/api/questions?' + params);
      const data = await res.json();
      questions.value = data.items;
      prepareQuestionState(data.items);
      totalPages.value = Math.ceil(data.total / data.page_size) || 1;
    };

    const loadRandom = async () => {
      const params = new URLSearchParams({ limit: 20 });
      if (filter.course) params.set('course', filter.course);
      if (filter.type) params.set('type', filter.type);
      if (filter.chapter) params.set('chapter', filter.chapter);
      const res = await fetch('/api/questions/random?' + params);
      const data = await res.json();
      questions.value = data.items;
      prepareQuestionState(data.items);
      totalPages.value = 1;
    };

    const submitAnswer = async (q) => {
      let ans = userAnswers[q.id];
      if (q.type === 'multiple') {
        if (!Array.isArray(ans) || ans.length === 0) { alert('请选择至少一项'); return; }
        ans = [...ans].sort();
      }
      if (q.type === 'single' || q.type === 'true_false') {
        if (!ans) { alert('请选择答案'); return; }
      }
      const res = await fetch('/api/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question_id: q.id, answer: ans })
      });
      const data = await res.json();
      results[q.id] = data;
      await loadStats();
      await loadMistakes();
    };

    const showAnswer = (q) => {
      showExplanations[q.id] = !showExplanations[q.id];
    };

    const loadStats = async () => {
      const res = await fetch('/api/stats');
      stats.value = await res.json();
    };

    const loadMistakes = async () => {
      const res = await fetch('/api/mistakes?page=1&page_size=100');
      const data = await res.json();
      mistakes.value = data.items;
    };

    const loadFavorites = async () => {
      const res = await fetch('/api/favorites?page=1&page_size=100');
      const data = await res.json();
      favorites.value = data.items;
      favIds.value = new Set(data.items.map(q => q.id));
    };

    const isFav = (id) => favIds.value.has(id);

    const toggleFav = async (q) => {
      const method = isFav(q.id) ? 'DELETE' : 'POST';
      await fetch(`/api/favorites/${q.id}`, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) });
      await loadFavorites();
      await loadStats();
    };

    onMounted(() => {
      document.documentElement.setAttribute('data-theme', theme.value);
      loadQuestions(1);
      loadStats();
      loadMistakes();
      loadFavorites();
    });

    return {
      showTab, themeLabel, toggleTheme,
      questions, page, totalPages, mode,
      filter, chapters, loadQuestions, loadRandom,
      userAnswers, results, showExplanations,
      submitAnswer, showAnswer, typeLabel, formatAnswer,
      stats, loadStats,
      mistakes, loadMistakes,
      favorites, favIds, isFav, toggleFav
    };
  }
}).mount('#app');
