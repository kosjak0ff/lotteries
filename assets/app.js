const tableBody = document.getElementById("table-body");
const countEl = document.getElementById("lottery-count");
const refDateEl = document.getElementById("reference-date");
const searchInput = document.getElementById("search");
const searchHint = document.getElementById("search-hint");

let data = [];

const stripAccents = (text) =>
  text
    .normalize("NFD")
    .replace(/\p{Mn}+/gu, "")
    .toLowerCase();

function renderTable(rows) {
  if (!rows.length) {
    tableBody.innerHTML = `<tr><td colspan="7" class="muted">Ничего не найдено по запросу</td></tr>`;
    return;
  }

  const html = rows
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
  } catch (err) {
    console.error(err);
    tableBody.innerHTML = `<tr><td colspan="7" class="muted">Не удалось загрузить данные (${err.message})</td></tr>`;
  }
}

bootstrap();
