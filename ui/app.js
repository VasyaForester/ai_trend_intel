/* global Chart */

function isoWeekStart(d) {
  const date = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  const day = date.getUTCDay() || 7; // Mon=1..Sun=7
  date.setUTCDate(date.getUTCDate() - (day - 1));
  date.setUTCHours(0, 0, 0, 0);
  return date;
}

function formatWeekLabel(date) {
  const dd = String(date.getUTCDate()).padStart(2, "0");
  const mm = String(date.getUTCMonth() + 1).padStart(2, "0");
  return `${dd}.${mm}`;
}

function linearTrendScore(series) {
  // simple slope estimate over last 6 points
  const n = Math.min(6, series.length);
  if (n < 2) return 0;
  const start = series.length - n;
  let sumX = 0, sumY = 0, sumXY = 0, sumXX = 0;
  for (let i = 0; i < n; i++) {
    const x = i;
    const y = series[start + i];
    sumX += x; sumY += y; sumXY += x * y; sumXX += x * x;
  }
  const denom = (n * sumXX - sumX * sumX) || 1;
  return (n * sumXY - sumX * sumY) / denom;
}

function growthTrendScore(series) {
  const points = growthPercentPoints(series);
  return points ? points[points.length - 1] : 0;
}

function average(values) {
  if (!values.length) return 0;
  return values.reduce((sum, value) => sum + Number(value || 0), 0) / values.length;
}

function growthSelectionFrom(seriesByKeyword, limit = 5) {
  return Object.entries(seriesByKeyword || {})
    .map(([key, series]) => ({ key, score: growthTrendScore(series), total: sum(series) }))
    .filter((item) => item.score > 0)
    .sort((a, b) => b.score - a.score || b.total - a.total)
    .slice(0, limit)
    .map((item, index) => ({ key: item.key, color: chartColor(index) }));
}

function growthPercentPoints(series) {
  if (!Array.isArray(series) || series.length < 3) return null;
  const chunk = Math.max(1, Math.floor(series.length / 3));
  const start = average(series.slice(0, chunk));
  const mid = average(series.slice(chunk, chunk * 2));
  const end = average(series.slice(chunk * 2));
  if (mid < start || end < mid) return null;
  const baseline = Math.max(1, start);
  const midGrowth = ((mid - start) / baseline) * 100;
  const endGrowth = ((end - start) / baseline) * 100;
  if (endGrowth <= 0) return null;
  return [0, roundPercent(midGrowth), roundPercent(endGrowth)];
}

function growthSeriesFrom(seriesByKeyword, keywords) {
  const out = {};
  keywords.forEach((keyword) => {
    const points = growthPercentPoints(seriesByKeyword[keyword.key]);
    if (points) out[keyword.key] = points;
  });
  return out;
}

function roundPercent(value) {
  return Math.round(value * 100) / 100;
}

function sum(values) {
  return (values || []).reduce((total, value) => total + Number(value || 0), 0);
}

function chartColor(index) {
  const colors = ["#22d3ee", "#a855f7", "#60a5fa", "#f59e0b", "#34d399", "#f472b6", "#facc15"];
  return colors[index % colors.length];
}

const now = new Date();
const startWeek = isoWeekStart(new Date(now.getTime() - 11 * 7 * 24 * 3600 * 1000));
const weekLabels = Array.from({ length: 12 }, (_, i) => {
  const d = new Date(startWeek.getTime() + i * 7 * 24 * 3600 * 1000);
  return formatWeekLabel(d);
});

// Primary path is loading real data from `ui/data.json`.
const fallbackData = {
  meta: { generatedAt: null, windowWeeks: 12, note: "No data loaded. Generate ui/data.json with scripts/collect_serpapi.py." },
  keywords: [],
  seriesByKeyword: {},
  topDocs: [],
  topSources: []
};

async function loadData() {
  try {
    const res = await fetch("./data.json", { cache: "no-store" });
    if (!res.ok) return fallbackData;
    const json = await res.json();
    if (!Array.isArray(json?.keywords) || !json.keywords.length || !json?.seriesByKeyword) return fallbackData;
    return { ...fallbackData, ...json };
  } catch {
    return fallbackData;
  }
}

