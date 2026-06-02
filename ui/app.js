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

const now = new Date();
const startWeek = isoWeekStart(new Date(now.getTime() - 11 * 7 * 24 * 3600 * 1000));
const weekLabels = Array.from({ length: 12 }, (_, i) => {
  const d = new Date(startWeek.getTime() + i * 7 * 24 * 3600 * 1000);
  return formatWeekLabel(d);
});

// Demo data (fallback). Primary path is loading `ui/data.json`.
const fallbackData = {
  meta: { generatedAt: null, windowWeeks: 12, note: "Demo fallback data." },
  keywords: [
    { key: "prompt injection", color: "#22d3ee" },
    { key: "mcp", color: "#a855f7" },
    { key: "ai agent", color: "#60a5fa" },
    { key: "self-evolving agent", color: "#f59e0b" },
    { key: "secure rag", color: "#34d399" },
  ],
  seriesByKeyword: {
    "prompt injection": [22, 19, 25, 21, 28, 24, 31, 27, 33, 29, 35, 32],
    mcp: [5, 8, 6, 11, 9, 14, 12, 16, 13, 18, 15, 20],
    "ai agent": [14, 12, 16, 13, 18, 15, 21, 19, 23, 20, 26, 24],
    "self-evolving agent": [3, 2, 4, 3, 5, 4, 6, 5, 7, 6, 8, 7],
    "secure rag": [9, 8, 10, 9, 11, 10, 12, 11, 13, 12, 14, 13]
  },
  topDocs: [],
  topSources: []
};

async function loadData() {
  try {
    const res = await fetch("./data.json", { cache: "no-store" });
    if (!res.ok) return fallbackData;
    const json = await res.json();
    return { ...fallbackData, ...json };
  } catch {
    return fallbackData;
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
    li.innerHTML = `
      <div class="sourceRow">
        <div class="sourceName">${escapeHtml(s.name)}</div>
        <div class="sourceCount">${s.count} новостей</div>
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

function renderChart(keywords, seriesByKeyword) {
  const ctx = document.getElementById("mentionsChart");
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
    data: { labels: weekLabels, datasets },
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
              return `${label}: ${n} сообщ. за неделю`;
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
            text: "Сообщений за неделю",
            color: "rgba(255,255,255,.62)",
          },
          ticks: { color: "rgba(255,255,255,.62)" },
          grid: { color: "rgba(255,255,255,.06)" },
        },
      },
    },
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
  renderChart(data.keywords, data.seriesByKeyword);
  renderTopDocs(data.topDocs);
  renderTopSources(data.topSources);
  renderForecast(data.keywords, data.seriesByKeyword);
});

