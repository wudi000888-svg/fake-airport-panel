import { api, post } from "./api.js";
import { state, setNotice } from "./state.js";
import { bindPopstate } from "./router.js";
import { esc, layout, bindLayoutEvents } from "./components/layout.js";
import { statusPill, stat } from "./components/ui.js";
import { renderAdminNodes } from "./pages/admin/nodes.js";
import { renderAdminOrders } from "./pages/admin/orders.js";
import { renderAdminOverview } from "./pages/admin/overview.js";
import { renderAdminSettings } from "./pages/admin/settings.js";
import { renderAdminUsers } from "./pages/admin/users.js";
import { renderUserAccount } from "./pages/user/account.js";
import { renderUserDashboard } from "./pages/user/dashboard.js";
import { renderUserLinks } from "./pages/user/links.js";
import { renderUserOrders } from "./pages/user/orders.js";
import { renderUserPlans } from "./pages/user/plans.js";


const app = document.querySelector("#app");


function loginView() {
  return `
    <section class="login-screen">
      <form class="login-card" data-form="login">
        <div>
          <h1>fake-ui</h1>
          <p>单机多出口代理编排系统</p>
        </div>
        <label>账号<input name="username" autocomplete="username" required></label>
        <label>密码<input name="password" type="password" autocomplete="current-password" required></label>
        <button class="primary" type="submit">登录</button>
      </form>
    </section>
  `;
}


function adminDashboardPage() {
  const users = state.data.users || [];
  const orders = state.data.orders || [];
  const nodes = state.data.nodes || [];
  const payments = state.data.payments || [];
  return `
    <section class="screen">
      <div class="screen-head">
        <div>
          <h1>概览</h1>
          <p>运营数据与节点状态</p>
        </div>
        <button class="secondary" data-action="refresh" type="button">刷新</button>
      </div>
      <div class="stat-grid">
        ${stat("用户", users.length)}
        ${stat("订单", orders.length)}
        ${stat("节点", nodes.length)}
        ${stat("链上付款", payments.length)}
      </div>
    </section>
  `;
}


function adminSimplePage(title, itemsKey) {
  const items = state.data[itemsKey] || [];
  return `
    <section class="screen">
      <div class="screen-head"><h1>${esc(title)}</h1><span>${items.length} 条</span></div>
      <div class="card-list">
        ${items.slice(0, 40).map((item) => `
          <article class="list-card">
            <strong>${esc(item.display_name || item.name || item.username || item.id || item.action || "-")}</strong>
            <span>${esc(item.status || item.kind || item.created_at || "")}</span>
          </article>
        `).join("") || `<div class="empty">暂无记录</div>`}
      </div>
    </section>
  `;
}


function page() {
  if (state.shell?.role !== "admin") {
    if (state.route === "plans") return renderUserPlans(state.data);
    if (state.route === "links") return renderUserLinks(state.data);
    if (state.route === "orders") return renderUserOrders(state.data);
    if (state.route === "account") return renderUserAccount(state.data, state.shell);
    return renderUserDashboard(state.data);
  }
  if (state.route === "orders") return renderAdminOrders(state.data);
  if (state.route === "account" || state.route === "settings") return renderAdminSettings(state.data);
  if (state.route === "users") return renderAdminUsers(state.data);
  if (state.route === "nodes") return renderAdminNodes(state.data);
  if (state.route === "plans") return adminSimplePage("套餐", "plans");
  if (state.route === "links") return adminSimplePage("订阅", "links");
  if (state.route === "requests") return adminSimplePage("申请", "registrations");
  if (state.route === "audit") return adminSimplePage("审计", "audit");
  if (state.route === "backups") return adminSimplePage("备份", "backups");
  if (state.route === "hy2") return adminDashboardPage();
  return renderAdminOverview(state.data);
}


export async function refresh() {
  const result = await api("/api/dashboard");
  state.session = result.data.session;
  state.data = result.data || {};
}


export async function render() {
  if (!state.session) {
    app.innerHTML = loginView();
    return;
  }
  app.innerHTML = layout(page());
}


async function boot() {
  try {
    const sessionResult = await api("/api/session");
    state.session = sessionResult.session;
    if (state.session) {
      state.shell = await api("/api/app-shell");
      await refresh();
    }
  } catch (error) {
    setNotice(error.message, "error");
  }
  bindPopstate();
  bindLayoutEvents(app);
  window.addEventListener("fake-ui:navigate", render);
  await render();
}


app.addEventListener("submit", async (event) => {
  const form = event.target.closest("[data-form]");
  if (!form) return;
  event.preventDefault();
  const data = Object.fromEntries(new FormData(form).entries());
  try {
    if (form.dataset.form === "login") {
      const result = await post("/api/login", data);
      state.session = result.session;
      state.shell = await api("/api/app-shell");
      await refresh();
      setNotice("登录成功", "success");
    }
  } catch (error) {
    setNotice(error.message, "error");
  }
  await render();
});


app.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-action]");
  if (!button) return;
  try {
    if (button.dataset.action === "refresh") {
      await refresh();
      setNotice("已刷新", "success");
    }
    if (button.dataset.action === "logout") {
      await post("/api/logout", {});
      state.session = null;
      state.shell = null;
      state.data = {};
      setNotice("已退出", "success");
    }
  } catch (error) {
    setNotice(error.message, "error");
  }
  await render();
});


boot();
