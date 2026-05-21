const state = {
  images: [],
  defaults: {},
  groups: [],
  quickControls: [],
  presets: [],
  saved: {},
  currentImage: null,
  params: {},
  quick: {
    cleanup_strength: 50,
  },
  bg: "checker",
  previewTimer: null,
  previewSerial: 0,
  previewMeta: null,
  zoom: 1,
  brushSize: 18,
  areaTolerance: 36,
  areaGrow: 3,
  paintTool: "white",
  paintMode: false,
  painting: false,
  strokes: [],
  currentStroke: null,
};

const els = {
  imageCount: document.querySelector("#imageCount"),
  imageList: document.querySelector("#imageList"),
  selectedName: document.querySelector("#selectedName"),
  statusText: document.querySelector("#statusText"),
  previewStage: document.querySelector("#previewStage"),
  paintStack: document.querySelector("#paintStack"),
  previewImage: document.querySelector("#previewImage"),
  paintCanvas: document.querySelector("#paintCanvas"),
  brushCursor: document.querySelector("#brushCursor"),
  zoomOut: document.querySelector("#zoomOut"),
  zoomIn: document.querySelector("#zoomIn"),
  zoomFit: document.querySelector("#zoomFit"),
  zoomLabel: document.querySelector("#zoomLabel"),
  originalImage: document.querySelector("#originalImage"),
  outputImage: document.querySelector("#outputImage"),
  presetButtons: document.querySelector("#presetButtons"),
  quickControls: document.querySelector("#quickControls"),
  controlGroups: document.querySelector("#controlGroups"),
  saveImage: document.querySelector("#saveImage"),
  topSaveImage: document.querySelector("#topSaveImage"),
  topGoBack: document.querySelector("#topGoBack"),
  saveParams: document.querySelector("#saveParams"),
  renderCurrent: document.querySelector("#renderCurrent"),
  renderSaved: document.querySelector("#renderSaved"),
  resetDefaults: document.querySelector("#resetDefaults"),
  loadSaved: document.querySelector("#loadSaved"),
  paintToggle: document.querySelector("#paintToggle"),
  eraseToggle: document.querySelector("#eraseToggle"),
  areaDeleteToggle: document.querySelector("#areaDeleteToggle"),
  brushSize: document.querySelector("#brushSize"),
  brushSizeNumber: document.querySelector("#brushSizeNumber"),
  areaTolerance: document.querySelector("#areaTolerance"),
  areaToleranceNumber: document.querySelector("#areaToleranceNumber"),
  areaGrow: document.querySelector("#areaGrow"),
  areaGrowNumber: document.querySelector("#areaGrowNumber"),
  undoPaint: document.querySelector("#undoPaint"),
  clearPaint: document.querySelector("#clearPaint"),
};

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function setStatus(text) {
  els.statusText.textContent = text;
}

function cacheBust(url) {
  return `${url}?t=${Date.now()}`;
}

