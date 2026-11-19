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
// RESUME FILE SELECTION FEEDBACK
document.addEventListener("DOMContentLoaded", function () {
    const resumeInput = document.getElementById("resume");
    const selectedFile = document.getElementById("selectedFile");

    if (!resumeInput || !selectedFile) return;

    resumeInput.addEventListener("change", function () {
        const file = resumeInput.files[0];

        if (file) {
            const fileSize = (file.size / (1024 * 1024)).toFixed(2);
            selectedFile.textContent =
                "Selected: " + file.name + " (" + fileSize + " MB)";
        } else {
            selectedFile.textContent = "No file selected";
        }
    });
});