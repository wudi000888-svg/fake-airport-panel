import { esc } from "../../components/layout.js";


function nodeCard(node) {
  return `
    <article class="admin-card node-admin-card">
      <div>
        <strong>${esc(node.display_name || node.name || node.id)}</strong>
        <span>${esc(node.kind || "")} · ${esc(node.outbound_mode || "direct")} · ${esc(node.status || "online")}</span>
      </div>
      <p>${esc(node.exit_ip || node.address || "")} ${node.country_code ? `· ${esc(node.country_code)}` : ""}</p>
      <div class="admin-actions">
        <button class="secondary" data-action="node-edit" data-node="${esc(node.id)}" type="button">编辑</button>
        <button class="secondary" data-action="node-quality-check" data-node="${esc(node.id)}" type="button">exit quality</button>
      </div>
    </article>
  `;
}


export function renderAdminNodes(data = {}) {
  const nodes = data.nodes || [];
  return `
    <section class="screen stack">
      <div class="screen-head">
        <div><h1>节点</h1><p>VLESS、Hysteria2 与出口质量检测。</p></div>
        <button class="primary" data-action="node-add" type="button">新增节点</button>
      </div>
      <div class="toolbar"><input placeholder="搜索节点、地区或出口 IP"><button data-action="nodes-filter" type="button">筛选</button></div>
      <div class="card-list">${nodes.map(nodeCard).join("") || `<article class="admin-card empty"><p>暂无节点</p><button data-action="node-add" type="button">新增节点</button></article>`}</div>
    </section>
  `;
}