function paramsForImage(name) {
  return clone(state.saved[name] || state.defaults);
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function roundStep(value, step) {
  const precision = String(step).includes(".") ? String(step).split(".")[1].length : 0;
  return Number((Math.round(value / step) * step).toFixed(precision));
}

function estimateCleanupStrength(params) {
  const raw = ((Number(params.shape_diff_min ?? state.defaults.shape_diff_min) - 6) / 8) * 100;
  return Math.round(clamp(raw, 0, 100));
}

function setCleanupStrength(value) {
  const cleanup = clamp(Number(value), 0, 100);
  const t = cleanup / 100;
  state.quick.cleanup_strength = cleanup;

  state.params.shape_diff_min = roundStep(6 + 8 * t, 1);
  state.params.shape_dark_diff_min = roundStep(18 + 16 * t, 1);
  state.params.shape_gradient_min = roundStep(3 + 5 * t, 0.5);
  state.params.shape_strong_diff = roundStep(48 + 32 * t, 1);
  state.params.adjacent_diff_min = roundStep(5 + 10 * t, 1);
  state.params.adjacent_dark_diff_min = roundStep(12 + 20 * t, 1);
  state.params.adjacent_gradient_min = roundStep(3 + 9 * t, 0.5);
  state.params.neutral_diff_min = roundStep(10 + 14 * t, 1);
  state.params.neutral_gradient_min = roundStep(6 + 10 * t, 0.5);
  state.params.art_diff_min = roundStep(7 + 5 * t, 1);
  state.params.art_strong_diff = roundStep(68 + 18 * t, 1);
  state.params.anchor_strong_diff = roundStep(70 + 15 * t, 1);
}

function setButtonsDisabled(disabled) {
  [
    els.saveImage,
    els.topSaveImage,
    els.topGoBack,
    els.saveParams,
    els.renderCurrent,
    els.renderSaved,
    els.resetDefaults,
    els.loadSaved,
    els.paintToggle,
    els.eraseToggle,
    els.areaDeleteToggle,
    els.undoPaint,
    els.clearPaint,
  ].forEach((button) => {
    button.disabled = disabled;
  });
}

function renderImageList() {
  els.imageList.innerHTML = "";
  els.imageCount.textContent = `${state.images.length} images`;

  state.images.forEach((name) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `image-item ${name === state.currentImage ? "active" : ""}`;
    button.dataset.image = name;

    const img = document.createElement("img");
    img.src = `/original/${name}`;
    img.alt = name;

    const label = document.createElement("div");
    label.className = "image-name";
    if (state.saved[name]) {
      const dot = document.createElement("span");
      dot.className = "saved-dot";
      label.appendChild(dot);
    }
    label.appendChild(document.createTextNode(name));

    button.appendChild(img);
    button.appendChild(label);
    button.addEventListener("click", () => selectImage(name));
    els.imageList.appendChild(button);
  });
}

function quickValue(key) {
  if (key === "cleanup_strength") return state.quick.cleanup_strength;
  return state.params[key];
}

function setQuickValue(key, value) {
  if (key === "cleanup_strength") {
    setCleanupStrength(value);
  } else {
    state.params[key] = Number(value);
  }
}

function renderPresets() {
  els.presetButtons.innerHTML = "";
  state.presets.forEach((preset) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "preset-button";
    button.dataset.preset = preset.id;
    button.innerHTML = `<span>${preset.label}</span><small>${preset.description}</small>`;
    button.addEventListener("click", () => applyPreset(preset.id));
    els.presetButtons.appendChild(button);
  });
}

function renderQuickControls() {
  els.quickControls.innerHTML = "";
  state.quickControls.forEach(([key, label, description, min, max, step]) => {
    const row = document.createElement("div");
    row.className = "quick-row";

    const labelWrap = document.createElement("div");
    labelWrap.className = "quick-label";
    const title = document.createElement("label");
    title.htmlFor = `quick-${key}`;
    title.textContent = label;
    const hint = document.createElement("p");
    hint.textContent = description;
    labelWrap.appendChild(title);
    labelWrap.appendChild(hint);

    const range = document.createElement("input");
    range.id = `quick-${key}`;
    range.type = "range";
    range.min = min;
    range.max = max;
    range.step = step;
    range.value = quickValue(key);

    const number = document.createElement("input");
    number.type = "number";
    number.min = min;
    number.max = max;
    number.step = step;
    number.value = quickValue(key);

    const onInput = (event) => {
      const value = Number(event.target.value);
      setQuickValue(key, value);
      range.value = quickValue(key);
      number.value = quickValue(key);
      renderControls();
      schedulePreview();
    };
    range.addEventListener("input", onInput);
    number.addEventListener("input", onInput);

    row.appendChild(labelWrap);
    row.appendChild(range);
    row.appendChild(number);
    els.quickControls.appendChild(row);
  });
}

