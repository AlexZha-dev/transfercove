// Progressive enhancement: without JavaScript, screenshots open as normal links.
(() => {
  const dialog = document.querySelector(".image-dialog");
  const screenshots = [...document.querySelectorAll("[data-lightbox]")];
  if (!dialog || typeof dialog.showModal !== "function" || !screenshots.length) return;

  const image = dialog.querySelector(".dialog-image");
  const caption = dialog.querySelector("#image-caption");
  const counter = dialog.querySelector(".dialog-counter");
  const original = dialog.querySelector(".dialog-original");
  const closeButton = dialog.querySelector(".dialog-close");
  let activeIndex = 0;
  let opener = null;

  function showScreenshot(index) {
    activeIndex = (index + screenshots.length) % screenshots.length;
    const link = screenshots[activeIndex];
    image.src = link.href;
    image.alt = link.querySelector("img").alt;
    caption.textContent = link.dataset.caption;
    counter.textContent = `${activeIndex + 1} / ${screenshots.length}`;
    original.href = link.href;
  }

  screenshots.forEach((link, index) => {
    link.addEventListener("click", (event) => {
      // Preserve open-in-new-tab, download, and other native link gestures.
      if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      opener = link;
      showScreenshot(index);
      dialog.showModal();
      document.body.classList.add("viewer-open");
    });
  });

  closeButton.addEventListener("click", () => dialog.close());
  dialog.querySelector(".dialog-previous").addEventListener("click", () => showScreenshot(activeIndex - 1));
  dialog.querySelector(".dialog-next").addEventListener("click", () => showScreenshot(activeIndex + 1));

  dialog.addEventListener("keydown", (event) => {
    if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
    if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
      event.preventDefault();
      showScreenshot(activeIndex + (event.key === "ArrowRight" ? 1 : -1));
    }
  });

  dialog.addEventListener("click", (event) => {
    const bounds = dialog.getBoundingClientRect();
    const outside = event.clientX < bounds.left || event.clientX > bounds.right
      || event.clientY < bounds.top || event.clientY > bounds.bottom;
    if (event.target === dialog && outside) dialog.close();
  });

  dialog.addEventListener("close", () => {
    document.body.classList.remove("viewer-open");
    opener?.focus({ preventScroll: true });
  });

  // Reveal the answer even if it has already been collapsed.
  document.querySelector('a[href="#security"]')?.addEventListener("click", () => {
    document.querySelector("#security").open = true;
  });
})();