async function loadArxivLinks() {
  try {
    const res = await fetch("./arxiv_links.json", { cache: "no-store" });
    if (!res.ok) return { meta: {}, papers: [] };
    return await res.json();
  } catch {
    return { meta: {}, papers: [] };
  }
}

function renderTopDocs(topDocs) {
  const el = document.getElementById("topDocs");
  el.innerHTML = "";
  if (!Array.isArray(topDocs) || topDocs.length === 0) {
    const li = document.createElement("li");
    li.innerHTML = `<div class="docMeta">Пока нет данных. Подключи пайплайн и обнови <code>ui/data.json</code>.</div>`;
    el.appendChild(li);
    return;
  }
  topDocs.forEach((d) => {
    const dateText = formatDocDate(d.date);
    const li = document.createElement("li");
    li.innerHTML = `
      <div class="docTitle">${escapeHtml(d.title)}</div>
      <div class="docMeta">
        <span>${escapeHtml(d.publisher)}</span>
        ${dateText ? `<span> · </span><span>${escapeHtml(dateText)}</span>` : ""}
        <span> · </span>
        <a class="docLink" href="${d.url}" target="_blank" rel="noreferrer">Открыть</a>
      </div>
      <div class="docMeta">${escapeHtml(d.why)}</div>
    `;
    el.appendChild(li);
  });
}

function renderArxivLinks(arxivData) {
  const metaEl = document.getElementById("arxivMeta");
  const listEl = document.getElementById("arxivPapers");
  const papers = Array.isArray(arxivData?.papers) ? arxivData.papers : [];
  const meta = arxivData?.meta || {};

  const total = Number(meta.totalPapers || papers.length || 0);
  const generated = meta.generatedAt ? ` · обновлено ${formatDocDate(String(meta.generatedAt).slice(0, 10))}` : "";
  metaEl.textContent = `${total} ссылок накоплено${generated}`;

  listEl.innerHTML = "";
  if (papers.length === 0) {
    const li = document.createElement("li");
    li.innerHTML = `<div class="docMeta">Пока нет arXiv-ссылок. Запусти <code>python scripts/collect_arxiv.py</code> или watcher.</div>`;
    listEl.appendChild(li);
    return;
  }

  papers.slice(0, 10).forEach((paper) => {
    const li = document.createElement("li");
    const dateText = formatDocDate(paper.published || paper.updated);
    const categories = Array.isArray(paper.categories) ? paper.categories.join(", ") : "";
    const matched = Array.isArray(paper.matchedKeywords) ? paper.matchedKeywords.join(", ") : "";
    li.innerHTML = `
      <div class="docTitle">${escapeHtml(paper.title || "Untitled arXiv paper")}</div>
      <div class="docMeta">
        ${dateText ? `<span>${escapeHtml(dateText)}</span><span> · </span>` : ""}
        ${categories ? `<span>${escapeHtml(categories)}</span><span> · </span>` : ""}
        <a class="docLink" href="${paper.url}" target="_blank" rel="noreferrer">arXiv</a>
        ${paper.pdfUrl ? `<span> · </span><a class="docLink" href="${paper.pdfUrl}" target="_blank" rel="noreferrer">PDF</a>` : ""}
      </div>
      ${matched ? `<div class="docMeta">Ключевые слова: ${escapeHtml(matched)}</div>` : ""}
    `;
    listEl.appendChild(li);
  });
}

function renderTopSources(topSources) {
  const el = document.getElementById("topSources");
  el.innerHTML = "";
  if (!Array.isArray(topSources) || topSources.length === 0) {
    const li = document.createElement("li");
    li.innerHTML = `<div class="docMeta">Пока нет данных. Подключи пайплайн и обнови <code>ui/data.json</code>.</div>`;
    el.appendChild(li);
    return;
  }
  topSources.forEach((s) => {
    const li = document.createElement("li");
    const count = Number(s.count || 0);
    li.innerHTML = `
      <div class="sourceRow">
        <a class="sourceName docLink" href="${s.url}" target="_blank" rel="noreferrer">${escapeHtml(s.name)}</a>
        <div class="sourceCount">${count} сообщений</div>
      </div>
    `;
    el.appendChild(li);
  });
}

