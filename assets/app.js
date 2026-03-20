const tableBody = document.getElementById("table-body");
const countEl = document.getElementById("lottery-count");
const refDateEl = document.getElementById("reference-date");
const searchInput = document.getElementById("search");
const searchHint = document.getElementById("search-hint");
const headerCells = Array.from(document.querySelectorAll("th[data-sort]"));

let data = [];
let sortKey = null;
let sortDir = "asc";

const stripAccents = (text) =>
  text
    .normalize("NFD")
    .replace(/\p{Mn}+/gu, "")
    .toLowerCase();

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
    va = stripAccents(String(va));
    vb = stripAccents(String(vb));
  }

  if (va < vb) return -1 * dir;
  if (va > vb) return 1 * dir;
  return 0;
};

function renderTable(rows) {
  const sorted = sortKey ? [...rows].sort(compare) : rows;

  if (!sorted.length) {
    tableBody.innerHTML = `<tr><td colspan="7" class="muted">Ничего не найдено по запросу</td></tr>`;
    return;
  }

  const html = sorted
    .map(
      (row) => `
        <tr>
          <td>${row.permit}</td>
          <td>${row.org}</td>
          <td>${row.product}</td>
          <td>${row.name}</td>
          <td>${row.start}</td>
          <td>${row.end}</td>
          <td>${row.place}</td>
        </tr>
      `
    )
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
    const hay = stripAccents(`${row.name} ${row.org}`);
    return hay.includes(query);
  });
  renderTable(filtered);
  searchHint.textContent = `Показано ${filtered.length} из ${data.length}`;
}

function handleSort(evt) {
  const key = evt.currentTarget.dataset.sort;
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
    const res = await fetch("assets/active_lotteries.json");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const payload = await res.json();

    data = payload.items || [];
    countEl.textContent = payload.count ?? data.length;
    refDateEl.textContent = payload.reference_date || "20.03.2026";
    renderTable(data);

    searchInput.addEventListener("input", applySearch);
    headerCells.forEach((th) => th.addEventListener("click", handleSort));
  } catch (err) {
    console.error(err);
    tableBody.innerHTML = `<tr><td colspan="7" class="muted">Не удалось загрузить данные (${err.message})</td></tr>`;
  }
}

bootstrap();