function renderControls() {
  els.controlGroups.innerHTML = "";
  const advanced = document.createElement("details");
  advanced.className = "advanced-shell";
  const advancedSummary = document.createElement("summary");
  advancedSummary.textContent = "Advanced Detection Parameters";
  advanced.appendChild(advancedSummary);
  const advancedBody = document.createElement("div");
  advancedBody.className = "advanced-body";

  state.groups.forEach((group) => {
    const details = document.createElement("details");

    const summary = document.createElement("summary");
    summary.textContent = group.title;
    details.appendChild(summary);

    const body = document.createElement("div");
    body.className = "control-group-body";

    group.items.forEach(([key, label, min, max, step]) => {
      const row = document.createElement("div");
      row.className = "control-row";

      const text = document.createElement("label");
      text.htmlFor = `range-${key}`;
      text.textContent = label;

      const range = document.createElement("input");
      range.id = `range-${key}`;
      range.type = "range";
      range.min = min;
      range.max = max;
      range.step = step;
      range.value = state.params[key];
      range.dataset.key = key;

      const number = document.createElement("input");
      number.type = "number";
      number.min = min;
      number.max = max;
      number.step = step;
      number.value = state.params[key];
      number.dataset.key = key;

      const onInput = (event) => {
        const value = Number(event.target.value);
        state.params[key] = value;
        range.value = value;
        number.value = value;
        schedulePreview();
      };
      range.addEventListener("input", onInput);
      number.addEventListener("input", onInput);

      row.appendChild(text);
      row.appendChild(range);
      row.appendChild(number);
      body.appendChild(row);
    });

    details.appendChild(body);
    advancedBody.appendChild(details);
  });
  advanced.appendChild(advancedBody);
  els.controlGroups.appendChild(advanced);
}

function setBackground(kind) {
  state.bg = kind;
  els.previewStage.classList.remove("checker-bg", "dark-bg", "white-bg");
  els.previewStage.classList.add(`${kind}-bg`);
  document.querySelectorAll("[data-bg]").forEach((button) => {
    button.classList.toggle("active", button.dataset.bg === kind);
  });
  redrawPaint();
}

function selectImage(name) {
  state.currentImage = name;
  state.params = paramsForImage(name);
  state.quick.cleanup_strength = estimateCleanupStrength(state.params);
  clearPaint(false);
  els.selectedName.textContent = name;
  els.originalImage.src = `/original/${name}`;
  els.outputImage.src = cacheBust(`/output/${name}`);
  renderImageList();
  renderPresets();
  renderQuickControls();
  renderControls();
  schedulePreview(true);
}

function schedulePreview(immediate = false) {
  clearPaint(false);
  window.clearTimeout(state.previewTimer);
  const delay = immediate ? 0 : 220;
  state.previewTimer = window.setTimeout(loadPreview, delay);
}

async function loadPreview() {
  if (!state.currentImage) return;
  const serial = ++state.previewSerial;
  setStatus("Rendering preview");

  try {
    const response = await fetch("/api/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        image: state.currentImage,
        params: state.params,
        maxSize: 980,
      }),
    });
    if (!response.ok) throw new Error(await response.text());
    const data = await response.json();
    if (serial !== state.previewSerial) return;
    state.previewMeta = {
      cropBox: data.cropBox,
      cropSize: data.cropSize,
      previewSize: data.size,
    };
    els.previewImage.src = data.image;
    setStatus(`Preview ${data.size[0]}x${data.size[1]} in ${data.elapsedMs} ms`);
  } catch (error) {
    setStatus(`Preview failed: ${error.message}`);
  }
}

function syncPaintCanvas() {
  const image = els.previewImage;
  const canvas = els.paintCanvas;
  if (!image.naturalWidth || !image.naturalHeight) return;
  canvas.width = image.naturalWidth;
  canvas.height = image.naturalHeight;
  canvas.style.width = `${image.clientWidth}px`;
  canvas.style.height = `${image.clientHeight}px`;
  updateBrushCursorSize();
  redrawPaint();
}

function fitScale() {
  const image = els.previewImage;
  const stageRect = els.previewStage.getBoundingClientRect();
  if (!image.naturalWidth || !image.naturalHeight || !stageRect.width || !stageRect.height) {
    return 1;
  }
  const maxWidth = Math.max(220, stageRect.width - 36);
  const maxHeight = Math.max(220, stageRect.height - 36);
  return Math.min(maxWidth / image.naturalWidth, maxHeight / image.naturalHeight, 1);
}

