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

    if (themeToggle) {
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
    }

    // ==========================================
    // ROADMAP TASK COMPLETION LOGIC
    // ==========================================
    const checkboxes = document.querySelectorAll(".roadmap-task-checkbox");
    if (checkboxes.length > 0) {
        const progressBar = document.getElementById("roadmap-progress-bar");
        const progressText = document.getElementById("roadmap-progress-text");

        function updateRoadmapProgress() {
            let completed = 0;
            const total = checkboxes.length;

            checkboxes.forEach(function (cb) {
                const taskId = cb.getAttribute("data-task-id");
                const card = document.getElementById("card_" + taskId);
                if (cb.checked) {
                    completed++;
                    if (card) {
                        card.style.opacity = "0.65";
                        const title = card.querySelector(".task-title");
                        if (title) title.style.textDecoration = "line-through";
                    }
                } else {
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
        }

        checkboxes.forEach(function (cb) {
            const taskId = cb.getAttribute("data-task-id");

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
// Resume upload validation & drag-and-drop handling
// Keep MAX_RESUME_SIZE_MB in sync with MAX_CONTENT_LENGTH in app.py.
// ---------------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", function () {
    const MAX_RESUME_SIZE_MB = 10;
    const MAX_RESUME_SIZE_BYTES = MAX_RESUME_SIZE_MB * 1024 * 1024;
    const ALLOWED_EXTENSIONS = [".pdf", ".docx"];

    const box = document.querySelector(".upload-box");
    const input = document.getElementById("resume-input") || document.querySelector('input[type="file"][name="resume"]');
    if (!input) return;

    const form = input.closest("form");
    const nameEl = document.getElementById("file-name");
    const errorEl = document.getElementById("upload-error");

    function formatSize(bytes) {
        return (bytes / (1024 * 1024)).toFixed(2) + " MB";
    }

    function validateFile(file) {
        if (!file) return "";
        const name = file.name.toLowerCase();
        if (!ALLOWED_EXTENSIONS.some(function (ext) { return name.endsWith(ext); })) {
            return "Invalid file format. Please upload a PDF or DOCX file.";
        }
        if (file.size > MAX_RESUME_SIZE_BYTES) {
            return (
                "File is too large (" + formatSize(file.size) + "). " +
                "Maximum allowed size is " + MAX_RESUME_SIZE_MB + " MB. " +
                "Please choose a smaller file."
            );
        }
        return "";
    }

    function showError(message) {
        if (errorEl) errorEl.textContent = message;
        if (nameEl) nameEl.textContent = "";
    }

    function applyFile(file) {
        const error = validateFile(file);
        if (error) {
            showError(error);
            input.value = "";
            input.setCustomValidity("");
            return false;
        }
        if (errorEl) errorEl.textContent = "";
        if (nameEl) nameEl.textContent = file ? "Selected: " + file.name : "";
        input.setCustomValidity("");
        return true;
    }

    input.addEventListener("change", function () {
        if (input.files && input.files.length) {
            applyFile(input.files[0]);
        } else {
            if (errorEl) errorEl.textContent = "";
            if (nameEl) nameEl.textContent = "";
            input.setCustomValidity("");
        }
    });

    if (form) {
        form.addEventListener("submit", function (event) {
            const file = input.files && input.files[0];
            if (!file) {
                event.preventDefault();
                showError("Please choose a PDF or DOCX resume before analyzing.");
                return;
            }
            if (!applyFile(file)) {
                event.preventDefault();
            }
        });
    }

    if (!box) return;

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
        const files = e.dataTransfer && e.dataTransfer.files;
        if (!files || files.length !== 1) {
            showError("Please drop only one file.");
            return;
        }
        if (applyFile(files[0])) {
            input.files = files;
        }
    });

    ["dragover", "drop"].forEach(function (evt) {
        window.addEventListener(evt, function (e) { e.preventDefault(); });
    });
});