function renderForecast(keywords, seriesByKeyword) {
  const scores = keywords.map((k) => ({
    key: k.key,
    score: linearTrendScore(seriesByKeyword[k.key] || []),
  }));
  scores.sort((a, b) => b.score - a.score);
  const hottest = scores[0];

  const forecast = document.getElementById("forecast");
  const topic = hottest?.key || "LLM security";
  forecast.textContent =
    `Согласно динамике упоминаний за последние 12 недель, в следующем квартале наиболее «горячей» темой ` +
    `в области кибербезопасности AI с высокой вероятностью станет «${topic}». ` +
    `Рекомендуется заранее подготовить практики: моделирование угроз, контроль доступа к инструментам агентов, ` +
    `политики для RAG/контекста, мониторинг инцидентов и тестирование защитных мер на собственных сценариях.`;
}

function renderLineChart(canvasId, keywords, seriesByKeyword, labels = weekLabels, options = {}) {
  const ctx = document.getElementById(canvasId);
  const valueSuffix = options.valueSuffix || "сообщ. за неделю";
  const yTitle = options.yTitle || "Сообщений за неделю";
  const datasets = keywords.map((k) => ({
    label: k.key,
    data: seriesByKeyword[k.key] || Array(12).fill(0),
    borderColor: k.color,
    backgroundColor: k.color,
    borderWidth: 2,
    pointRadius: 2,
    pointHoverRadius: 4,
    tension: 0.35,
  }));

  // eslint-disable-next-line no-new
  new Chart(ctx, {
    type: "line",
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: {
          labels: { color: "rgba(255,255,255,.78)", boxWidth: 10, boxHeight: 10 },
        },
        tooltip: {
          callbacks: {
            title: (items) => `Неделя от ${items?.[0]?.label ?? ""}`,
            label: (ctx) => {
              const n = ctx.parsed?.y ?? 0;
              const label = ctx.dataset?.label ?? "";
              return `${label}: ${n} ${valueSuffix}`;
            },
          },
        },
      },
      scales: {
        x: {
          ticks: { color: "rgba(255,255,255,.62)" },
          grid: { color: "rgba(255,255,255,.06)" },
        },
        y: {
          beginAtZero: true,
          title: {
            display: true,
            text: yTitle,
            color: "rgba(255,255,255,.62)",
          },
          ticks: { color: "rgba(255,255,255,.62)" },
          grid: { color: "rgba(255,255,255,.06)" },
        },
      },
    },
  });
}

function renderDashboardCharts(data) {
  const labels = data.weekLabels || weekLabels;
  const volumeKeywords = data.keywords || [];
  const volumeSeries = data.seriesByKeyword || {};
  const growthLabels = data.growthLabels || ["Начало", "Середина", "Конец"];
  const growthBaseSeries = data.growthSeriesByKeyword || volumeSeries;
  const growthKeywords = data.growthKeywords || growthSelectionFrom(growthBaseSeries);
  const growthSeries = data.growthSeriesByKeyword || growthSeriesFrom(growthBaseSeries, growthKeywords);

  renderLineChart("mentionsChart", volumeKeywords, volumeSeries, labels);
  renderLineChart("growthChart", growthKeywords, growthSeries, growthLabels, {
    valueSuffix: "% прироста",
    yTitle: "Прирост, %",
  });
}

function renderMeta(meta) {
  const el = document.getElementById("lastUpdated");
  const d = meta?.generatedAt ? new Date(meta.generatedAt) : new Date();
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const yyyy = d.getFullYear();
  const suffix = meta?.note ? ` · ${meta.note}` : "";
  el.textContent = `Обновлено: ${dd}.${mm}.${yyyy}${suffix}`;
}

function formatDocDate(value) {
  if (!value) return "";
  // Expect "YYYY-MM-DD"
  const m = String(value).match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!m) return String(value);
  return `${m[3]}.${m[2]}.${m[1]}`;
}

function escapeHtml(str) {
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

loadData().then((data) => {
  renderMeta(data.meta);
  renderDashboardCharts(data);
  renderTopDocs(data.topDocs);
  renderTopSources(data.topSources);
  renderForecast(data.keywords, data.seriesByKeyword);
});

loadArxivLinks().then(renderArxivLinks);

