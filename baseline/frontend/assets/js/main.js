import { api } from "./api.js";
import { state, setBootError, setNotice } from "./state.js";
import { bindPopstate } from "./router.js";
import { layout, bindLayoutEvents } from "./components/layout.js";
import { loginView } from "./components/login.js";
import { renderCharts } from "./components/charts.js";
import { renderAppError } from "./components/ui.js";
import { bindAppActions } from "./actions/handlers.js";
import { pageForState } from "./pages/registry.js";


const app = document.querySelector("#app");


export async function refresh() {
  const result = await api("/api/dashboard");
  state.session = result.data.session;
  state.data = result.data || {};
  setBootError(null);
}


export async function loadAuthenticatedApp() {
  state.shell = await api("/api/app-shell");
  state.publicSettings = state.shell.public_settings || state.publicSettings;
  await refresh();
}


export async function render() {
  if (!state.session) {
    app.innerHTML = loginView();
    return;
  }
  if (state.bootError && state.session) {
    app.innerHTML = layout(renderAppError(state.bootError));
    return;
  }
  app.innerHTML = layout(pageForState(state));
  renderCharts(app);
}


async function boot() {
  try {
    if (new URLSearchParams(location.search).get("registered") === "1") {
      setNotice("注册成功，请登录", "success");
      history.replaceState(null, "", "/login");
    }
    const publicSettings = await api("/api/public-settings");
    state.publicSettings = publicSettings.public_settings || {};
    const sessionResult = await api("/api/session");
    state.session = sessionResult.session;
    if (state.session) {
      await loadAuthenticatedApp();
    }
  } catch (error) {
    if (state.session) {
      setBootError(error.message);
    } else {
      setNotice(error.message, "error");
    }
  }
  bindPopstate();
  bindLayoutEvents(app);
  bindAppActions(app, { refresh, render, loadAuthenticatedApp });
  window.addEventListener("fake-ui:navigate", render);
  await render();
}


boot();
