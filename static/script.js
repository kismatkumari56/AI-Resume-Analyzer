// DARK / LIGHT MODE TOGGLE
//
// The theme is stored as data-theme="dark" on the <html> element and the
// choice is saved in localStorage so it survives page reloads and works on
// both pages. This file is loaded in <head> so the saved theme is applied
// before the page is painted (no flash of the wrong theme).

const THEME_KEY = "resumeTheme";

function getSavedTheme() {
    try {
        return localStorage.getItem(THEME_KEY);
    } catch (error) {
        // Storage can be blocked (for example in private mode)
        return null;
    }
}

function saveTheme(theme) {
    try {
        localStorage.setItem(THEME_KEY, theme);
    } catch (error) {
        // The theme still switches, it just will not be remembered
    }
}

function applyTheme(theme) {
    if (theme === "dark") {
        document.documentElement.setAttribute("data-theme", "dark");
    } else {
        document.documentElement.removeAttribute("data-theme");
    }
}

// Used when the user clicks the toggle. Cards and buttons have a 0.3s CSS
// transition, which would leave some of them half-faded (light text on a
// light card) for a moment, so transitions are turned off during the switch.
function switchTheme(theme) {
    const root = document.documentElement;

    root.classList.add("theme-switching");
    applyTheme(theme);
    void root.offsetWidth; // force the browser to apply the new colors now
    root.classList.remove("theme-switching");
}

// Apply the saved theme immediately (light is the default)
applyTheme(getSavedTheme());

document.addEventListener("DOMContentLoaded", function () {

    const themeToggle = document.getElementById("themeToggle");

    if (!themeToggle) return;

    function isDark() {
        return document.documentElement.getAttribute("data-theme") === "dark";
    }

    function updateButton() {
        if (isDark()) {
            themeToggle.textContent = "☀️ Light Mode";
            themeToggle.setAttribute("aria-label", "Switch to light mode");
        } else {
            themeToggle.textContent = "🌙 Dark Mode";
            themeToggle.setAttribute("aria-label", "Switch to dark mode");
        }
    }

    updateButton();

    themeToggle.addEventListener("click", function () {

        const newTheme = isDark() ? "light" : "dark";

        switchTheme(newTheme);
        saveTheme(newTheme);
        updateButton();
    });

    // ==========================================
    // ROADMAP TASK COMPLETION LOGIC
    // ==========================================
    const checkboxes = document.querySelectorAll(".roadmap-task-checkbox");
    if (checkboxes.length > 0) {
        const progressBar = document.getElementById("roadmap-progress-bar");
        const progressText = document.getElementById("roadmap-progress-text");
        const STORAGE_KEY = "roadmap_completed_tasks";

        let completedSet = new Set();
        try {
            const saved = localStorage.getItem(STORAGE_KEY);
            if (saved) {
                completedSet = new Set(JSON.parse(saved));
            }
        } catch (e) {}

        function updateRoadmapProgress() {
            let completed = 0;
            const total = checkboxes.length;

            checkboxes.forEach(function (cb) {
                const taskId = cb.getAttribute("data-task-id");
                const card = document.getElementById("card_" + taskId);
                if (cb.checked) {
                    completed++;
                    completedSet.add(taskId);
                    if (card) {
                        card.style.opacity = "0.65";
                        const title = card.querySelector(".task-title");
                        if (title) title.style.textDecoration = "line-through";
                    }
                } else {
                    completedSet.delete(taskId);
                    if (card) {
                        card.style.opacity = "1";
                        const title = card.querySelector(".task-title");
                        if (title) title.style.textDecoration = "none";
                    }
                }
            });

            const pct = total > 0 ? Math.round((completed / total) * 100) : 0;
            if (progressBar) {
                progressBar.style.width = pct + "%";
                progressBar.setAttribute("data-width", pct);
            }
            if (progressText) {
                progressText.textContent = `${completed} of ${total} Tasks Completed (${pct}%)`;
            }

            try {
                localStorage.setItem(STORAGE_KEY, JSON.stringify(Array.from(completedSet)));
            } catch (e) {}
        }

        checkboxes.forEach(function (cb) {
            const taskId = cb.getAttribute("data-task-id");
            if (completedSet.has(taskId)) {
                cb.checked = true;
            }

            cb.addEventListener("change", function () {
                updateRoadmapProgress();

                // Sync with server session
                try {
                    fetch("/roadmap/toggle", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ task_id: taskId, completed: cb.checked }),
                    }).catch(function () {});
                } catch (e) {}
            });
        });

        updateRoadmapProgress();
    }

});

