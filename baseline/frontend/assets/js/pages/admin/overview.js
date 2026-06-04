import { esc } from "../../components/layout.js";
import { stat } from "../../components/ui.js";


export function renderAdminOverview(data = {}) {
  const users = data.users || [];
  const orders = data.orders || [];
  const nodes = data.nodes || [];
  const payments = data.payments || [];
  const pending = orders.filter((order) => order.status === "pending").length;
  return `
    <section class="screen stack">
      <div class="screen-head">
        <div><h1>概览</h1><p>面板运营、链上付款和节点出口状态。</p></div>
        <button class="secondary" data-action="refresh" type="button">刷新</button>
      </div>
      <div class="stat-grid">
        ${stat("用户", users.length)}
        ${stat("待处理订单", pending)}
        ${stat("节点", nodes.length)}
        ${stat("链上付款", payments.length)}
      </div>
      <article class="admin-card">
        <div><strong>系统状态</strong><span>Xray / Hysteria2 / Nginx</span></div>
        <p>${esc(data.xray?.xray || "unknown")} · ${esc(data.hy2?.running || "unknown")}</p>
        <button class="secondary" data-action="open-nodes" type="button">查看节点</button>
      </article>
    </section>
  `;
}