function updateZoomLabel() {
  els.zoomLabel.textContent = state.zoom === 1 ? "Fit" : `${Math.round(state.zoom * 100)}%`;
}

function applyZoom() {
  const image = els.previewImage;
  if (!image.naturalWidth || !image.naturalHeight) {
    updateZoomLabel();
    return;
  }
  const scale = fitScale() * state.zoom;
  image.classList.add("zoomed");
  image.style.width = `${Math.max(80, Math.round(image.naturalWidth * scale))}px`;
  image.style.height = "auto";
  updateZoomLabel();
}

function setZoom(nextZoom) {
  state.zoom = clamp(nextZoom, 0.35, 4);
  applyZoom();
  syncPaintCanvas();
}

function zoomIn() {
  setZoom(state.zoom * 1.25);
  setStatus(`Zoom ${Math.round(state.zoom * 100)}%`);
}

function zoomOut() {
  setZoom(state.zoom / 1.25);
  setStatus(`Zoom ${state.zoom === 1 ? "Fit" : `${Math.round(state.zoom * 100)}%`}`);
}

function zoomFit() {
  setZoom(1);
  setStatus("Zoom fit");
}

function brushDisplaySize() {
  const canvas = els.paintCanvas;
  const rect = canvas.getBoundingClientRect();
  if (!canvas.width || !canvas.height || !rect.width || !rect.height) {
    return state.brushSize;
  }
  const scale = (rect.width / canvas.width + rect.height / canvas.height) / 2;
  return Math.max(3, state.brushSize * scale);
}

function updateBrushCursorSize() {
  const size = brushDisplaySize();
  els.brushCursor.style.width = `${size}px`;
  els.brushCursor.style.height = `${size}px`;
}

function moveBrushCursor(event) {
  if (!state.paintMode) return;
  const rect = els.paintStack.getBoundingClientRect();
  els.brushCursor.style.left = `${event.clientX - rect.left}px`;
  els.brushCursor.style.top = `${event.clientY - rect.top}px`;
  els.brushCursor.classList.add("visible");
}

function hideBrushCursor() {
  els.brushCursor.classList.remove("visible");
}

function paintContext() {
  return els.paintCanvas.getContext("2d");
}

function alignedCheckerCanvas(width, height) {
  const tile = 12;
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  const paintRect = els.paintCanvas.getBoundingClientRect();
  const stageRect = els.previewStage.getBoundingClientRect();
  const scaleX = paintRect.width / Math.max(1, width);
  const scaleY = paintRect.height / Math.max(1, height);
  const offsetX = paintRect.left - stageRect.left;
  const offsetY = paintRect.top - stageRect.top;

  ctx.fillStyle = "#fff";
  ctx.fillRect(0, 0, width, height);
  ctx.fillStyle = "#d4d7db";

  const firstCol = Math.floor(offsetX / tile) - 1;
  const lastCol = Math.ceil((offsetX + paintRect.width) / tile) + 1;
  const firstRow = Math.floor(offsetY / tile) - 1;
  const lastRow = Math.ceil((offsetY + paintRect.height) / tile) + 1;

  for (let row = firstRow; row <= lastRow; row += 1) {
    for (let col = firstCol; col <= lastCol; col += 1) {
      if ((row + col) % 2 !== 0) continue;
      const x = (col * tile - offsetX) / scaleX;
      const y = (row * tile - offsetY) / scaleY;
      ctx.fillRect(x, y, tile / scaleX, tile / scaleY);
    }
  }

  return canvas;
}

function eraserPreviewStyle(ctx) {
  if (state.bg === "dark") return "#2b313c";
  if (state.bg === "white") return "#fff";

  return ctx.createPattern(alignedCheckerCanvas(ctx.canvas.width, ctx.canvas.height), "no-repeat") || "#fff";
}

