// ==============================
// State
// ==============================
let allItems = [];
let currentDate = new Date();
let currentPage = 'home';
let currentFilter = 'all';
let currentCategory = '';
let previousItemIds = new Set();
let refreshTimer = null;
let currentDigestTab = localStorage.getItem('digestTab') || 'all';

// ==============================
// Theme & Mobile
// ==============================
function toggleTheme() {
    const dark = document.body.classList.toggle('dark');
    localStorage.setItem('theme', dark ? 'dark' : 'light');
    document.querySelector('.theme-toggle').textContent = dark ? '☀️' : '🌙';
}

function toggleSidebar() {
    document.querySelector('.sidebar').classList.toggle('open');
    document.getElementById('sidebar-overlay').classList.toggle('hidden');
}

// Restore theme on load
(function() {
    if (localStorage.getItem('theme') === 'dark') {
        document.body.classList.add('dark');
        // Theme toggle button text will be set after DOM ready
    }
})();

// ==============================
// Init
// ==============================
document.addEventListener('DOMContentLoaded', () => {
    // Set theme toggle button text
    const themeBtn = document.querySelector('.theme-toggle');
    if (themeBtn) themeBtn.textContent = document.body.classList.contains('dark') ? '☀️' : '🌙';

    updateDateDisplay();
    load();
    loadStats();
    startRefresh();

    const input = document.getElementById('search-input');
    input.addEventListener('input', () => {
        const q = input.value.trim();
        if (!q) { renderCurrentPage(); return; }
        doSearch(q);
    });
    input.addEventListener('keydown', e => {
        if (e.key === 'Escape') { input.value = ''; renderCurrentPage(); }
    });
});

// ==============================
// Data Loading
// ==============================
async function load() {
    try {
        // Load twitter categories mapping (once)
        if (Object.keys(twitterCategories).length === 0) {
            await loadTwitterCategories();
        }

        const r = await fetch('/api/news?limit=1000');
        const d = await r.json();
        const newItems = d.items || [];

        // Detect breaking news (new high-score items or backend-flagged)
        if (previousItemIds.size > 0) {
            const breaking = newItems.filter(i =>
                !previousItemIds.has(i.id) && (i.is_breaking || (i.score || 0) >= 50)
            );
            breaking.forEach(i => showToast(i.title_zh || i.title));
            if (breaking.length > 0) {
                showBreaking(breaking[0].title_zh || breaking[0].title);
            }
        }
        // 首次加载也显示突发新闻
        if (previousItemIds.size === 0) {
            const breakingItems = newItems.filter(i => i.is_breaking);
            if (breakingItems.length > 0) {
                showBreaking(breakingItems[0].title_zh || breakingItems[0].title);
            }
        }

        previousItemIds = new Set(newItems.map(i => i.id));
        allItems = newItems;

        // Auto-detect latest date with data if today has no items
        if (getDateItems().length === 0 && allItems.length > 0) {
            const dates = allItems.map(i => (i.created_at || '').substring(0, 10)).filter(Boolean);
            dates.sort((a, b) => b.localeCompare(a));
            if (dates[0]) {
                currentDate = new Date(dates[0] + 'T12:00:00');
                updateDateDisplay();
            }
        }

        renderCurrentPage();
    } catch (e) {
        // silent
    }
}

async function loadStats() {
    try {
        const r = await fetch('/api/stats');
        const d = await r.json();
        document.getElementById('stats-info').textContent = `${d.unread_count} 条未读`;
    } catch (e) {}

    // 更新突发新闻徽标
    try {
        const breakingCount = allItems.filter(i => i.is_breaking).length;
        const badge = document.getElementById('badge-breaking');
        if (badge) badge.textContent = breakingCount > 0 ? breakingCount : '';
    } catch(e) {}
}

function startRefresh() {
    if (refreshTimer) clearInterval(refreshTimer);
    refreshTimer = setInterval(() => { load(); loadStats(); }, 5 * 60 * 1000);
}

// ==============================
// Common Renderers
// ==============================
function cleanTitle(title) {
    if (!title) return '';
    // Remove "RT by @xxx: " prefix
    title = title.replace(/^RT?\s+by\s+@\w+:\s*/i, '');
    // Remove "R to @xxx: " reply prefix
    title = title.replace(/^R\s+to\s+@\w+:\s*/i, '');
    // Remove URLs
    title = title.replace(/https?:\/\/\S+/g, '').trim();
    // Truncate if too long
    if (title.length > 150) title = title.substring(0, 147) + '...';
    return title;
}

function stripHtml(html) {
    if (!html) return '';
    // Simple HTML tag stripping
    return html.replace(/<[^>]+>/g, ' ').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/\s+/g, ' ').trim();
}

function renderListItem(it) {
    const rawSummary = it.summary_zh || stripHtml(it.content) || '';
    const summary = rawSummary.length > 200 ? rawSummary.substring(0, 197) + '...' : rawSummary;
    const isHot = isBreakingItem(it);
    const displayTitle = cleanTitle(it.title_zh || it.title);
    const subTitle = it.title_zh && it.title_zh !== it.title ? cleanTitle(it.title) : '';
    return `<div class="list-item ${it.is_read ? 'read' : ''} ${isHot ? 'breaking' : ''}"
                onclick="openItem('${it.id}','${esc(it.source_url)}')">
        <div class="list-score">${it.score ? '▲' + it.score : ''}</div>
        <div class="list-body">
            <div class="list-title">${h(displayTitle)}</div>
            ${subTitle ? `<div class="list-title-zh">${h(subTitle)}</div>` : ''}
            ${summary ? `<div class="list-summary">${h(summary)}</div>` : ''}
            <div class="list-meta">
                <span class="src">${h(formatSource(it.source))}</span>
                <span>${h(it.author || '')}</span>
                <span>${timeAgo(it.created_at)}</span>
            </div>
        </div>
        <button class="list-star ${it.is_starred ? 'on' : ''}"
            onclick="event.stopPropagation();toggleStar('${it.id}',this)">
            ${it.is_starred ? '⭐' : '☆'}</button>
    </div>`;
}

