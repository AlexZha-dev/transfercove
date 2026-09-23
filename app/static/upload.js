const availableLocales = window.UPLOAD_LOCALES || {};
const requestedLanguage = String(
  window.APP_LANGUAGE || document.documentElement.dataset.language || "en",
).toLowerCase().split("-")[0];
const activeLanguage = availableLocales[requestedLanguage] ? requestedLanguage : "en";
const messages = availableLocales[activeLanguage] || {};

const form = document.querySelector("#upload-form");
const input = document.querySelector("#file-input");
const dropZone = document.querySelector("#drop-zone");
const fileList = document.querySelector("#file-list");
const fileCount = document.querySelector("#file-count");
const cancelButton = document.querySelector("#cancel-button");
const stopButton = document.querySelector("#stop-button");
const submitButton = document.querySelector("#submit-button");
const buttonLabel = document.querySelector(".button-label");
const uploadStatus = document.querySelector("#status");
const overallProgress = document.querySelector("#overall-progress");
const overallPercent = document.querySelector("#overall-percent");
const speedValue = document.querySelector("#speed-value");
const overallStatus = document.querySelector("#overall-status");

const state = {
  files: [],
  isUploading: false,
  startedAt: 0,
  currentXhr: null,
  stopRequested: false,
  cancelRequested: false,
};

function getMessage(key) {
  return key.split(".").reduce((value, part) => value?.[part], messages);
}

function t(key, values = {}) {
  const message = getMessage(key);
  if (typeof message !== "string") return key;

  return message.replace(/\{\{(\w+)\}\}/g, (_, name) => values[name] ?? "");
}

function applyTranslations() {
  document.documentElement.lang = activeLanguage;
  document.title = t("pageTitle");

  document.querySelectorAll("[data-i18n]").forEach((element) => {
    element.textContent = t(element.dataset.i18n);
  });

  document.querySelectorAll("[data-i18n-aria-label]").forEach((element) => {
    element.setAttribute("aria-label", t(element.dataset.i18nAriaLabel));
  });
}

function formatBytes(bytes) {
  if (bytes === 0) return "0 B";

  const units = ["B", "KB", "MB", "GB", "TB"];
  const unitIndex = Math.floor(Math.log(bytes) / Math.log(1024));
  const value = bytes / 1024 ** unitIndex;
  const digits = unitIndex === 0 ? 0 : value < 10 ? 2 : 1;

  return `${value.toFixed(digits)} ${units[unitIndex]}`;
}

function formatSpeed(bytesPerSecond) {
  if (!bytesPerSecond || bytesPerSecond < 1) return "—";
  return `${formatBytes(bytesPerSecond)}/s`;
}

function setStatus(message, tone = "neutral") {
  uploadStatus.textContent = message;
  uploadStatus.className = `status-message status-${tone}`;
}

function updateControls() {
  const hasFiles = state.files.length > 0;
  const hasPendingFiles = state.files.some((item) => item.status !== "done");

  submitButton.disabled = !hasFiles || !hasPendingFiles || state.isUploading;
  cancelButton.disabled = !hasFiles;
  stopButton.hidden = !state.isUploading;
  stopButton.disabled = !state.isUploading;
  input.disabled = state.isUploading;
  buttonLabel.textContent = state.isUploading ? t("uploadingButton") : t("startUpload");
}

function updateFileCount() {
  if (state.files.length === 0) {
    fileCount.textContent = t("noFiles");
    return;
  }

  const totalSize = state.files.reduce((sum, item) => sum + item.file.size, 0);
  const key = state.files.length === 1 ? "fileCount.one" : "fileCount.other";
  fileCount.textContent = t(key, {
    count: state.files.length,
    size: formatBytes(totalSize),
  });
}

function getFileStatus(item) {
  if (item.status === "uploading") {
    return `${t("uploading")} · ${formatSpeed(item.speed)}`;
  }
  if (item.status === "done") return t("done");
  if (item.status === "error") return item.error || t("error");
  if (item.status === "stopped") return t("stopped");
  return t("queued");
}

