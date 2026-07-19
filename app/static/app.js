let currentPage = 1;
let currentUsers = [];
const selected = new Set();

const usersBody = document.querySelector("#usersBody");
const resultBox = document.querySelector("#resultBox");
const selectedCount = document.querySelector("#selectedCount");
const pageLabel = document.querySelector("#pageLabel");
const selectAll = document.querySelector("#selectAll");
const filterInput = document.querySelector("#filterInput");

function badge(text, kind = "") {
  return `<span class="badge ${kind}">${text}</span>`;
}

function fmt(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString();
}

function updateSelectedCount() {
  selectedCount.textContent = `${selected.size} selected`;
}

function visibleUsers() {
  const query = filterInput.value.trim().toLowerCase();
  if (!query) return currentUsers;
  return currentUsers.filter((user) => [
    user.login,
    user.email,
    user.full_name,
    user.website,
    user.location,
    user.visibility,
  ].some((value) => String(value || "").toLowerCase().includes(query)));
}

function renderUsers() {
  const users = visibleUsers();
  pageLabel.textContent = `Page ${currentPage}`;
  selectAll.checked = users.length > 0 && users.every((user) => selected.has(user.login));

  if (!users.length) {
    usersBody.innerHTML = `<tr><td colspan="8" class="empty">No users on this page.</td></tr>`;
    updateSelectedCount();
    return;
  }

  usersBody.innerHTML = users.map((user) => {
    const status = [
      user.is_admin ? badge("admin", "warn") : "",
      user.restricted ? badge("restricted") : "",
      user.prohibit_login ? badge("login prohibited", "danger") : "",
      user.active === false ? badge("inactive", "danger") : "",
      user.visibility ? badge(user.visibility) : "",
    ].join("");
    return `
      <tr>
        <td><input class="user-check" type="checkbox" data-login="${user.login}" ${selected.has(user.login) ? "checked" : ""}></td>
        <td><strong>${user.login || ""}</strong><br>${user.full_name || ""}</td>
        <td>${user.email || ""}</td>
        <td><div class="badges">${status}</div></td>
        <td>${user.website || ""}</td>
        <td>${user.location || ""}</td>
        <td>${fmt(user.created)}</td>
        <td>${fmt(user.last_login)}</td>
      </tr>`;
  }).join("");

  document.querySelectorAll(".user-check").forEach((box) => {
    box.addEventListener("change", () => {
      if (box.checked) selected.add(box.dataset.login);
      else selected.delete(box.dataset.login);
      updateSelectedCount();
      renderUsers();
    });
  });
  updateSelectedCount();
}

async function loadUsers() {
  usersBody.innerHTML = `<tr><td colspan="8" class="empty">Loading users...</td></tr>`;
  const response = await fetch(`/api/users?page=${currentPage}&limit=50`);
  if (!response.ok) {
    resultBox.textContent = await response.text();
    usersBody.innerHTML = `<tr><td colspan="8" class="empty">Failed to load users.</td></tr>`;
    return;
  }
  const data = await response.json();
  currentUsers = data.users;
  renderUsers();
}

function actionPayload(dryRun) {
  return {
    usernames: [...selected],
    dry_run: dryRun,
    actions: {
      restricted: document.querySelector("#restricted").checked,
      clear_website: document.querySelector("#clearWebsite").checked,
      clear_location: document.querySelector("#clearLocation").checked,
      keep_email_private: document.querySelector("#keepEmailPrivate").checked,
      disable_org_creation: document.querySelector("#disableOrg").checked,
      prohibit_login: document.querySelector("#prohibitLogin").checked,
      zero_repo_limit: document.querySelector("#zeroRepoLimit").checked,
      visibility: document.querySelector("#keepEmailPrivate").checked ? "private" : null,
    },
  };
}

async function runBulk(dryRun) {
  if (!selected.size) {
    resultBox.textContent = "Select at least one user first.";
    return;
  }
  if (!dryRun && !confirm(`Apply selected actions to ${selected.size} user(s)?`)) return;

  resultBox.textContent = dryRun ? "Running dry run..." : "Applying changes...";
  const response = await fetch("/api/users/bulk", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(actionPayload(dryRun)),
  });
  const text = await response.text();
  try {
    resultBox.textContent = JSON.stringify(JSON.parse(text), null, 2);
  } catch {
    resultBox.textContent = text;
  }
  if (!dryRun) await loadUsers();
}

document.querySelector("#prevPage").addEventListener("click", () => {
  if (currentPage > 1) {
    currentPage -= 1;
    loadUsers();
  }
});
document.querySelector("#nextPage").addEventListener("click", () => {
  currentPage += 1;
  loadUsers();
});
document.querySelector("#refreshUsers").addEventListener("click", loadUsers);
document.querySelector("#dryRun").addEventListener("click", () => runBulk(true));
document.querySelector("#applyBulk").addEventListener("click", () => runBulk(false));
filterInput.addEventListener("input", renderUsers);
selectAll.addEventListener("change", () => {
  visibleUsers().forEach((user) => {
    if (selectAll.checked) selected.add(user.login);
    else selected.delete(user.login);
  });
  renderUsers();
});

loadUsers();