function renderItemList(items, listEl) {
    if (items.length === 0) {
        listEl.innerHTML = '<div class="empty-state">暂无内容</div>';
        return;
    }
    listEl.innerHTML = items.map(renderListItem).join('');
}

// ==============================
// Date
// ==============================
function updateDateDisplay() {
    const d = currentDate;
    const w = ['日', '一', '二', '三', '四', '五', '六'];
    document.getElementById('current-date').textContent =
        `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日 星期${w[d.getDay()]}`;
    const today = new Date(); today.setHours(0, 0, 0, 0);
    const sel = new Date(d); sel.setHours(0, 0, 0, 0);
    const nb = document.getElementById('next-btn');
    nb.disabled = sel >= today;
    nb.style.opacity = sel >= today ? '0.3' : '1';
}

async function changeDate(n) {
    const today = new Date(); today.setHours(0, 0, 0, 0);
    const nd = new Date(currentDate);
    nd.setDate(nd.getDate() + n);
    nd.setHours(0, 0, 0, 0);
    if (nd > today) return;
    currentDate = nd;
    updateDateDisplay();
    // If no items for this date, try fetching from /api/daily
    if (getDateItems().length === 0) {
        try {
            const r = await fetch(`/api/daily?date=${toISO(nd)}`);
            const d = await r.json();
            const cats = d.categories || {};
            const existingIds = new Set(allItems.map(i => i.id));
            for (const items of Object.values(cats)) {
                for (const it of items) {
                    if (!existingIds.has(it.id)) { allItems.push(it); existingIds.add(it.id); }
                }
            }
        } catch(e) {}
    }
    if (currentPage === 'home') renderHome();
}

function goToday() {
    currentDate = new Date();
    updateDateDisplay();
    if (currentPage === 'home') renderHome();
}