function growAreaMaskCanvas(maskCanvas, grow) {
  const radius = Math.max(0, Math.round(grow));
  if (!radius) return maskCanvas;

  const grown = document.createElement("canvas");
  grown.width = maskCanvas.width;
  grown.height = maskCanvas.height;
  const ctx = grown.getContext("2d");
  for (let dy = -radius; dy <= radius; dy += 1) {
    for (let dx = -radius; dx <= radius; dx += 1) {
      if (dx * dx + dy * dy > radius * radius) continue;
      ctx.drawImage(maskCanvas, dx, dy);
    }
  }
  return grown;
}

function createAreaMaskCanvas(mask, width, height, grow = 0) {
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  const imageData = ctx.createImageData(width, height);
  for (let i = 0; i < mask.length; i += 1) {
    const offset = i * 4;
    imageData.data[offset] = 255;
    imageData.data[offset + 1] = 255;
    imageData.data[offset + 2] = 255;
    imageData.data[offset + 3] = mask[i];
  }
  ctx.putImageData(imageData, 0, 0);
  return growAreaMaskCanvas(canvas, grow);
}

function drawAreaDelete(ctx, action) {
  if (!action.maskCanvas) return;
  const temp = document.createElement("canvas");
  temp.width = action.maskCanvas.width;
  temp.height = action.maskCanvas.height;
  const tempCtx = temp.getContext("2d");
  tempCtx.fillStyle = eraserPreviewStyle(tempCtx);
  tempCtx.fillRect(0, 0, temp.width, temp.height);
  tempCtx.globalCompositeOperation = "destination-in";
  tempCtx.drawImage(action.maskCanvas, 0, 0);
  ctx.drawImage(temp, 0, 0);
}

function redrawPaint() {
  const ctx = paintContext();
  ctx.clearRect(0, 0, els.paintCanvas.width, els.paintCanvas.height);
  state.strokes.forEach((stroke) => drawStroke(ctx, stroke));
}

function drawStroke(ctx, stroke) {
  if (stroke.tool === "area-delete") {
    drawAreaDelete(ctx, stroke);
    return;
  }

  const points = stroke.points;
  if (!points.length) return;
  const tool = stroke.tool || "white";
  const style = tool === "erase" ? eraserPreviewStyle(ctx) : "#fff";
  ctx.save();
  ctx.globalCompositeOperation = "source-over";
  ctx.strokeStyle = style;
  ctx.fillStyle = style;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.lineWidth = stroke.size;
  ctx.beginPath();
  ctx.moveTo(points[0].x, points[0].y);
  points.slice(1).forEach((point) => ctx.lineTo(point.x, point.y));
  ctx.stroke();
  points.forEach((point) => {
    ctx.beginPath();
    ctx.arc(point.x, point.y, stroke.size / 2, 0, Math.PI * 2);
    ctx.fill();
  });
  ctx.restore();
}

function previewImageData() {
  const image = els.previewImage;
  if (!image.naturalWidth || !image.naturalHeight) return null;
  const canvas = document.createElement("canvas");
  canvas.width = image.naturalWidth;
  canvas.height = image.naturalHeight;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
  return ctx.getImageData(0, 0, canvas.width, canvas.height);
}

