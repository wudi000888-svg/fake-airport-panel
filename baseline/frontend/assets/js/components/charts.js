function parseDataset(node, fallback) {
  try {
    return JSON.parse(node.dataset.chart || fallback);
  } catch {
    return JSON.parse(fallback);
  }
}


function setupCanvas(canvas) {
  const rect = canvas.getBoundingClientRect();
  const scale = window.devicePixelRatio || 1;
  const width = Math.max(320, Math.floor(rect.width || canvas.clientWidth || 320));
  const height = Math.max(180, Math.floor(rect.height || canvas.clientHeight || 220));
  canvas.width = width * scale;
  canvas.height = height * scale;
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    canvas.replaceWith(chartFallback(canvas, "图表暂不可用"));
    return null;
  }
  ctx.setTransform(scale, 0, 0, scale, 0, 0);
  return { ctx, width, height };
}


function chartFallback(canvas, message) {
  const fallback = document.createElement("div");
  fallback.className = "chart-fallback";
  fallback.setAttribute("role", "img");
  fallback.setAttribute("aria-label", canvas.getAttribute("aria-label") || "图表");
  fallback.textContent = message;
  return fallback;
}


function formatBytes(value) {
  const gb = Number(value || 0) / 1024 / 1024 / 1024;
  if (gb >= 1) return `${gb.toFixed(gb >= 10 ? 0 : 1)}G`;
  const mb = Number(value || 0) / 1024 / 1024;
  return `${mb.toFixed(mb >= 10 ? 0 : 1)}M`;
}


export function renderLineChart(canvas) {
  const data = parseDataset(canvas, "[]");
  const setup = setupCanvas(canvas);
  if (!setup) return;
  const { ctx, width, height } = setup;
  const pad = { top: 18, right: 20, bottom: 42, left: 58 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  const max = Math.max(1, ...data.map((item) => Number(item.total_bytes || 0)));
  ctx.clearRect(0, 0, width, height);
  ctx.strokeStyle = "#e5edf5";
  ctx.lineWidth = 1;
  ctx.fillStyle = "#667085";
  ctx.font = "12px system-ui";
  for (let i = 0; i <= 4; i += 1) {
    const y = pad.top + (plotH / 4) * i;
    ctx.beginPath();
    ctx.moveTo(pad.left, y);
    ctx.lineTo(width - pad.right, y);
    ctx.stroke();
    ctx.fillText(formatBytes(max - (max / 4) * i), 10, y + 4);
  }
  if (!data.length) {
    ctx.fillText("暂无流量样本", pad.left, pad.top + 24);
    return;
  }
  const xFor = (idx) => pad.left + (data.length === 1 ? plotW / 2 : (plotW / (data.length - 1)) * idx);
  const yFor = (value) => pad.top + plotH - (Number(value || 0) / max) * plotH;
  const drawSeries = (key, color) => {
    ctx.strokeStyle = color;
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    data.forEach((item, idx) => {
      const x = xFor(idx);
      const y = yFor(item[key]);
      if (idx === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();
    ctx.fillStyle = color;
    data.forEach((item, idx) => {
      const x = xFor(idx);
      const y = yFor(item[key]);
      ctx.beginPath();
      ctx.arc(x, y, 3, 0, Math.PI * 2);
      ctx.fill();
    });
  };
  drawSeries("total_bytes", "#2563eb");
  drawSeries("downlink_bytes", "#14b8a6");
  drawSeries("uplink_bytes", "#f59e0b");
  ctx.fillStyle = "#667085";
  const step = Math.max(1, Math.ceil(data.length / 6));
  data.forEach((item, idx) => {
    if (idx % step !== 0 && idx !== data.length - 1) return;
    const label = String(item.bucket || "").slice(5, 16).replace("T", " ");
    ctx.save();
    ctx.translate(xFor(idx), height - 8);
    ctx.rotate(-0.45);
    ctx.fillText(label, 0, 0);
    ctx.restore();
  });
}


export function renderDonutChart(canvas) {
  const data = parseDataset(canvas, "[]");
  const setup = setupCanvas(canvas);
  if (!setup) return;
  const { ctx, width, height } = setup;
  const cx = width / 2;
  const cy = height / 2;
  const radius = Math.min(width, height) * 0.34;
  const total = data.reduce((sum, item) => sum + Number(item.value || item.users || item.total_bytes || 0), 0);
  const colors = ["#2563eb", "#14b8a6", "#f59e0b", "#8b5cf6", "#ef4444", "#64748b"];
  ctx.clearRect(0, 0, width, height);
  if (!total) {
    ctx.fillStyle = "#667085";
    ctx.font = "13px system-ui";
    ctx.fillText("暂无分布数据", cx - 42, cy);
    return;
  }
  let start = -Math.PI / 2;
  data.forEach((item, idx) => {
    const value = Number(item.value || item.users || item.total_bytes || 0);
    const end = start + (value / total) * Math.PI * 2;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.arc(cx, cy, radius, start, end);
    ctx.closePath();
    ctx.fillStyle = colors[idx % colors.length];
    ctx.fill();
    start = end;
  });
  ctx.globalCompositeOperation = "destination-out";
  ctx.beginPath();
  ctx.arc(cx, cy, radius * 0.58, 0, Math.PI * 2);
  ctx.fill();
  ctx.globalCompositeOperation = "source-over";
  ctx.fillStyle = "#101828";
  ctx.font = "700 20px system-ui";
  ctx.textAlign = "center";
  ctx.fillText(String(total), cx, cy + 7);
  ctx.textAlign = "start";
}


export function renderCharts(root = document) {
  root.querySelectorAll("canvas[data-chart-type='line']").forEach((canvas) => {
    try {
      renderLineChart(canvas);
    } catch {
      canvas.replaceWith(chartFallback(canvas, "流量图表加载失败"));
    }
  });
  root.querySelectorAll("canvas[data-chart-type='donut']").forEach((canvas) => {
    try {
      renderDonutChart(canvas);
    } catch {
      canvas.replaceWith(chartFallback(canvas, "分布图表加载失败"));
    }
  });
}
