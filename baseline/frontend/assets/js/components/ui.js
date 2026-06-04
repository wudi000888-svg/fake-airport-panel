import { esc } from "./layout.js";


export function gb(bytes) {
  const value = Number(bytes || 0) / 1024 / 1024 / 1024;
  return `${value.toFixed(value >= 10 ? 0 : 1)} GB`;
}


export function statusPill(status) {
  const label = {
    completed: "已完成",
    pending: "待处理",
    awaiting_payment: "待付款",
    cancelled: "已取消",
    detected: "已到账",
    confirmed: "已到账",
    ambiguous: "需补 TXID",
    failed: "校验失败",
    expired: "已过期",
  }[status] || status || "未知";
  return `<span class="pill status-${esc(status || "unknown")}">${esc(label)}</span>`;
}


export function stat(label, value, tone = "") {
  return `
    <div class="stat-tile ${esc(tone)}">
      <span>${esc(label)}</span>
      <strong>${esc(value)}</strong>
    </div>
  `;
}


export function empty(message, action = "", label = "") {
  return `
    <article class="mobile-card empty">
      <p>${esc(message)}</p>
      ${action ? `<button class="secondary" data-action="${esc(action)}" type="button">${esc(label || "操作")}</button>` : ""}
    </article>
  `;
}


export function money(value) {
  const number = Number(value || 0);
  return Number.isFinite(number) ? `$${number.toFixed(number % 1 ? 2 : 0)}` : `$${esc(value)}`;
}
