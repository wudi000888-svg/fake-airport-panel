import { state } from "../state.js";
import { navigate } from "../router.js";


export function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}


function navButton(item) {
  const active = state.route === item.id ? " active" : "";
  return `
    <button class="nav-item${active}" data-nav="${esc(item.id)}" type="button">
      <span class="nav-dot" aria-hidden="true"></span>
      <span>${esc(item.label)}</span>
    </button>
  `;
}


function notice() {
  if (!state.notice) return "";
  return `<div class="notice ${esc(state.notice.type)}">${esc(state.notice.message)}</div>`;
}


export function layout(content) {
  const nav = (state.shell?.nav || []).map(navButton).join("");
  const secondary = (state.shell?.secondary_nav || []).map(navButton).join("");
  const username = state.shell?.username || state.session?.username || "";
  const role = state.shell?.role === "admin" ? "管理员" : "用户";
  return `
    <div class="app-shell-v2">
      <aside class="side-nav" aria-label="主导航">
        <div class="brand-block">
          <strong>fake-ui</strong>
          <span>单机多出口代理编排系统</span>
        </div>
        <div class="nav-stack">${nav}</div>
        ${secondary ? `<div class="nav-stack secondary">${secondary}</div>` : ""}
      </aside>
      <div class="workspace-v2">
        <header class="topbar">
          <div>
            <strong>fake-ui</strong>
            <span>单机多出口代理编排系统</span>
          </div>
          <div class="identity-chip">${esc(username || role)}</div>
        </header>
        <main class="main-v2">${notice()}${content}</main>
      </div>
      <nav class="bottom-nav" aria-label="移动端导航">${nav}</nav>
    </div>
  `;
}


export function bindLayoutEvents(root) {
  root.addEventListener("click", (event) => {
    const button = event.target.closest("[data-nav]");
    if (!button) return;
    navigate(button.dataset.nav);
  });
}
