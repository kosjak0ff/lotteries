const tableBody = document.getElementById("table-body");
const countEl = document.getElementById("lottery-count");
const refDateEl = document.getElementById("reference-date");
const searchInput = document.getElementById("search");
const searchHint = document.getElementById("search-hint");
const headerCells = Array.from(document.querySelectorAll("th[data-sort]"));

let data = [];
let sortKey = null;
let sortDir = "asc";
let enriched = {};

const stripAccents = (text) =>
  text
    .normalize("NFD")
    .replace(/\p{Mn}+/gu, "")
    .toLowerCase();

const escapeHtml = (text) =>
  String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");

const safe = (text) => (text ? escapeHtml(text) : "— данных пока нет");

const compare = (a, b) => {
  if (!sortKey) return 0;
  const dir = sortDir === "desc" ? -1 : 1;

  const parseDate = (val) => (val ? new Date(val).getTime() || 0 : 0);

  let va = a[sortKey];
  let vb = b[sortKey];

  if (sortKey === "permit") {
    va = Number(va) || 0;
    vb = Number(vb) || 0;
  } else if (sortKey === "start" || sortKey === "end") {
    va = parseDate(va);
    vb = parseDate(vb);
  } else {
    va = stripAccents(String(va ?? ""));
    vb = stripAccents(String(vb ?? ""));
  }

  if (va < vb) return -1 * dir;
  if (va > vb) return 1 * dir;
  return 0;
};

function renderTable(rows) {
  const sorted = sortKey ? [...rows].sort(compare) : rows;

  if (!sorted.length) {
    tableBody.innerHTML = '<tr><td colspan="10" class="muted">Ничего не найдено по запросу</td></tr>';
    return;
  }

  const html = sorted
    .map((row) => {
      const details = enriched[row.permit] || {};
      const registrationCell = details.registration_url
        ? `<a class="reg-link" href="${escapeHtml(details.registration_url)}" target="_blank" rel="noopener">Ссылка</a>`
        : "—";

      return `
        <tr>
          <td>${escapeHtml(row.permit)}</td>
          <td>${escapeHtml(row.org)}</td>
          <td>${escapeHtml(row.product)}</td>
          <td>${escapeHtml(row.name)}</td>
          <td>${escapeHtml(row.start)}</td>
          <td>${escapeHtml(row.end)}</td>
          <td>${escapeHtml(row.place)}</td>
          <td>${safe(details.requirements)}</td>
          <td>${safe(details.prizes)}</td>
          <td>${registrationCell}</td>
        </tr>
      `;
    })
    .join("");

  tableBody.innerHTML = html;
}

function applySearch() {
  const query = stripAccents(searchInput.value.trim());
  if (!query) {
    renderTable(data);
    searchHint.textContent = "Показываются все записи; фильтрация происходит на клиенте.";
    return;
  }

  const filtered = data.filter((row) => {
    const details = enriched[row.permit] || {};
    const haystack = stripAccents(
      [
        row.permit,
        row.org,
        row.org_reg,
        row.product,
        row.name,
        row.start,
        row.end,
        row.place,
        details.requirements,
        details.prizes,
        details.registration_url,
        details.registration_until,
        details.notes
      ]
        .filter(Boolean)
        .join(" ")
    );
    return haystack.includes(query);
  });

  renderTable(filtered);
  searchHint.textContent = `Показано ${filtered.length} из ${data.length}`;
}

function handleSort(event) {
  const key = event.currentTarget.dataset.sort;
  if (!key) return;

  if (sortKey === key) {
    sortDir = sortDir === "asc" ? "desc" : "asc";
  } else {
    sortKey = key;
    sortDir = "asc";
  }

  headerCells.forEach((th) => {
    th.classList.toggle("sorted", th.dataset.sort === sortKey);
    th.classList.toggle("desc", th.dataset.sort === sortKey && sortDir === "desc");
  });

  applySearch();
}

async function bootstrap() {
  try {
    const response = await fetch("assets/active_lotteries.json");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();

    try {
      const enrichedResponse = await fetch("assets/enriched_info.json");
      if (enrichedResponse.ok) {
        enriched = await enrichedResponse.json();
      }
    } catch {
      enriched = {};
    }

    data = payload.items || [];
    countEl.textContent = payload.count ?? data.length;
    refDateEl.textContent = payload.reference_date || "20.03.2026";

    renderTable(data);

    searchInput.addEventListener("input", applySearch);
    headerCells.forEach((th) => th.addEventListener("click", handleSort));
  } catch (error) {
    tableBody.innerHTML = `<tr><td colspan="10" class="muted">Не удалось загрузить данные (${escapeHtml(error.message)})</td></tr>`;
  }
}

bootstrap();
