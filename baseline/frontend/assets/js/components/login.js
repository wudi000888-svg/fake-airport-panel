import { state } from "../state.js";


export function loginView() {
  const registrationEnabled = state.publicSettings?.registration_enabled === true;
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
      ${registrationEnabled ? `
      <form class="login-card" data-form="register">
        <div>
          <h1>注册账号</h1>
          <p>注册后可登录购买套餐。</p>
        </div>
        <label>账号<input name="username" autocomplete="username" required></label>
        <label>密码<input name="password" type="password" autocomplete="new-password" minlength="8" required></label>
        <label>邮箱<input name="email" type="email" autocomplete="email"></label>
        <button class="primary" type="submit">注册并登录</button>
      </form>
      ` : ""}
    </section>
  `;
}
