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

// Demo data (replace later with pipeline output)
const keywords = [
  { key: "prompt injection", color: "#22d3ee" },
  { key: "mcp", color: "#a855f7" },
  { key: "ai agent", color: "#60a5fa" },
  { key: "self-evolving agent", color: "#f59e0b" },
  { key: "secure rag", color: "#34d399" },
];

const now = new Date();
const startWeek = isoWeekStart(new Date(now.getTime() - 11 * 7 * 24 * 3600 * 1000));
const weekLabels = Array.from({ length: 12 }, (_, i) => {
  const d = new Date(startWeek.getTime() + i * 7 * 24 * 3600 * 1000);
  return formatWeekLabel(d);
});

// Build plausible 12-week series (deterministic-ish)
const seriesByKeyword = {
  "prompt injection": [18, 19, 21, 24, 26, 29, 31, 33, 34, 36, 37, 39],
  "mcp":             [6,  7,  9,  10, 11, 12, 15, 16, 18, 20, 22, 24],
  "ai agent":        [10, 11, 12, 13, 15, 18, 20, 22, 23, 25, 28, 30],
  "self-evolving agent": [2, 2, 3, 3, 4, 5, 6, 6, 7, 8, 9, 10],
  "secure rag":      [7,  7,  8,  9,  10, 11, 11, 12, 13, 14, 14, 15],
};

const topDocs = [
  {
    title: "OWASP Top 10 for Large Language Model Applications (latest edition)",
    publisher: "OWASP",
    why: "Дефакто-список рисков и контрольных мер для LLM-приложений.",
    url: "https://owasp.org/www-project-top-ten-for-large-language-model-applications/",
  },
  {
    title: "Secure AI / GenAI guidance (security posture & controls)",
    publisher: "Google",
    why: "Практики по безопасному использованию GenAI и управлению рисками.",
    url: "https://cloud.google.com/security",
  },
  {
    title: "AI Risk Management Framework (AI RMF) and related AI guidance",
    publisher: "NIST",
    why: "Рамка управления рисками, полезна для комплаенса и внутренней политики.",
    url: "https://www.nist.gov/itl/ai-risk-management-framework",
  },
  {
    title: "Security Research / AI-adjacent advisories and writeups",
    publisher: "GitHub Security Lab",
    why: "Посты и исследования, которые часто отражают практические тренды экосистемы.",
    url: "https://securitylab.github.com/",
  },
  {
    title: "Industry outlook on AI/LLM security (quarterly-style overview)",
    publisher: "Gartner (example placeholder)",
    why: "Высокоуровневые тренды рынка; заменить на конкретный публичный документ при подключении источников.",
    url: "https://www.gartner.com/en",
  },
];

const topSources = [
  { name: "OpenAI", count: 42 },
  { name: "Hacker News", count: 37 },
  { name: "OWASP", count: 24 },
  { name: "NIST", count: 18 },
  { name: "GitHub Security Lab", count: 15 },
];

function renderTopDocs() {
  const el = document.getElementById("topDocs");
  el.innerHTML = "";
  topDocs.forEach((d) => {
    const li = document.createElement("li");
    li.innerHTML = `
      <div class="docTitle">${escapeHtml(d.title)}</div>
      <div class="docMeta">
        <span>${escapeHtml(d.publisher)}</span>
        <span> · </span>
        <a class="docLink" href="${d.url}" target="_blank" rel="noreferrer">Открыть</a>
      </div>
      <div class="docMeta">${escapeHtml(d.why)}</div>
    `;
    el.appendChild(li);
  });
}

function renderTopSources() {
  const el = document.getElementById("topSources");
  el.innerHTML = "";
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

function renderForecast() {
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

function renderChart() {
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
          ticks: { color: "rgba(255,255,255,.62)" },
          grid: { color: "rgba(255,255,255,.06)" },
        },
      },
    },
  });
}

function renderMeta() {
  const el = document.getElementById("lastUpdated");
  const d = new Date();
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const yyyy = d.getFullYear();
  el.textContent = `Обновлено: ${dd}.${mm}.${yyyy} (demo)`;
}

function escapeHtml(str) {
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

renderMeta();
renderChart();
renderTopDocs();
renderTopSources();
renderForecast();

