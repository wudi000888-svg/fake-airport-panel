import { esc } from "../../components/layout.js";
import { empty, money } from "../../components/ui.js";


function planCard(plan, currentPlanId) {
  const current = plan.id === currentPlanId;
  return `
    <article class="mobile-card plan-mobile-card ${current ? "current" : ""}">
      <div>
        <strong>${esc(plan.name || plan.id)}</strong>
        <span>${esc(plan.days)} 天 · ${esc(plan.traffic_gb)} GB · ${esc((plan.node_groups || []).join(",") || "default")}</span>
      </div>
      <div class="plan-price">${money(plan.price)}</div>
      <button class="primary" data-action="buy-plan" data-plan="${esc(plan.id)}" type="button">
        ${current ? "续费当前套餐" : "购买套餐"}
      </button>
    </article>
  `;
}


export function renderUserPlans(data = {}) {
  const plans = (data.plans || []).filter((plan) => plan.enabled !== false);
  const profile = data.profile || {};
  return `
    <section class="screen stack">
      <div class="screen-head">
        <div>
          <h1>套餐</h1>
          <p>美元计价，链上到账后自动开通或续费。</p>
        </div>
      </div>
      <article class="mobile-card">
        <div>
          <strong>当前套餐</strong>
          <span>${esc(profile.plan_name || "未开通")}</span>
        </div>
        <button class="secondary" data-action="refresh" type="button">刷新状态</button>
      </article>
      <div class="card-grid">
        ${plans.map((plan) => planCard(plan, profile.plan_id)).join("") || empty("暂无可购买套餐", "refresh", "刷新")}
      </div>
    </section>
  `;
}
