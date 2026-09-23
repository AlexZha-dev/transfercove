const demoDrop = document.querySelector("#demo-drop");
const demoInput = document.querySelector("#demo-input");
const chooseFiles = document.querySelector("#choose-files");
const demoQueue = document.querySelector("#demo-queue");
const demoCount = document.querySelector("#demo-count");
const demoStart = document.querySelector("#demo-start");
const demoStatus = document.querySelector("#demo-status");
const year = document.querySelector("#year");

if (year) year.textContent = new Date().getFullYear();

const formatBytes = (bytes) => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
};

function addFiles(files) {
  if (!files.length) return;

  demoQueue.replaceChildren();
  Array.from(files).slice(0, 4).forEach((file) => {
    const row = document.createElement("div");
    row.className = "queue-row";
    row.dataset.demoFile = file.name;
    row.dataset.demoSize = formatBytes(file.size);
    row.innerHTML = `
      <span class="queue-file-icon">↥</span>
      <span class="queue-file-copy">
        <strong></strong>
        <small><span class="queue-size"></span> · <em>Ready to send</em></small>
        <span class="mini-progress"><i></i></span>
      </span>
      <b class="queue-percent">0%</b>
    `;
    row.querySelector("strong").textContent = file.name;
    row.querySelector(".queue-size").textContent = formatBytes(file.size);
    demoQueue.appendChild(row);
  });
  demoCount.textContent = `${Math.min(files.length, 4)} ${files.length === 1 ? "file" : "files"} · demo queue`;
  demoStatus.textContent = "Ready when you are";
  demoStatus.classList.remove("is-done");
  demoStart.disabled = false;
}

chooseFiles?.addEventListener("click", (event) => {
  event.preventDefault();
  demoInput?.click();
});

demoInput?.addEventListener("change", (event) => addFiles(event.target.files));

["dragenter", "dragover"].forEach((eventName) => {
  demoDrop?.addEventListener(eventName, (event) => {
    event.preventDefault();
    demoDrop.classList.add("is-dragging");
  });
});

["dragleave", "drop"].forEach((eventName) => {
  demoDrop?.addEventListener(eventName, (event) => {
    event.preventDefault();
    demoDrop.classList.remove("is-dragging");
  });
});

demoDrop?.addEventListener("drop", (event) => addFiles(event.dataTransfer.files));

demoStart?.addEventListener("click", () => {
  const rows = [...demoQueue.querySelectorAll(".queue-row")];
  if (!rows.length || demoStart.disabled) return;

  demoStart.disabled = true;
  demoStatus.classList.remove("is-done");
  demoStatus.textContent = "Transferring locally…";
  let rowIndex = 0;
  let progress = 0;

  const timer = window.setInterval(() => {
    const row = rows[rowIndex];
    if (!row) {
      window.clearInterval(timer);
      demoStatus.textContent = "Transfer complete · files stayed local";
      demoStatus.classList.add("is-done");
      demoStart.disabled = false;
      return;
    }

    row.classList.add("is-active");
    const percent = row.querySelector(".queue-percent");
    const fill = row.querySelector(".mini-progress i");
    const state = row.querySelector("em");
    progress = Math.min(100, progress + 8 + Math.round(Math.random() * 12));
    percent.textContent = `${progress}%`;
    fill.style.width = `${progress}%`;
    state.textContent = progress === 100 ? "Transferred" : "Sending locally";

    if (progress === 100) {
      row.classList.remove("is-active");
      row.classList.add("is-done");
      rowIndex += 1;
      progress = 0;
    }
  }, 180);
});

document.querySelectorAll('a[href^="#"]').forEach((link) => {
  link.addEventListener("click", (event) => {
    const target = document.querySelector(link.getAttribute("href"));
    if (!target) return;
    event.preventDefault();
    target.scrollIntoView({ behavior: "smooth", block: "start" });
  });
});
