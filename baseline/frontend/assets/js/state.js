function routeFromLocation() {
  const route = location.pathname.replace(/^\/+/, "").split("/")[0];
  return route || "dashboard";
}

export const state = {
  session: null,
  shell: null,
  route: routeFromLocation(),
  data: {},
  busy: false,
  notice: null,
};

export function setRouteFromLocation() {
  state.route = routeFromLocation();
}

export function setNotice(message, type = "info") {
  state.notice = message ? { message, type } : null;
}

export function clearNotice() {
  state.notice = null;
}