function renderFileList() {
  fileList.replaceChildren();
  updateFileCount();

  state.files.forEach((item, index) => {
    const row = document.createElement("article");
    row.className = "file-row";
    row.id = `file-row-${index}`;
    row.innerHTML = `
      <div class="file-type-icon" aria-hidden="true">↗</div>
      <div class="file-details">
        <div class="file-heading">
          <span class="file-name"></span>
          <span class="file-percent">0%</span>
        </div>
        <div class="file-meta">
          <span class="file-size"></span>
          <span class="file-status"></span>
        </div>
        <div class="progress-track">
          <div class="file-progress-fill"></div>
        </div>
      </div>
    `;

    row.querySelector(".file-name").textContent = item.file.name;
    row.querySelector(".file-size").textContent = formatBytes(item.file.size);
    fileList.appendChild(row);
    updateFileRow(index);
  });

  fileList.hidden = state.files.length === 0;
  updateControls();
}

function updateFileRow(index) {
  const item = state.files[index];
  const row = document.querySelector(`#file-row-${index}`);

  if (!item || !row) return;

  const percent = Math.round(item.progress);
  const progress = row.querySelector(".file-progress-fill");
  const percentLabel = row.querySelector(".file-percent");
  const statusLabel = row.querySelector(".file-status");

  row.classList.toggle("is-active", item.status === "uploading");
  row.classList.toggle("is-done", item.status === "done");
  row.classList.toggle("is-error", item.status === "error");
  row.classList.toggle("is-stopped", item.status === "stopped");
  progress.style.width = `${percent}%`;
  percentLabel.textContent = `${percent}%`;
  statusLabel.textContent = getFileStatus(item);
}

function updateOverallProgress() {
  const totalBytes = state.files.reduce((sum, item) => sum + item.file.size, 0);
  const uploadedBytes = state.files.reduce((sum, item) => sum + item.uploaded, 0);
  const percent = totalBytes === 0 ? 0 : Math.min(100, (uploadedBytes / totalBytes) * 100);
  const completed = state.files.filter((item) => item.status === "done").length;
  const failed = state.files.filter((item) => item.status === "error").length;
  const activeIndex = state.files.findIndex((item) => item.status === "uploading");

  overallProgress.style.width = `${percent}%`;
  overallPercent.textContent = `${Math.round(percent)}%`;

  if (state.startedAt && uploadedBytes > 0) {
    const seconds = Math.max((performance.now() - state.startedAt) / 1000, 0.001);
    speedValue.textContent = formatSpeed(uploadedBytes / seconds);
  } else {
    speedValue.textContent = "—";
  }

  if (state.isUploading && activeIndex >= 0) {
    overallStatus.textContent = t("fileProgress", {
      current: activeIndex + 1,
      total: state.files.length,
    });
  } else if (state.stopRequested) {
    overallStatus.textContent = t("stopped");
  } else if (failed > 0) {
    overallStatus.textContent = t("errors", { count: failed });
  } else if (completed === state.files.length && completed > 0) {
    overallStatus.textContent = t("completed");
  } else {
    overallStatus.textContent = t("waiting");
  }
}

function selectFiles(fileListValue) {
  if (state.isUploading) return;

  state.files = Array.from(fileListValue).map((file) => ({
    file,
    status: "queued",
    progress: 0,
    uploaded: 0,
    speed: 0,
    error: "",
  }));

  state.startedAt = 0;
  state.stopRequested = false;
  state.cancelRequested = false;
  renderFileList();
  updateOverallProgress();

  if (state.files.length > 0) {
    setStatus(t("ready"), "ready");
  }
}

