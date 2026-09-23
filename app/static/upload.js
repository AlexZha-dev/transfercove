const form = document.querySelector("#upload-form");
const input = document.querySelector("#file-input");
const uploadStatus = document.querySelector("#status");
const submitButton = form.querySelector("button[type=\"submit\"]");

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const files = Array.from(input.files);
  const failedFiles = [];

  if (files.length === 0) {
    uploadStatus.textContent = "Выберите хотя бы один файл";
    return;
  }

  submitButton.disabled = true;
  input.disabled = true;

  try {
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const formData = new FormData();

      formData.append("file", file);
      uploadStatus.textContent =
        `Загрузка ${i + 1}/${files.length}: ${file.name}`;

      try {
        const response = await fetch("/v1/files", {
          method: "POST",
          body: formData,
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        await response.json();
      } catch (error) {
        console.error(`Не удалось загрузить файл ${file.name}:`, error);
        failedFiles.push(file.name);
      }
    }

    if (failedFiles.length === 0) {
      uploadStatus.textContent = `Загружено файлов: ${files.length}`;
      form.reset();
    } else {
      uploadStatus.textContent =
        `Не загружено файлов: ${failedFiles.length} из ${files.length}`;
    }
  } finally {
    submitButton.disabled = false;
    input.disabled = false;
  }
});