function toISO(d) {
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

// ==============================
// Classification
// ==============================
const ZH_SOURCES = ['AI科技评论', '36氪', '少数派', '爱范儿'];
const ZH_TWITTER_ACCOUNTS = ['kaifulee', 'dotey', 'op7418', 'tuturetom', 'financeyf5', 'barret_china', 'aigclink', 'hitw93'];

// Twitter handle → display name mapping
const DISPLAY_NAMES = {
    'openai': 'OpenAI', 'anthropicai': 'Anthropic', 'googledeepmind': 'DeepMind',
    'googleai': 'Google AI', 'aiatmeta': 'Meta AI', 'xai': 'xAI',
    'mistralai': 'Mistral AI', 'stabilityai': 'Stability AI', 'huggingface': 'Hugging Face',
    'perplexity_ai': 'Perplexity', 'sama': 'Sam Altman', 'darioamodei': 'Dario Amodei',
    'elonmusk': 'Elon Musk', 'gregbrockman': 'Greg Brockman', 'ilyasut': 'Ilya Sutskever',
    'demishassabis': 'Demis Hassabis', 'kaifulee': '李开复',
    'ylecun': 'Yann LeCun', 'karpathy': 'Andrej Karpathy', 'drjimfan': 'Jim Fan',
    '_akhaliq': 'AK', 'swyx': 'swyx', 'emostaque': 'Emad Mostaque',
    'bindureddy': 'Bindu Reddy', 'jeffdean': 'Jeff Dean', 'fchollet': 'François Chollet',
    'hardmaru': 'David Ha', 'mmitchell_ai': 'Margaret Mitchell', 'simonw': 'Simon Willison',
    'llama_index': 'LlamaIndex', 'a16z': 'a16z', 'sequoia': 'Sequoia',
    'natfriedman': 'Nat Friedman', 'dotey': '宝玉', 'op7418': '歸藏',
    'tuturetom': 'Tom Huang', 'financeyf5': 'YF', 'barret_china': '小胡子哥',
    'aigclink': 'AIGC Link', 'hitw93': 'Tw93',
};

function formatSource(source) {
    if (!source) return '';
    if (source.startsWith('twitter/')) {
        const handle = (source.split('/@')[1] || source.split('/')[1] || '').toLowerCase();
        return DISPLAY_NAMES[handle] || ('@' + handle);
    }
    return source;
}

// Twitter account → category mapping (loaded from API)
let twitterCategories = {};
async function loadTwitterCategories() {
    try {
        const r = await fetch('/api/twitter-categories');
        const d = await r.json();
        twitterCategories = d.categories || {};
    } catch(e) { console.warn('Failed to load twitter categories', e); }
}

function getTwitterCategory(item) {
    if (!item.source.startsWith('twitter/')) return '';
    const account = item.source.split('/@')[1] || item.source.split('/')[1] || '';
    const baseCat = twitterCategories[account.toLowerCase()] || '';
    if (!baseCat) return '';
    // Detect content language from title text
    const title = item.title || '';
    const zhChars = (title.match(/[\u4e00-\u9fff]/g) || []).length;
    const isZh = zhChars > title.length * 0.1 && zhChars >= 3;
    const type = baseCat.startsWith('news') ? 'news' : 'experience';
    const lang = isZh ? 'zh' : 'en';
    return type + '_' + lang;
}

function getTwitterLang(item) {
    const title = item.title || '';
    const zhChars = (title.match(/[\u4e00-\u9fff]/g) || []).length;
    return (zhChars > title.length * 0.1 && zhChars >= 3) ? 'zh' : 'en';
}

function getTwitterType(item) {
    const account = item.source.split('/@')[1] || item.source.split('/')[1] || '';
    const baseCat = twitterCategories[account.toLowerCase()] || '';
    return baseCat.startsWith('news') ? 'news' : 'experience';
}

function getLang(item) {
    const s = item.source || '';
    if (ZH_SOURCES.includes(s)) return 'zh';
    // Chinese Twitter accounts
    if (s.startsWith('twitter/')) {
        const account = s.split('/')[1];
        if (ZH_TWITTER_ACCOUNTS.includes(account)) return 'zh';
    }
    return 'en';
}

function classifyItem(item) {
    const s = (item.source || '').toLowerCase();
    if (s.startsWith('twitter')) return 'twitter';
    if (s === 'github') return 'github';
    if (s === 'huggingface') return 'huggingface';
    if (s.startsWith('reddit')) return 'reddit';
    if (s === 'product hunt' || s === 'producthunt') return 'producthunt';
    if (s === 'hackernews') return 'hackernews';
    if (s.includes('techcrunch')) return 'techcrunch';
    if (s.includes('the verge') || s.includes('theverge')) return 'theverge';
    if (s === 'ai科技评论' || s.includes('leiphone')) return 'leiphone';
    if (s === '36氪') return '36kr';
    if (s === '少数派') return 'sspai';
    if (s === '爱范儿') return 'ifanr';
    return 'news';
}

function getDateItems() {
    const ds = toISO(currentDate);
    return allItems.filter(i => (i.created_at || '').substring(0, 10) === ds);
}

function getCategoryItems(cat) {
    return allItems.filter(i => classifyItem(i) === cat).sort(byScore);
}

function byScore(a, b) {
    return (b.score || 0) - (a.score || 0) || new Date(b.created_at) - new Date(a.created_at);
}

// ==============================
// Navigation
// ==============================
function toggleNavSection(sectionId) {
    const section = document.getElementById(sectionId);
    const toggle = document.getElementById('toggle-' + sectionId);
    if (section.classList.contains('collapsed')) {
        section.classList.remove('collapsed');
        toggle.textContent = '▾';
    } else {
        section.classList.add('collapsed');
        toggle.textContent = '▸';
    }
}

function switchPage(page) {
    currentPage = page;
    currentFilter = 'all';

    // Close mobile sidebar
    document.querySelector('.sidebar').classList.remove('open');
    document.getElementById('sidebar-overlay').classList.add('hidden');

    // Update nav active state
    document.querySelectorAll('.nav-item').forEach(el => {
        el.classList.toggle('active', el.dataset.page === page);
    });

    // Show/hide pages
    document.getElementById('page-home').classList.toggle('hidden', page !== 'home');
    document.getElementById('page-category').classList.toggle('hidden',
        page === 'home' || page === 'starred' || page === 'sources' || page === 'breaking' || page === 'hot-topics' || page === 'ai-settings');
    document.getElementById('page-starred').classList.toggle('hidden', page !== 'starred');
    document.getElementById('page-sources').classList.toggle('hidden', page !== 'sources');
    document.getElementById('page-breaking').classList.toggle('hidden', page !== 'breaking');
    document.getElementById('page-hot-topics').classList.toggle('hidden', page !== 'hot-topics');
    document.getElementById('page-ai-settings').classList.toggle('hidden', page !== 'ai-settings');

    if (page === 'home') {
        renderHome();
    } else if (page === 'breaking') {
        renderBreakingPage();
    } else if (page === 'hot-topics') {
        renderHotTopics();
    } else if (page === 'ai-settings') {
        renderAiSettings();
    } else if (page === 'starred') {
        renderStarred();
    } else if (page === 'sources') {
        renderSources();
    } else if (page === 'en-sources') {
        currentCategory = page;
        renderLangPage('en');
    } else if (page === 'zh-sources') {
        currentCategory = page;
        renderLangPage('zh');
    } else if (page.startsWith('twitter-news-') || page.startsWith('twitter-exp-')) {
        currentCategory = page;
        renderTwitterCategoryPage(page);
    } else {
        currentCategory = page;
        renderCategory(page);
    }
}

function renderCurrentPage() {
    updateBadges();
    if (currentPage === 'home') renderHome();
    else if (currentPage === 'breaking') renderBreakingPage();
    else if (currentPage === 'hot-topics') renderHotTopics();
    else if (currentPage === 'starred') renderStarred();
    else if (currentPage === 'en-sources') renderLangPage('en');
    else if (currentPage === 'zh-sources') renderLangPage('zh');
    else if (currentPage.startsWith('twitter-news-') || currentPage.startsWith('twitter-exp-')) renderTwitterCategoryPage(currentPage);
    else renderCategory(currentPage);
}

// ==============================
// Render: Home
// ==============================
const DIGEST_FILTERS = {
    all: () => true,
    twitter: i => (i.source || '').toLowerCase().startsWith('twitter'),
    github: i => (i.source || '').toLowerCase() === 'github',
    huggingface: i => (i.source || '').toLowerCase() === 'huggingface',
    news: i => ['techcrunch','theverge','hackernews'].includes((i.source || '').toLowerCase()),
    'zh-media': i => ZH_SOURCES.includes(i.source),
};

function switchDigestTab(tab) {
    currentDigestTab = tab;
    localStorage.setItem('digestTab', tab);
    document.querySelectorAll('.digest-tab').forEach(b => {
        b.classList.toggle('active', b.dataset.tab === tab);
    });
    renderHome();
}

function renderHome() {
    // Restore active tab highlight on first render
    document.querySelectorAll('.digest-tab').forEach(b => {
        b.classList.toggle('active', b.dataset.tab === currentDigestTab);
    });

    const items = getDateItems();
    const filterFn = DIGEST_FILTERS[currentDigestTab] || DIGEST_FILTERS.all;
    const top10 = [...items].filter(filterFn).sort(byScore).slice(0, 10);
    const el = document.getElementById('home-digest-list');

    if (top10.length === 0) {
        el.innerHTML = '<div class="empty-state">今日暂无资讯</div>';
        return;
    }

    const rankColors = ['#e6a717', '#8a8a8a', '#b87333'];
    el.innerHTML = top10.map((it, i) => {
        const displayTitle = cleanTitle(it.title_zh || it.title);
        const subTitle = it.title_zh && it.title_zh !== it.title ? cleanTitle(it.title) : '';
        const summary = stripHtml(it.summary_zh || it.content || '');
        const summaryText = summary.length > 120 ? summary.slice(0, 120) + '...' : summary;
        const rankStyle = i < 3 ? `background:${rankColors[i]};color:#fff` : '';
        const langClass = getLang(it) === 'zh' ? 'zh' : 'en';
        return `<div class="digest-card ${it.is_read ? 'read' : ''}"
                    onclick="openItem('${it.id}','${esc(it.source_url)}')">
            <div class="digest-rank" style="${rankStyle}">${i + 1}</div>
            <div class="digest-body">
                <div class="digest-title">${h(displayTitle)}</div>
                ${subTitle ? `<div class="digest-subtitle">${h(subTitle)}</div>` : ''}
                ${summaryText ? `<div class="digest-summary">${h(summaryText)}</div>` : ''}
                <div class="digest-meta">
                    <span class="digest-source ${langClass}">${h(formatSource(it.source))}</span>
                    <span class="digest-time">${timeAgo(it.created_at)}</span>
                    ${it.score ? `<span class="digest-score">▲${it.score}</span>` : ''}
                </div>
            </div>
            <button class="digest-star ${it.is_starred ? 'on' : ''}"
                onclick="event.stopPropagation();toggleStar('${it.id}',this)">
                ${it.is_starred ? '⭐' : '☆'}</button>
        </div>`;
    }).join('');
}

// ==============================
// Render: Category
// ==============================
function renderCategory(cat) {
    const titles = {
        twitter: '🐦 大佬动态',
        github: '💻 热门开源',
        news: '📋 行业新闻',
        huggingface: '🤗 模型发布',
        reddit: '💬 社区热议',
        producthunt: '🚀 新产品',
        hackernews: '📰 HackerNews',
        techcrunch: '📰 TechCrunch',
        theverge: '📰 The Verge',
        leiphone: '📰 AI科技评论',
        '36kr': '📰 36氪',
        sspai: '📰 少数派',
        ifanr: '📰 爱范儿',
        'twitter-news-en': '🐦🇬🇧 AI新闻推特 · 英文区',
        'twitter-news-zh': '🐦🇨🇳 AI新闻推特 · 中文区',
        'twitter-exp-en': '💡🇬🇧 AI经验与资源 · 英文区',
        'twitter-exp-zh': '💡🇨🇳 AI经验与资源 · 中文区',
    };
    document.getElementById('cat-page-title').textContent = titles[cat] || cat;

    let items = getCategoryItems(cat);

    if (currentFilter === 'unread') items = items.filter(i => !i.is_read);
    if (currentFilter === 'starred') items = items.filter(i => i.is_starred);

    renderItemList(items, document.getElementById('cat-item-list'));
}

// ==============================
// Render: Language Page
// ==============================
function renderLangPage(lang) {
    const title = lang === 'zh' ? '🇨🇳 中文信息源' : '🌐 英文信息源';
    document.getElementById('cat-page-title').textContent = title;

    // switchPage already handles visibility, just ensure category page is shown
    document.getElementById('page-category').classList.remove('hidden');

    let items = allItems.filter(i => getLang(i) === lang).sort(byScore);

    if (currentFilter === 'unread') items = items.filter(i => !i.is_read);
    if (currentFilter === 'starred') items = items.filter(i => i.is_starred);

    renderItemList(items, document.getElementById('cat-item-list'));
}

// ==============================
// Render: Twitter Category Pages
// ==============================
function renderTwitterCategoryPage(page) {
    // page format: twitter-news-en, twitter-news-zh, twitter-exp-en, twitter-exp-zh
    const [, type, lang] = page.split('-'); // type: news/exp, lang: en/zh
    const targetType = type === 'news' ? 'news' : 'experience';

    const titles = {
        'twitter-news-en': '🐦🇬🇧 AI新闻推特 · 英文区',
        'twitter-news-zh': '🐦🇨🇳 AI新闻推特 · 中文区',
        'twitter-exp-en': '💡🇬🇧 AI经验与资源 · 英文区',
        'twitter-exp-zh': '💡🇨🇳 AI经验与资源 · 中文区',
    };

    document.getElementById('cat-page-title').textContent = titles[page] || page;
    document.getElementById('page-home').classList.add('hidden');
    document.getElementById('page-starred').classList.add('hidden');
    document.getElementById('page-sources').classList.add('hidden');
    document.getElementById('page-breaking').classList.add('hidden');
    document.getElementById('page-category').classList.remove('hidden');

    let items = allItems.filter(i => {
        if (!i.source.startsWith('twitter/')) return false;
        const account = i.source.split('/@')[1] || i.source.split('/')[1] || '';
        const baseCat = twitterCategories[account.toLowerCase()] || '';
        if (!baseCat) return false;
        // For language filtering, check content language
        // For type filtering, check account category
        const itemType = baseCat.startsWith('news') ? 'news' : 'experience';
        if (itemType !== targetType) return false;
        return getTwitterLang(i) === lang;
    }).sort(byScore);

    // If no items found (e.g. news-zh has no Chinese tweets from news accounts),
    // fall back to showing ALL twitter items in that language
    if (items.length === 0) {
        items = allItems.filter(i => {
            if (!i.source.startsWith('twitter/')) return false;
            const account = i.source.split('/@')[1] || i.source.split('/')[1] || '';
            if (!twitterCategories[account.toLowerCase()]) return false;
            return getTwitterLang(i) === lang;
        }).sort(byScore);
    }

    if (currentFilter === 'unread') items = items.filter(i => !i.is_read);
    if (currentFilter === 'starred') items = items.filter(i => i.is_starred);

    renderItemList(items, document.getElementById('cat-item-list'));
}

// ==============================
// Render: Starred
// ==============================
// ==============================
// Hot Topics
// ==============================
const HOT_KEYWORDS = [
    'claude','gpt','chatgpt','openai','anthropic','google','gemini','llama','meta',
    'deepseek','mistral','grok','sora','midjourney','stable diffusion','copilot',
    'cursor','devin','manus','agent','rag','mcp','o3','o4','qwen','kimi',
    'doubao','perplexity','huggingface','langchain','vscode','codex',
    'reasoning','multimodal','fine-tuning','微调','embedding','transformer',
    'diffusion','vision','robotics','self-driving','autonomous',
    'apple intelligence','nvidia','amd','tpu','gpu','chip',
    '豆包','通义','文心','智谱','月之暗面','零一万物','百川',
    'claude code','windsurf','bolt','lovable','v0','replit'
];

const SOURCE_ICONS = {
    twitter: '🐦',
    hackernews: '📰',
    reddit: '💬',
    github: '💻',
    huggingface: '🤗',
    rss: '📋',
    producthunt: '🚀'
};

function getSourceType(source) {
    const s = (source || '').toLowerCase();
    if (s.startsWith('twitter')) return 'twitter';
    if (s === 'hackernews') return 'hackernews';
    if (s.startsWith('reddit')) return 'reddit';
    if (s === 'github') return 'github';
    if (s === 'huggingface') return 'huggingface';
    if (s === 'product hunt' || s === 'producthunt') return 'producthunt';
    return 'rss';
}

function computeHotTopics() {
    const now = Date.now();
    const topicMap = {}; // keyword → { keyword, items, sources, totalScore }

    for (const item of allItems) {
        const title = ((item.title || '') + ' ' + (item.title_zh || '')).toLowerCase();
        const matched = new Set();

        for (const kw of HOT_KEYWORDS) {
            if (title.includes(kw.toLowerCase())) {
                matched.add(kw);
            }
        }

        if (matched.size === 0) continue;

        // Time decay: items within 24h get full weight, decays over 72h
        const itemTime = new Date(item.created_at).getTime();
        const hoursAgo = Math.max(0, (now - itemTime) / 3600000);
        const timeDecay = 1 / (1 + hoursAgo / 24);

        const baseScore = (item.score || 0) * 0.1 + 1; // min 1 point per item
        const itemScore = baseScore * timeDecay;
        const srcType = getSourceType(item.source);

        for (const kw of matched) {
            if (!topicMap[kw]) {
                topicMap[kw] = { keyword: kw, items: [], sources: {}, totalScore: 0 };
            }
            topicMap[kw].items.push(item);
            topicMap[kw].sources[srcType] = (topicMap[kw].sources[srcType] || 0) + 1;
            topicMap[kw].totalScore += itemScore;
        }
    }

    // Cross-platform bonus: more source types = higher score
    const topics = Object.values(topicMap).filter(t => t.items.length >= 2);
    for (const t of topics) {
        const platformCount = Object.keys(t.sources).length;
        if (platformCount >= 3) t.totalScore *= 2.0;
        else if (platformCount >= 2) t.totalScore *= 1.5;
    }

    // Merge overlapping topics (e.g. "claude" and "anthropic" often co-occur)
    // Simple: if >50% items overlap, keep the higher-scored one
    topics.sort((a, b) => b.totalScore - a.totalScore);
    const merged = [];
    const used = new Set();
    for (const t of topics) {
        if (used.has(t.keyword)) continue;
        // Check overlap with already-selected topics
        const tIds = new Set(t.items.map(i => i.id));
        let shouldSkip = false;
        for (const m of merged) {
            const mIds = new Set(m.items.map(i => i.id));
            const overlap = [...tIds].filter(id => mIds.has(id)).length;
            if (overlap > Math.min(tIds.size, mIds.size) * 0.5) {
                // Merge into the existing topic
                for (const item of t.items) {
                    if (!mIds.has(item.id)) {
                        m.items.push(item);
                        const srcType = getSourceType(item.source);
                        m.sources[srcType] = (m.sources[srcType] || 0) + 1;
                    }
                }
                m.totalScore += t.totalScore * 0.3;
                m.keyword = m.keyword + ' / ' + t.keyword;
                shouldSkip = true;
                break;
            }
        }
        if (!shouldSkip) {
            merged.push({...t, items: [...t.items]});
        }
        used.add(t.keyword);
    }

    return merged.sort((a, b) => b.totalScore - a.totalScore).slice(0, 10);
}

function renderHotTopics() {
    const container = document.getElementById('page-hot-topics');
    const topics = computeHotTopics();

    if (topics.length === 0) {
        container.innerHTML = `
            <div class="category-header"><h2>📊 AI 热点</h2>
            <p class="category-desc">近期被多平台热议的 AI 话题</p></div>
            <div class="empty-state">暂无热点话题</div>`;
        return;
    }

    const maxScore = topics[0].totalScore;

    container.innerHTML = `
        <div class="category-header">
            <h2>📊 AI 热点</h2>
            <p class="category-desc">近期被多平台热议的 AI 话题（基于跨平台讨论频率和时间衰减自动聚合）</p>
        </div>
        <div class="hot-topics-list">
            ${topics.map((t, i) => {
                const pct = Math.round(t.totalScore / maxScore * 100);
                const srcBadges = Object.entries(t.sources)
                    .sort((a, b) => b[1] - a[1])
                    .map(([type, count]) => `<span class="src-badge">${SOURCE_ICONS[type] || '📰'}${count}</span>`)
                    .join('');
                // Top 3 items for this topic
                const topItems = [...t.items]
                    .sort((a, b) => (b.score || 0) - (a.score || 0))
                    .slice(0, 3);
                const itemsHtml = topItems.map(it => `
                    <div class="hot-ref-item ${it.is_read ? 'read' : ''}"
                         onclick="openItem('${it.id}','${esc(it.source_url)}')">
                        <span class="hot-ref-src">${h(formatSource(it.source))}</span>
                        <span class="hot-ref-title">${h(cleanTitle(it.title_zh || it.title))}</span>
                        <span class="hot-ref-time">${timeAgo(it.created_at)}</span>
                    </div>`).join('');

                return `
                <div class="hot-topic-card">
                    <div class="hot-topic-header">
                        <span class="hot-rank">#${i + 1}</span>
                        <span class="hot-keyword">${h(t.keyword)}</span>
                        <span class="hot-count">${t.items.length} 条讨论</span>
                    </div>
                    <div class="hot-bar-wrap">
                        <div class="hot-bar" style="width:${pct}%"></div>
                    </div>
                    <div class="hot-sources">${srcBadges}</div>
                    <div class="hot-refs">${itemsHtml}</div>
                </div>`;
            }).join('')}
        </div>`;
}

// ==============================
// Breaking News Page
// ==============================
const BREAKING_LEVELS = {
    3: { icon: '🔴', label: '紧急', color: '#ef4444' },
    2: { icon: '🟠', label: '重要', color: '#f97316' },
    1: { icon: '🟡', label: '关注', color: '#eab308' },
};

const BREAKING_CATEGORIES = {
    new_model:    { icon: '🚀', label: '新模型发布' },
    new_feature:  { icon: '✨', label: '新功能/产品' },
    github_hot:   { icon: '🔥', label: 'GitHub 热门' },
    major_news:   { icon: '📢', label: '重大新闻' },
};

function getBreakingCategory(item) {
    const reason = item.breaking_reason || '';
    if (reason.startsWith('[new_model]')) return 'new_model';
    if (reason.startsWith('[new_feature]')) return 'new_feature';
    if (reason.startsWith('[github_hot]')) return 'github_hot';
    return 'major_news';
}

function renderBreakingItem(it) {
    const cleanReason = (it.breaking_reason || '').replace(/^\[.*?\]\s*/, '');
    const readIds = JSON.parse(localStorage.getItem('breakingRead') || '[]');
    const isRead = readIds.includes(it.id);
    const level = it.breaking_level || 0;
    const levelInfo = BREAKING_LEVELS[level] || { icon: '', label: '' };
    const fallbackText = (it.title_zh && it.title_zh !== it.title) ? it.title : (it.content || it.title || '');
    const snippetRaw = stripHtml(it.summary_zh || it.content || fallbackText || '');
    const snippet = snippetRaw.length > 140 ? snippetRaw.slice(0, 140) + '...' : snippetRaw;
    return `
        <div class="list-item breaking ${isRead ? 'read' : 'unread'}"
            onclick="markBreakingRead('${it.id}');openItem('${it.id}','${esc(it.source_url)}')">
            <div class="list-score">${isRead ? '📰' : '🔥'}</div>
            <div class="list-body">
                <div class="breaking-reason">${h(cleanReason)}${level ? ` <span class="breaking-level-badge" style="background:${BREAKING_LEVELS[level].color}">${levelInfo.icon} ${levelInfo.label}</span>` : ''}</div>
                <div class="list-title">${h(cleanTitle(it.title_zh || it.title))}</div>
                ${it.title_zh && it.title_zh !== it.title ? `<div class="list-title-zh">${h(cleanTitle(it.title))}</div>` : ''}
                <div class="breaking-snippet">${h(snippet || '点击查看详情')}</div>
                <div class="list-meta">
                    <span class="src">${h(formatSource(it.source))}</span>
                    <span>${h(it.author || '')}</span>
                    <span>${timeAgo(it.created_at)}</span>
                </div>
            </div>
            <button class="list-star ${it.is_starred ? 'on' : ''}"
                onclick="event.stopPropagation();toggleStar('${it.id}',this)">⭐</button>
        </div>`;
}

async function renderBreakingPage() {
    const container = document.getElementById('page-breaking');
    container.classList.remove('hidden');

    // markBreakingRead helper
    if (!window.markBreakingRead) {
        window.markBreakingRead = function(id) {
            const readIds = JSON.parse(localStorage.getItem('breakingRead') || '[]');
            if (!readIds.includes(id)) {
                readIds.push(id);
                localStorage.setItem('breakingRead', JSON.stringify(readIds));
            }
        };
    }

    try {
        const r = await fetch('/api/breaking?limit=50');
        const d = await r.json();
        let items = d.items || [];

        // Fallback: if no strict breaking items, show recent high-value candidates
        if (items.length === 0) {
            const now = Date.now();
            items = (allItems || [])
                .filter(i => i && i.created_at)
                .filter(i => now - new Date(i.created_at).getTime() <= 48 * 3600 * 1000)
                .sort(byScore)
                .slice(0, 10)
                .map(i => ({
                    ...i,
                    is_breaking: true,
                    breaking_level: 1,
                    breaking_reason: i.breaking_reason || '[major_news] 候选热点（自动回退）',
                }));
        }

        const breakingBadge = document.getElementById('badge-breaking');
        if (breakingBadge) {
            const readIds = JSON.parse(localStorage.getItem('breakingRead') || '[]');
            const unreadCount = items.filter(i => !readIds.includes(i.id)).length;
            breakingBadge.textContent = unreadCount > 0 ? unreadCount : '';
        }

        // 按等级分组（level 0 视为 level 1 关注）
        const levelGroups = { 3: {}, 2: {}, 1: {} };
        for (const it of items) {
            const level = (it.breaking_level >= 1 && it.breaking_level <= 3) ? it.breaking_level : 1;
            const cat = getBreakingCategory(it);
            if (!levelGroups[level][cat]) levelGroups[level][cat] = [];
            levelGroups[level][cat].push(it);
        }

        let sectionsHtml = '';
        // 按紧急 > 重要 > 关注 的顺序显示
        for (const level of [3, 2, 1]) {
            const levelInfo = BREAKING_LEVELS[level];
            const groups = levelGroups[level];
            let levelHtml = '';
            
            for (const [cat, catItems] of Object.entries(groups)) {
                if (catItems.length === 0) continue;
                const info = BREAKING_CATEGORIES[cat] || { icon: '📰', label: cat };
                levelHtml += `
                    <section class="breaking-section">
                        <h3 class="breaking-section-title">${info.icon} ${info.label} <span class="breaking-count">${catItems.length}</span></h3>
                        <div class="news-list">
                            ${catItems.map(renderBreakingItem).join('')}
                        </div>
                    </section>`;
            }
            
            if (levelHtml) {
                sectionsHtml += `
                    <div class="breaking-level-group" style="border-left:4px solid ${levelInfo.color}; padding-left:12px; margin-bottom:20px;">
                        <h2 class="breaking-level-title">${levelInfo.icon} ${levelInfo.label}</h2>
                        ${levelHtml}
                    </div>`;
            }
        }

        container.innerHTML = `
            <div class="category-header">
                <h2>🔥 突发新闻</h2>
                <p class="category-desc">按等级分类的突发资讯：🔴 紧急 | 🟠 重要 | 🟡 关注</p>
            </div>
            ${items.length === 0 ? '<div class="empty-state">暂无突发新闻</div>' : sectionsHtml}
        `;
    } catch(e) {
        container.innerHTML = '<div class="empty-state">加载突发新闻失败</div>';
    }
}

function renderStarred() {
    const items = allItems.filter(i => i.is_starred).sort(byScore);
    renderItemList(items, document.getElementById('starred-list'));
}

// ==============================
// Filter
// ==============================
function setFilter(filter, btn) {
    currentFilter = filter;
    document.querySelectorAll('.filter-tabs .tab').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
    renderCategory(currentCategory);
}

// ==============================
// Search
// ==============================
function doSearch(q) {
    q = q.toLowerCase();
    const matched = allItems.filter(i =>
        (i.title || '').toLowerCase().includes(q) ||
        (i.title_zh || '').toLowerCase().includes(q) ||
        (i.summary_zh || '').toLowerCase().includes(q) ||
        (i.author || '').toLowerCase().includes(q) ||
        (i.source || '').toLowerCase().includes(q)
    );

    document.getElementById('page-home').classList.add('hidden');
    document.getElementById('page-starred').classList.add('hidden');
    document.getElementById('page-category').classList.remove('hidden');
    document.getElementById('cat-page-title').innerHTML = `<a href="#" onclick="event.preventDefault();switchPage('${currentPage}')" style="color:var(--accent);text-decoration:none;margin-right:8px">← 返回</a> 搜索结果 (${matched.length})`;

    const list = document.getElementById('cat-item-list');
    renderItemList(matched.sort(byScore), list);
}

// ==============================
// Badges
// ==============================
function updateBadges() {
    const enCount = allItems.filter(i => getLang(i) === 'en' && !i.is_read).length;
    const zhCount = allItems.filter(i => getLang(i) === 'zh' && !i.is_read).length;
    const enBadge = document.getElementById('badge-en-sources');
    const zhBadge = document.getElementById('badge-zh-sources');
    if (enBadge) enBadge.textContent = enCount > 0 ? enCount : '';
    if (zhBadge) zhBadge.textContent = zhCount > 0 ? zhCount : '';
}

// ==============================
// Breaking News Detection
// ==============================
function isBreakingItem(item) {
    // 优先使用后端检测结果
    if (item.is_breaking) return true;
    // 兼容：1小时内高分也算突发
    if (!item.created_at) return false;
    const age = Date.now() - new Date(item.created_at).getTime();
    const oneHour = 3600000;
    return age < oneHour && (item.score || 0) >= 30;
}

function showBreaking(text) {
    const bar = document.getElementById('breaking-bar');
    document.getElementById('breaking-text').textContent = text;
    bar.classList.remove('hidden');
}

function dismissBreaking() {
    document.getElementById('breaking-bar').classList.add('hidden');
}

function showToast(text) {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = '🔴 新热点: ' + text;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 5000);
}