// ---------------------------------------------------------------------------
// Resume file size validation (runs in the browser before upload)
// Keep MAX_RESUME_SIZE_MB in sync with MAX_CONTENT_LENGTH in app.py.
// ---------------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", function () {

    const MAX_RESUME_SIZE_MB = 10;
    const MAX_RESUME_SIZE_BYTES = MAX_RESUME_SIZE_MB * 1024 * 1024;

    const fileInput = document.querySelector('input[type="file"][name="resume"]');
    if (!fileInput) return;

    const form = fileInput.closest("form");

    const errorBox = document.createElement("div");
    errorBox.id = "fileSizeError";
    errorBox.setAttribute("role", "alert");
    errorBox.style.cssText =
        "display:none; margin-top:10px; padding:10px 14px; border-radius:8px; " +
        "background:#fdecea; color:#b3261e; border:1px solid #f5c2c0; " +
        "font-size:13px; font-weight:500;";
    fileInput.insertAdjacentElement("afterend", errorBox);

    function formatSize(bytes) {
        return (bytes / (1024 * 1024)).toFixed(2) + " MB";
    }

    function validateFileSize() {
        const file = fileInput.files && fileInput.files[0];

        if (file && file.size > MAX_RESUME_SIZE_BYTES) {
            errorBox.textContent =
                "File is too large (" + formatSize(file.size) + "). " +
                "Maximum allowed size is " + MAX_RESUME_SIZE_MB + " MB. " +
                "Please choose a smaller file.";
            errorBox.style.display = "block";
            fileInput.setCustomValidity("File exceeds the " + MAX_RESUME_SIZE_MB + " MB limit.");
            fileInput.value = "";
            return false;
        }

        errorBox.style.display = "none";
        fileInput.setCustomValidity("");
        return true;
    }

    fileInput.addEventListener("change", validateFileSize);

    if (form) {
        form.addEventListener("submit", function (event) {
            if (!validateFileSize()) event.preventDefault();
        });
    }
});
document.addEventListener("DOMContentLoaded", function () {
  const box = document.querySelector(".upload-box");
  const input = document.getElementById("resume-input");
  const nameEl = document.getElementById("file-name");
  const errorEl = document.getElementById("upload-error");
  if (!box || !input) return;

  const MAX_SIZE = 10 * 1024 * 1024;
  const ALLOWED = [".pdf", ".docx"];

  function validate(file) {
    const name = file.name.toLowerCase();
    if (!ALLOWED.some((ext) => name.endsWith(ext))) {
      return "Invalid file format. Please upload a PDF or DOCX file.";
    }
    if (file.size > MAX_SIZE) return "File size exceeds the 10 MB limit.";
    return "";
  }

  function showFile(file) {
    const error = validate(file);
    if (error) {
      errorEl.textContent = error;
      nameEl.textContent = "";
      input.value = "";
      return false;
    }
    errorEl.textContent = "";
    nameEl.textContent = "Selected: " + file.name;
    return true;
  }

  input.addEventListener("change", function () {
    if (input.files.length) showFile(input.files[0]);
  });

  ["dragenter", "dragover"].forEach(function (evt) {
    box.addEventListener(evt, function (e) {
      e.preventDefault();
      box.classList.add("dragover");
    });
  });

  ["dragleave", "drop"].forEach(function (evt) {
    box.addEventListener(evt, function (e) {
      e.preventDefault();
      box.classList.remove("dragover");
    });
  });

  box.addEventListener("drop", function (e) {
    const files = e.dataTransfer.files;
    if (files.length !== 1) {
      errorEl.textContent = "Please drop only one file.";
      return;
    }
    if (showFile(files[0])) input.files = files;
  });

  ["dragover", "drop"].forEach(function (evt) {
    window.addEventListener(evt, function (e) { e.preventDefault(); });
  });
});