function uploadFile(item, index) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const startedAt = performance.now();
    const formData = new FormData();
    let settled = false;

    const rejectUpload = (message, code = "error") => {
      if (settled) return;
      settled = true;
      state.currentXhr = null;
      item.status = code === "stopped" ? "stopped" : code === "canceled" ? "canceled" : "error";
      item.error = message;
      updateFileRow(index);
      updateOverallProgress();
      reject(Object.assign(new Error(message), { code }));
    };

    item.status = "uploading";
    updateFileRow(index);
    state.currentXhr = xhr;
    xhr.open("POST", "/v1/files");

    xhr.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable) {
        item.uploaded = event.loaded;
        item.progress = (event.loaded / event.total) * 100;
      }

      const seconds = Math.max((performance.now() - startedAt) / 1000, 0.001);
      item.speed = item.uploaded / seconds;
      updateFileRow(index);
      updateOverallProgress();
    });

    xhr.addEventListener("load", () => {
      if (settled) return;

      if (xhr.status >= 200 && xhr.status < 300) {
        settled = true;
        state.currentXhr = null;
        item.status = "done";
        item.progress = 100;
        item.uploaded = item.file.size;
        updateFileRow(index);
        updateOverallProgress();
        resolve();
        return;
      }

      rejectUpload(t("serverError", { status: xhr.status }));
    });

    xhr.addEventListener("error", () => {
      rejectUpload(t("connectionError"));
    });

    xhr.addEventListener("abort", () => {
      if (state.cancelRequested) {
        rejectUpload(t("canceled"), "canceled");
      } else if (state.stopRequested) {
        rejectUpload(t("stopped"), "stopped");
      } else {
        rejectUpload(t("connectionError"));
      }
    });

    formData.append("file", item.file);
    xhr.send(formData);
  });
}

function resetQueue() {
  state.files = [];
  state.startedAt = 0;
  state.currentXhr = null;
  input.value = "";
  fileList.replaceChildren();
  fileList.hidden = true;
  updateFileCount();
  updateOverallProgress();
  updateControls();
}

input.addEventListener("change", () => {
  selectFiles(input.files);
});

cancelButton.addEventListener("click", () => {
  if (state.isUploading) {
    state.cancelRequested = true;
    state.stopRequested = true;
    if (state.currentXhr) state.currentXhr.abort();
    return;
  }

  resetQueue();
  setStatus(t("canceled"));
});

stopButton.addEventListener("click", () => {
  if (!state.isUploading) return;

  state.stopRequested = true;
  setStatus(t("stoppedStatus"), "warning");
  if (state.currentXhr) state.currentXhr.abort();
});

["dragenter", "dragover"].forEach((eventName) => {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    if (!state.isUploading) dropZone.classList.add("is-dragging");
  });
});

["dragleave", "drop"].forEach((eventName) => {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.remove("is-dragging");
  });
});

dropZone.addEventListener("drop", (event) => {
  if (!state.isUploading) selectFiles(event.dataTransfer.files);
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  if (state.isUploading || state.files.length === 0) return;

  const pendingFiles = state.files.some((item) => item.status !== "done");
  if (!pendingFiles) return;

  state.isUploading = true;
  state.stopRequested = false;
  state.cancelRequested = false;
  if (!state.startedAt) state.startedAt = performance.now();

  state.files.forEach((item) => {
    if (item.status !== "done") {
      item.status = "queued";
      item.progress = 0;
      item.uploaded = 0;
      item.error = "";
    }
  });

  updateControls();
  updateOverallProgress();
  setStatus(t("uploadStarted"), "active");

  for (let index = 0; index < state.files.length; index++) {
    const item = state.files[index];

    if (item.status === "done") continue;
    if (state.stopRequested || state.cancelRequested) break;

    try {
      await uploadFile(item, index);
    } catch (error) {
      if (state.stopRequested || state.cancelRequested) break;
      console.error(`Upload failed for ${item.file.name}:`, error);
    }
  }

  state.isUploading = false;
  state.currentXhr = null;

  if (state.cancelRequested) {
    resetQueue();
    state.stopRequested = false;
    state.cancelRequested = false;
    setStatus(t("canceled"));
    return;
  }

  updateControls();
  updateOverallProgress();

  if (state.stopRequested) {
    setStatus(t("stoppedStatus"), "warning");
    return;
  }

  const failed = state.files.filter((item) => item.status === "error");

  if (failed.length === 0) {
    setStatus(t("uploadedFiles", { count: state.files.length }), "success");
  } else {
    setStatus(t("failedFiles", {
      count: failed.length,
      total: state.files.length,
    }), "error");
  }
});

applyTranslations();
updateControls();
updateOverallProgress();
