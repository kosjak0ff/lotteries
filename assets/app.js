const tableBody = document.getElementById("table-body");
const countEl = document.getElementById("lottery-count");
const refDateEl = document.getElementById("reference-date");
const searchInput = document.getElementById("search");
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

const getDetails = (row) => enriched[row.permit] || {};

const getEffectiveRegistrationDate = (row, details = getDetails(row)) =>
  details.registration_until || row.end || "";

const parseSortableDate = (value) => {
  if (!value) return null;
  const trimmed = String(value).trim();
  const isoMatch = /^(\d{4})-(\d{2})-(\d{2})$/.exec(trimmed);
  if (isoMatch) {
    const [, year, month, day] = isoMatch;
    return Date.UTC(Number(year), Number(month) - 1, Number(day));
  }

  const parsed = new Date(trimmed).getTime();
  return Number.isFinite(parsed) ? parsed : null;
};

const formatLotteryDate = (value) => formatReferenceDate(value) || "—";

const formatRegistrationDate = (row, details) => {
  return formatLotteryDate(getEffectiveRegistrationDate(row, details));
};

const formatStartDate = (row) => formatLotteryDate(row.start);

const buildRequirementsCell = (row, details) => {
  const parts = [];

  if (details.requirements) {
    parts.push(escapeHtml(details.requirements));
  }

  if (details.eligible_brands) {
    parts.push(`<strong>Подходят бренды:</strong> ${escapeHtml(details.eligible_brands)}`);
  }

  if (row.place) {
    parts.push(`<strong>Где действует:</strong> ${escapeHtml(row.place)}`);
  }

  return parts.length ? parts.join("<br>") : "— данных пока нет";
};

const formatReferenceDate = (value) => {
  if (!value) return "";
  const isoMatch = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value).trim());
  if (!isoMatch) return String(value);
  const [, year, month, day] = isoMatch;
  return `${day}.${month}.${year}`;
};

const compare = (a, b) => {
  if (!sortKey) return 0;
  const dir = sortDir === "desc" ? -1 : 1;

  let va = a[sortKey];
  let vb = b[sortKey];

  if (sortKey === "permit") {
    va = Number(va) || 0;
    vb = Number(vb) || 0;
  } else if (sortKey === "start" || sortKey === "end") {
    const dateA = sortKey === "start"
      ? parseSortableDate(a.start)
      : parseSortableDate(getEffectiveRegistrationDate(a));
    const dateB = sortKey === "start"
      ? parseSortableDate(b.start)
      : parseSortableDate(getEffectiveRegistrationDate(b));

    if (dateA === null && dateB === null) return 0;
    if (dateA === null) return 1;
    if (dateB === null) return -1;

    va = dateA;
    vb = dateB;
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
    tableBody.innerHTML = '<tr><td colspan="9" class="muted">Ничего не найдено по запросу</td></tr>';
    return;
  }

  const html = sorted
    .map((row) => {
      const details = getDetails(row);
      const requirementsCell = buildRequirementsCell(row, details);
      const startDateCell = escapeHtml(formatStartDate(row));
      const registrationDeadlineCell = escapeHtml(formatRegistrationDate(row, details));
      const registrationCell = details.registration_url
        ? `<a class="reg-link" href="${escapeHtml(details.registration_url)}" target="_blank" rel="noopener">Ссылка</a>`
        : "—";

      return `
        <tr>
          <td>${escapeHtml(row.permit)}</td>
          <td>${escapeHtml(row.org)}</td>
          <td>${escapeHtml(row.product)}</td>
          <td>${escapeHtml(row.name)}</td>
          <td>${startDateCell}</td>
          <td>${registrationDeadlineCell}</td>
          <td>${requirementsCell}</td>
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
        details.eligible_brands,
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
    const referenceDate = formatReferenceDate(payload.reference_date) || refDateEl.textContent.trim();
    countEl.textContent = payload.count ?? data.length;
    refDateEl.textContent = referenceDate;
    document.title = referenceDate && referenceDate !== "—"
      ? `Активные лотереи Латвии · ${referenceDate}`
      : "Активные лотереи Латвии";

    renderTable(data);

    searchInput.addEventListener("input", applySearch);
    headerCells.forEach((th) => th.addEventListener("click", handleSort));
  } catch (error) {
    tableBody.innerHTML = `<tr><td colspan="9" class="muted">Не удалось загрузить данные (${escapeHtml(error.message)})</td></tr>`;
  }
}

bootstrap();
