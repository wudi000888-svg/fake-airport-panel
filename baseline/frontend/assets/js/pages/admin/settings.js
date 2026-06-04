import { esc } from "../../components/layout.js";


function methodCard(method) {
  return `
    <article class="admin-card">
      <div>
        <strong>${esc(method.asset || "")} / ${esc(method.chain || "")}</strong>
        <span>${method.enabled ? "启用" : "停用"} · ${esc(method.id || "")}</span>
      </div>
      <p>${esc(method.address || "")}</p>
      <div class="admin-actions">
        <button class="secondary" data-action="payment-method-edit" data-method="${esc(method.id || "")}" type="button">编辑</button>
        <button class="secondary" data-action="payment-method-action" data-method="${esc(method.id || "")}" type="button">切换</button>
      </div>
    </article>
  `;
}


export function renderAdminSettings(data = {}) {
  const methods = data.payment_methods || [];
  return `
    <section class="screen stack">
      <div class="screen-head">
        <div><h1>设置</h1><p>链上收款、缓存和运营参数。</p></div>
        <button class="primary" data-action="payment-method-sheet" type="button">添加收款</button>
      </div>
      <article class="admin-card">
        <div><strong>缓存</strong><span>Dashboard / RPC / 汇率</span></div>
        <button class="secondary" data-action="cache-clear" type="button">清理缓存</button>
      </article>
      <div class="section-row"><h2>链上收款方式</h2><span>${methods.length}</span></div>
      <div class="card-list">${methods.map(methodCard).join("") || `<article class="admin-card empty"><p>暂无收款方式</p><button data-action="payment-method-sheet" type="button">添加收款</button></article>`}</div>
    </section>
  `;
}
