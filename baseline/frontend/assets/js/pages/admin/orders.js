import { esc } from "../../components/layout.js";
import { money, statusPill } from "../../components/ui.js";


function orderCard(order) {
  return `
    <article class="admin-card">
      <div>
        <strong>${esc(order.username || "-")}</strong>
        ${statusPill(order.status)}
      </div>
      <p>${esc(order.plan_name || order.plan_id || order.kind || "订单")} · ${money(order.amount)} · ${esc(order.created_at || "")}</p>
      <div class="admin-actions">
        <button class="secondary" data-action="order-open-sheet" data-order="${esc(order.id)}" type="button">处理</button>
        <button class="secondary" data-action="payment-refresh" data-payment="${esc(order.payment_id || "")}" type="button">查账</button>
      </div>
    </article>
  `;
}


export function renderAdminOrders(data = {}) {
  const orders = data.orders || [];
  const active = orders.filter((order) => order.status === "pending");
  const history = orders.filter((order) => order.status !== "pending");
  return `
    <section class="screen stack">
      <div class="screen-head">
        <div><h1>订单运营</h1><p>未付款、取消和已完成分开处理。</p></div>
        <button class="primary" data-action="order-create-sheet" type="button">创建订单</button>
      </div>
      <div class="toolbar"><input placeholder="搜索用户或订单"><button data-action="orders-filter" type="button">筛选</button></div>
      <div class="section-row"><h2>待处理</h2><span>${active.length}</span></div>
      <div class="card-list">${active.map(orderCard).join("") || `<article class="admin-card empty"><p>暂无待处理订单</p><button data-action="orders-refresh" type="button">刷新</button></article>`}</div>
      <div class="section-row"><h2>历史</h2><span>${history.length}</span></div>
      <div class="card-list">${history.slice(0, 40).map(orderCard).join("") || `<article class="admin-card empty"><p>暂无历史订单</p><button data-action="orders-refresh" type="button">刷新</button></article>`}</div>
      <div class="bottom-sheet" hidden></div>
    </section>
  `;
}