// ==============================
// Actions
// ==============================
function openItem(id, url) {
    markRead(id);
    if (url) window.open(url, '_blank');
}

async function markRead(id) {
    try {
        await fetch(`/api/news/${id}/read`, { method: 'POST' });
        const item = allItems.find(i => i.id === id);
        if (item) item.is_read = true;
        loadStats();
        // Refresh current view cards
        document.querySelectorAll(`[onclick*="${id}"]`).forEach(el => el.classList.add('read'));
    } catch (e) {}
}

async function toggleStar(id, btn) {
    try {
        await fetch(`/api/news/${id}/star`, { method: 'POST' });
        const item = allItems.find(i => i.id === id);
        if (item) {
            item.is_starred = !item.is_starred;
            btn.textContent = item.is_starred ? '⭐' : '☆';
            btn.classList.toggle('on');
        }
    } catch (e) {}
}

// ==============================
// Utility
// ==============================
function h(s) {
    if (!s) return '';
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}

function esc(s) {
    return (s || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'");
}

function timeAgo(iso) {
    if (!iso) return '';
    const ms = Date.now() - new Date(iso).getTime();
    const m = Math.floor(ms / 60000);
    if (m < 1) return '刚刚';
    if (m < 60) return m + '分钟前';
    const hr = Math.floor(ms / 3600000);
    if (hr < 24) return hr + '小时前';
    const day = Math.floor(ms / 86400000);
    if (day < 7) return day + '天前';
    const dt = new Date(iso);
    return (dt.getMonth() + 1) + '月' + dt.getDate() + '日';
}

// ==============================
// Subscriptions / Sources Management
// ==============================
async function renderSources() {
    const list = document.getElementById('sources-list');
    try {
        const r = await fetch('/api/subscriptions');
        const d = await r.json();
        const subs = d.items || [];
        if (subs.length === 0) {
            list.innerHTML = '<div class="empty-state">暂无订阅源，请在上方添加</div>';
            return;
        }
        list.innerHTML = subs.map(s => `
            <div class="sub-item">
                <span class="sub-type">${h(s.type)}</span>
                <div class="sub-info">
                    <div class="sub-value">${h(s.value)}</div>
                    ${s.label && s.label !== s.value ? `<div class="sub-label">${h(s.label)}</div>` : ''}
                </div>
                <button class="sub-delete" onclick="deleteSubscription('${s.id}')">删除</button>
            </div>
        `).join('');
    } catch (e) {
        list.innerHTML = '<div class="empty-state">加载失败</div>';
    }
}

async function addSubscription() {
    const type = document.getElementById('sub-type').value;
    const value = document.getElementById('sub-value').value.trim();
    const label = document.getElementById('sub-label').value.trim();

    if (!value) return;

    try {
        await fetch('/api/subscriptions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ type, value, label })
        });
        document.getElementById('sub-value').value = '';
        document.getElementById('sub-label').value = '';
        renderSources();
    } catch (e) {}
}