function floodFillPreviewArea(seed, tolerance) {
  const imageData = previewImageData();
  if (!imageData) return null;

  const width = imageData.width;
  const height = imageData.height;
  const x = Math.round(clamp(seed.x, 0, width - 1));
  const y = Math.round(clamp(seed.y, 0, height - 1));
  const data = imageData.data;
  const startIndex = y * width + x;
  const startOffset = startIndex * 4;
  const target = [
    data[startOffset],
    data[startOffset + 1],
    data[startOffset + 2],
    data[startOffset + 3],
  ];

  if (target[3] < 8) return null;

  const visited = new Uint8Array(width * height);
  const mask = new Uint8ClampedArray(width * height);
  const stack = [startIndex];
  let count = 0;
  let minX = x;
  let maxX = x;
  let minY = y;
  let maxY = y;

  const matches = (index) => {
    const offset = index * 4;
    return (
      data[offset + 3] >= 8 &&
      Math.abs(data[offset] - target[0]) <= tolerance &&
      Math.abs(data[offset + 1] - target[1]) <= tolerance &&
      Math.abs(data[offset + 2] - target[2]) <= tolerance
    );
  };

  while (stack.length) {
    const index = stack.pop();
    if (visited[index]) continue;
    visited[index] = 1;
    if (!matches(index)) continue;

    mask[index] = 255;
    count += 1;
    const px = index % width;
    const py = Math.floor(index / width);
    minX = Math.min(minX, px);
    maxX = Math.max(maxX, px);
    minY = Math.min(minY, py);
    maxY = Math.max(maxY, py);

    if (px > 0) stack.push(index - 1);
    if (px < width - 1) stack.push(index + 1);
    if (py > 0) stack.push(index - width);
    if (py < height - 1) stack.push(index + width);
    if (px > 0 && py > 0) stack.push(index - width - 1);
    if (px < width - 1 && py > 0) stack.push(index - width + 1);
    if (px > 0 && py < height - 1) stack.push(index + width - 1);
    if (px < width - 1 && py < height - 1) stack.push(index + width + 1);
  }

  if (!count) return null;
  return {
    mask,
    width,
    height,
    count,
    bounds: [minX, minY, maxX + 1, maxY + 1],
  };
}

function addAreaDelete(seed) {
  const area = floodFillPreviewArea(seed, state.areaTolerance);
  if (!area) {
    setStatus("No visible area selected");
    return;
  }

  state.strokes.push({
    tool: "area-delete",
    seed,
    tolerance: state.areaTolerance,
    grow: state.areaGrow,
    bounds: area.bounds,
    pixels: area.count,
    maskCanvas: createAreaMaskCanvas(area.mask, area.width, area.height, state.areaGrow),
  });
  redrawPaint();
  setStatus(strokeSummary());
}

function canvasPoint(event) {
  const rect = els.paintCanvas.getBoundingClientRect();
  return {
    x: ((event.clientX - rect.left) / rect.width) * els.paintCanvas.width,
    y: ((event.clientY - rect.top) / rect.height) * els.paintCanvas.height,
  };
}

function startPaint(event) {
  if (!state.paintMode) return;
  event.preventDefault();
  moveBrushCursor(event);
  if (state.paintTool === "area-delete") {
    addAreaDelete(canvasPoint(event));
    return;
  }

  els.paintCanvas.setPointerCapture(event.pointerId);
  state.painting = true;
  state.currentStroke = {
    size: state.brushSize,
    tool: state.paintTool,
    points: [canvasPoint(event)],
  };
  state.strokes.push(state.currentStroke);
  redrawPaint();
}

function movePaint(event) {
  moveBrushCursor(event);
  if (!state.painting || !state.currentStroke) return;
  event.preventDefault();
  state.currentStroke.points.push(canvasPoint(event));
  redrawPaint();
}

function endPaint(event) {
  if (!state.painting) return;
  event.preventDefault();
  state.painting = false;
  state.currentStroke = null;
  setStatus(strokeSummary());
}

function clearPaint(updateStatus = true) {
  state.strokes = [];
  state.currentStroke = null;
  state.painting = false;
  if (els.paintCanvas) {
    redrawPaint();
  }
  if (updateStatus) {
    setStatus("Cleared manual edits");
  }
}

function undoPaint() {
  state.strokes.pop();
  redrawPaint();
  setStatus(strokeSummary());
}

function strokeSummary() {
  if (!state.strokes.length) return "No manual edits";
  const whiteCount = state.strokes.filter((stroke) => (stroke.tool || "white") === "white").length;
  const eraseCount = state.strokes.filter((stroke) => stroke.tool === "erase").length;
  const areaCount = state.strokes.filter((stroke) => stroke.tool === "area-delete").length;
  const parts = [];
  if (whiteCount) parts.push(`${whiteCount} white stroke${whiteCount === 1 ? "" : "s"}`);
  if (eraseCount) parts.push(`${eraseCount} erase stroke${eraseCount === 1 ? "" : "s"}`);
  if (areaCount) parts.push(`${areaCount} area delete${areaCount === 1 ? "" : "s"}`);
  return `${parts.join(", ")} pending`;
}

