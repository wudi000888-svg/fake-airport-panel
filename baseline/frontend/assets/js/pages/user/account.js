import { esc } from "../../components/layout.js";
import { gb } from "../../components/ui.js";


export function renderUserAccount(data = {}, shell = {}) {
  const profile = data.profile || {};
  return `
    <section class="screen stack">
      <div class="screen-head"><h1>账号</h1></div>
      <article class="mobile-card">
        <div>
          <strong>${esc(profile.username || shell.username || "")}</strong>
          <span>${esc(profile.status || "状态未知")}</span>
        </div>
        <button class="secondary" data-action="logout" type="button">退出</button>
      </article>
      <div class="detail-list">
        <div><span>当前套餐</span><strong>${esc(profile.plan_name || "-")}</strong></div>
        <div><span>到期时间</span><strong>${esc(profile.expires_at || "-")}</strong></div>
        <div><span>已用流量</span><strong>${gb(profile.used_bytes)}</strong></div>
        <div><span>剩余流量</span><strong>${gb(profile.remain_bytes)}</strong></div>
      </div>
      <article class="mobile-card">
        <div><strong>安全建议</strong><span>定期更换面板密码，订阅链接泄露后请联系管理员重置。</span></div>
        <button class="secondary" data-action="refresh" type="button">刷新账号</button>
      </article>
    </section>
  `;
}