async function deleteSubscription(id) {
    try {
        await fetch(`/api/subscriptions/${id}`, { method: 'DELETE' });
        renderSources();
    } catch (e) {}
}

// ==============================
// LLM Settings
// ==============================
async function loadLlmSettings() {
    try {
        const r = await fetch('/api/settings/llm');
        const d = await r.json();
        document.getElementById('llm-api-base').value = d.api_base || '';
        document.getElementById('llm-api-key').placeholder = d.configured ? `已配置 (${d.api_key_masked})` : 'sk-...';
        document.getElementById('llm-model').value = d.model || '';
        document.getElementById('llm-status').textContent = d.configured ? '✅ 已配置' : '⚠️ 未配置';
        document.getElementById('llm-status').style.color = d.configured ? 'var(--green)' : 'var(--orange)';
    } catch(e) {}
}

async function saveLlmSettings() {
    const body = {};
    const base = document.getElementById('llm-api-base').value.trim();
    const key = document.getElementById('llm-api-key').value.trim();
    const model = document.getElementById('llm-model').value.trim();
    if (base) body.api_base = base;
    if (key) body.api_key = key;
    if (model) body.model = model;
    try {
        const r = await fetch('/api/settings/llm', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        const d = await r.json();
        document.getElementById('llm-status').textContent = d.ok ? '✅ ' + d.message : '❌ ' + d.message;
        document.getElementById('llm-status').style.color = d.ok ? 'var(--green)' : 'var(--accent)';
        if (d.ok) loadLlmSettings();
    } catch(e) {
        document.getElementById('llm-status').textContent = '❌ 保存失败';
    }
}

async function testLlm() {
    document.getElementById('llm-status').textContent = '⏳ 测试中...';
    try {
        const r = await fetch('/api/settings/llm/test', { method: 'POST' });
        const d = await r.json();
        document.getElementById('llm-status').textContent = d.ok ? '✅ ' + d.message : '❌ ' + d.message;
        document.getElementById('llm-status').style.color = d.ok ? 'var(--green)' : 'var(--accent)';
    } catch(e) {
        document.getElementById('llm-status').textContent = '❌ 测试失败';
    }
}

// LLM Presets
const LLM_PRESETS = [
    { name: 'DeepSeek', base: 'https://api.deepseek.com/v1', model: 'deepseek-chat', color: '#4a90d9', free: '注册送 500万 tokens' },
    { name: '硅基流动', base: 'https://api.siliconflow.cn/v1', model: 'Qwen/Qwen2.5-7B-Instruct', color: '#7c3aed', free: '免费模型可用' },
    { name: 'Groq', base: 'https://api.groq.com/openai/v1', model: 'llama-3.3-70b-versatile', color: '#f55036', free: '免费，速度极快' },
    { name: 'Gemini', base: 'https://generativelanguage.googleapis.com/v1beta/openai', model: 'gemini-2.0-flash', color: '#4285f4', free: '免费额度充足' },
    { name: '通义千问', base: 'https://dashscope.aliyuncs.com/compatible-mode/v1', model: 'qwen-plus', color: '#6236ff', free: '注册送100万 tokens' },
    { name: '智谱', base: 'https://open.bigmodel.cn/api/paas/v4', model: 'glm-4-flash', color: '#2d5af0', free: 'flash 模型免费' },
    { name: 'OpenAI', base: 'https://api.openai.com/v1', model: 'gpt-4o-mini', color: '#10a37f', free: '' },
    { name: 'Claude', base: 'https://api.anthropic.com/v1', model: 'claude-sonnet-4-20250514', color: '#d97706', free: '' },
    { name: '豆包', base: 'https://ark.cn-beijing.volces.com/api/v3', model: 'doubao-pro-32k', color: '#ff6b35', free: '注册送50万 tokens' },
    { name: 'Kimi', base: 'https://api.moonshot.cn/v1', model: 'moonshot-v1-8k', color: '#1a1a2e', free: '注册送 tokens' },
    { name: '百川', base: 'https://api.baichuan-ai.com/v1', model: 'Baichuan4', color: '#e84142', free: '' },
];

function applyPreset(preset) {
    document.getElementById('llm-api-base').value = preset.base;
    document.getElementById('llm-model').value = preset.model;
    document.getElementById('llm-api-key').value = '';
    document.getElementById('llm-api-key').focus();
    document.getElementById('llm-status').textContent = `已选择 ${preset.name}，请填入 API Key 后保存`;
    document.getElementById('llm-status').style.color = 'var(--blue)';
}

function renderAiSettings() {
    const container = document.getElementById('llm-presets');
    container.innerHTML = LLM_PRESETS.map((p, i) =>
        `<button onclick="applyPreset(LLM_PRESETS[${i}])" style="padding:6px 14px;border:2px solid ${p.color};background:transparent;color:${p.color};border-radius:20px;cursor:pointer;font-size:0.85em;font-weight:600;transition:all 0.15s;position:relative" onmouseover="this.style.background='${p.color}';this.style.color='#fff'" onmouseout="this.style.background='transparent';this.style.color='${p.color}'">${p.name}${p.free ? `<span style="display:block;font-size:0.7em;font-weight:400;opacity:0.8">🎁 ${p.free}</span>` : ''}</button>`
    ).join('');
    loadLlmSettings();
}
