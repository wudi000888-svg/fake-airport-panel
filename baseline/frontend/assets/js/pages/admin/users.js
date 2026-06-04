import { esc } from "../../components/layout.js";


function userCard(user) {
  return `
    <article class="admin-card">
      <div>
        <strong>${esc(user.username)}</strong>
        <span>${esc(user.status || "")} · ${esc(user.quota_status || "")}</span>
      </div>
      <p>${esc(user.plan_name || user.plan_id || "自定义套餐")} · ${esc(user.metrics?.days_left ?? "-")} 天</p>
      <div class="admin-actions">
        <button class="secondary" data-action="user-edit" data-user="${esc(user.username)}" type="button">编辑</button>
        <button class="secondary" data-action="copy-subscription" data-text="${esc(user.raw_subscription_url || user.subscription_url || "")}" type="button">复制订阅</button>
      </div>
    </article>
  `;
}


export function renderAdminUsers(data = {}) {
  const users = data.users || [];
  return `
    <section class="screen stack">
      <div class="screen-head">
        <div><h1>用户</h1><p>创建、续费、订阅与节点授权。</p></div>
        <button class="primary" data-action="user-create-sheet" type="button">新建</button>
      </div>
      <div class="toolbar"><input placeholder="搜索用户"><button data-action="users-filter" type="button">筛选</button></div>
      <div class="card-list">${users.map(userCard).join("") || `<article class="admin-card empty"><p>暂无用户</p><button data-action="user-create-sheet" type="button">创建用户</button></article>`}</div>
    </section>
  `;
}