function setPaintMode(enabled, tool = state.paintTool) {
  state.paintTool = tool;
  state.paintMode = enabled;
  els.paintToggle.classList.toggle("active", enabled && tool === "white");
  els.eraseToggle.classList.toggle("active", enabled && tool === "erase");
  els.areaDeleteToggle.classList.toggle("active", enabled && tool === "area-delete");
  els.paintStack.classList.toggle("painting", enabled);
  els.paintStack.classList.toggle("erasing", enabled && tool === "erase");
  els.paintStack.classList.toggle("area-deleting", enabled && tool === "area-delete");
  updateBrushCursorSize();
  if (!enabled) hideBrushCursor();
  const toolName = tool === "area-delete" ? "Area delete" : tool === "erase" ? "Eraser" : "White brush";
  setStatus(enabled ? `${toolName} enabled` : "Brush disabled");
}

function togglePaintTool(tool) {
  const shouldDisable = state.paintMode && state.paintTool === tool;
  setPaintMode(!shouldDisable, tool);
}

function setBrushSize(value) {
  state.brushSize = clamp(Number(value), 2, 80);
  els.brushSize.value = state.brushSize;
  els.brushSizeNumber.value = state.brushSize;
  updateBrushCursorSize();
}

function setAreaTolerance(value) {
  state.areaTolerance = clamp(Number(value), 4, 96);
  els.areaTolerance.value = state.areaTolerance;
  els.areaToleranceNumber.value = state.areaTolerance;
  if (state.paintMode && state.paintTool === "area-delete") {
    setStatus(`Area delete sensitivity ${state.areaTolerance}`);
  }
}

function setAreaGrow(value) {
  state.areaGrow = clamp(Number(value), 0, 16);
  els.areaGrow.value = state.areaGrow;
  els.areaGrowNumber.value = state.areaGrow;
  if (state.paintMode && state.paintTool === "area-delete") {
    setStatus(`Area grow ${state.areaGrow}px`);
  }
}

async function postJson(url, payload) {
  setButtonsDisabled(true);
  try {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error(await response.text());
    return await response.json();
  } finally {
    setButtonsDisabled(false);
  }
}

function manualActionsForSave() {
  return state.strokes.map((stroke) => {
    if (stroke.tool === "area-delete") {
      return {
        tool: stroke.tool,
        seed: stroke.seed,
        tolerance: stroke.tolerance,
        grow: stroke.grow,
      };
    }
    return {
      tool: stroke.tool || "white",
      size: stroke.size,
      points: stroke.points,
    };
  });
}

async function saveCurrentImage() {
  if (!state.currentImage) return;
  const hasPaint = state.strokes.length > 0;
  setStatus(hasPaint ? "Saving manual edits" : "Saving image");
  const payload = {
    image: state.currentImage,
    params: state.params,
  };
  let data;
  if (hasPaint) {
    data = await postJson("/api/save-painted", {
      ...payload,
      cropBox: state.previewMeta?.cropBox,
      previewSize: state.previewMeta?.previewSize,
      strokes: manualActionsForSave(),
    });
  } else {
    data = await postJson("/api/save", payload);
  }
  state.saved = data.saved;
  els.outputImage.src = cacheBust(`/output/${state.currentImage}`);
  clearPaint(false);
  renderImageList();
  setStatus(`Saved ${state.currentImage}`);
}

async function saveParamsOnly() {
  if (!state.currentImage) return;
  setStatus("Saving params");
  const data = await postJson("/api/save-params", {
    image: state.currentImage,
    params: state.params,
  });
  state.saved = data.saved;
  renderImageList();
  setStatus(`Saved params for ${state.currentImage}`);
}

async function renderAll(mode) {
  setStatus(mode === "saved" ? "Rendering saved set" : "Rendering all current");
  const data = await postJson("/api/render-all", {
    mode,
    params: state.params,
  });
  if (state.currentImage) {
    els.outputImage.src = cacheBust(`/output/${state.currentImage}`);
  }
  setStatus(`Rendered ${data.rendered.length} images`);
}

function resetDefaults() {
  state.params = clone(state.defaults);
  state.quick.cleanup_strength = estimateCleanupStrength(state.params);
  renderQuickControls();
  renderControls();
  schedulePreview(true);
}

function loadSaved() {
  if (!state.currentImage) return;
  state.params = paramsForImage(state.currentImage);
  state.quick.cleanup_strength = estimateCleanupStrength(state.params);
  renderQuickControls();
  renderControls();
  schedulePreview(true);
}

function applyPreset(id) {
  const preset = state.presets.find((item) => item.id === id);
  if (!preset) return;
  Object.assign(state.params, preset.params || {});
  if (typeof preset.cleanupStrength === "number") {
    setCleanupStrength(preset.cleanupStrength);
  } else {
    state.quick.cleanup_strength = estimateCleanupStrength(state.params);
  }
  renderQuickControls();
  renderControls();
  schedulePreview(true);
  setStatus(`Applied ${preset.label}`);
}

async function init() {
  const response = await fetch("/api/state");
  const data = await response.json();
  state.images = data.images;
  state.defaults = data.defaults;
  state.groups = data.groups;
  state.quickControls = data.quickControls;
  state.presets = data.presets;
  state.saved = data.saved || {};

  document.querySelectorAll("[data-bg]").forEach((button) => {
    button.addEventListener("click", () => setBackground(button.dataset.bg));
  });
  els.saveImage.addEventListener("click", saveCurrentImage);
  els.topSaveImage.addEventListener("click", saveCurrentImage);
  els.topGoBack.addEventListener("click", undoPaint);
  els.saveParams.addEventListener("click", saveParamsOnly);
  els.renderCurrent.addEventListener("click", () => renderAll("current"));
  els.renderSaved.addEventListener("click", () => renderAll("saved"));
  els.resetDefaults.addEventListener("click", resetDefaults);
  els.loadSaved.addEventListener("click", loadSaved);
  els.zoomIn.addEventListener("click", zoomIn);
  els.zoomOut.addEventListener("click", zoomOut);
  els.zoomFit.addEventListener("click", zoomFit);
  els.previewImage.addEventListener("load", () => {
    applyZoom();
    syncPaintCanvas();
  });
  window.addEventListener("resize", () => {
    applyZoom();
    syncPaintCanvas();
  });
  els.paintCanvas.addEventListener("pointerdown", startPaint);
  els.paintCanvas.addEventListener("pointermove", movePaint);
  els.paintCanvas.addEventListener("pointerenter", moveBrushCursor);
  els.paintCanvas.addEventListener("pointerleave", hideBrushCursor);
  els.paintCanvas.addEventListener("pointerup", endPaint);
  els.paintCanvas.addEventListener("pointercancel", endPaint);
  els.paintToggle.addEventListener("click", () => togglePaintTool("white"));
  els.eraseToggle.addEventListener("click", () => togglePaintTool("erase"));
  els.areaDeleteToggle.addEventListener("click", () => togglePaintTool("area-delete"));
  els.undoPaint.addEventListener("click", undoPaint);
  els.clearPaint.addEventListener("click", () => clearPaint(true));
  els.brushSize.addEventListener("input", (event) => setBrushSize(event.target.value));
  els.brushSizeNumber.addEventListener("input", (event) => setBrushSize(event.target.value));
  els.areaTolerance.addEventListener("input", (event) => setAreaTolerance(event.target.value));
  els.areaToleranceNumber.addEventListener("input", (event) => setAreaTolerance(event.target.value));
  els.areaGrow.addEventListener("input", (event) => setAreaGrow(event.target.value));
  els.areaGrowNumber.addEventListener("input", (event) => setAreaGrow(event.target.value));
  setBrushSize(state.brushSize);
  setAreaTolerance(state.areaTolerance);
  setAreaGrow(state.areaGrow);

  setBackground("checker");
  if (state.images.length > 0) {
    selectImage(state.images[0]);
  } else {
    setStatus("No PNG files found in original");
  }
}

init().catch((error) => {
  setStatus(`Startup failed: ${error.message}`);
});
