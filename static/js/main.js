const form = document.getElementById("item-form");
const input = document.getElementById("item-input");
const list = document.getElementById("item-list");
const schemaSelect = document.getElementById("schema-select");
const searchInput = document.getElementById("search-input");
const searchBtn = document.getElementById("search-btn");
const tableSelect = document.getElementById("table-select");
const featureSchemaSelect = document.getElementById("feature-schema-select");
const featureSearchInput = document.getElementById("feature-search-input");
const featureSearchBtn = document.getElementById("feature-search-btn");
const modelTableSelect = document.getElementById("model-table-select");
const featureList = document.getElementById("feature-item-list");
const runAnalysisBtn = document.getElementById("run-analysis-btn");
const analysisStatus = document.getElementById("analysis-status");
const runFeaturesBtn = document.getElementById("run-features-btn");
const featuresStatus = document.getElementById("features-status");
const gainsSchemaSelect = document.getElementById("gains-schema-select");
const gainsSearchInput = document.getElementById("gains-search-input");
const gainsSearchBtn = document.getElementById("gains-search-btn");
const gainsTableSelect = document.getElementById("gains-table-select");
const gainsList = document.getElementById("gains-item-list");
const runGainsBtn = document.getElementById("run-gains-btn");
const gainsStatus = document.getElementById("gains-status");
const dsnInput = document.getElementById("dsn-input");
const usernameInput = document.getElementById("username-input");
const connectBtn = document.getElementById("connect-btn");
const connectStatus = document.getElementById("connect-status");

let currentItems = window.__INITIAL_ITEMS__ || [];
let currentFeatureItems = window.__INITIAL_FEATURE_ITEMS__ || [];
let currentGainItems = window.__INITIAL_GAIN_ITEMS__ || [];

async function loadTables(schemaValue) {
    if (!tableSelect) return;
    if (!schemaValue) {
        tableSelect.innerHTML = '<option value="">Select a project first</option>';
        return;
    }

    tableSelect.innerHTML = '<option value="">Loading tables...</option>';

    try {
        const res = await fetch(`/api/tables?schema=${encodeURIComponent(schemaValue)}`);
        if (!res.ok) throw new Error("Request failed");
        const tables = await res.json();
        if (!Array.isArray(tables)) throw new Error(tables.error || "Request failed");

        tableSelect.innerHTML = "";
        if (tables.length === 0) {
            tableSelect.innerHTML = '<option value="">No tables found</option>';
            return;
        }

        tables.forEach((row) => {
            const shortName = typeof row === "string" ? row.replace(/^S/, "") : row.short_name;
            const scoring = typeof row === "string" ? row : row.scoring;
            const option = document.createElement("option");
            option.value = shortName;
            option.textContent = scoring;
            tableSelect.appendChild(option);
        });
    } catch (err) {
        tableSelect.innerHTML = '<option value="">Failed to load tables</option>';
        console.error(err);
    }
}

async function loadModels(schemaValue, selectEl = modelTableSelect) {
    if (!selectEl) return;
    if (!schemaValue) {
        selectEl.innerHTML = '<option value="">Select a project first</option>';
        return;
    }

    selectEl.innerHTML = '<option value="">Loading models...</option>';

    try {
        const res = await fetch(`/api/models?schema=${encodeURIComponent(schemaValue)}`);
        if (!res.ok) throw new Error("Request failed");
        const models = await res.json();
        if (!Array.isArray(models)) throw new Error(models.error || "Request failed");

        selectEl.innerHTML = "";
        if (models.length === 0) {
            selectEl.innerHTML = '<option value="">No models found</option>';
            return;
        }

        models.forEach((row) => {
            const shortName = typeof row === "string" ? row.replace(/^M/, "") : row.short_name;
            const modeling = typeof row === "string" ? row : row.modeling;
            const option = document.createElement("option");
            option.value = shortName;
            option.textContent = modeling;
            selectEl.appendChild(option);
        });
    } catch (err) {
        selectEl.innerHTML = '<option value="">Failed to load models</option>';
        console.error(err);
    }
}

if (schemaSelect) {
    schemaSelect.addEventListener("change", () => {
        loadTables(schemaSelect.value);
    });
}

if (featureSchemaSelect) {
    featureSchemaSelect.addEventListener("change", () => {
        loadModels(featureSchemaSelect.value, modelTableSelect);
    });
}

if (gainsSchemaSelect) {
    gainsSchemaSelect.addEventListener("change", () => {
        loadModels(gainsSchemaSelect.value, gainsTableSelect);
    });
}

const addSelectedBtn = document.getElementById("add-selected-btn");

if (addSelectedBtn) {
    addSelectedBtn.addEventListener("click", async () => {
        const project = schemaSelect.value;
        const shortNames = Array.from(tableSelect.selectedOptions)
            .map((opt) => opt.value)
            .filter(Boolean);

        if (!project || shortNames.length === 0) {
            alert("Select a project and at least one short name first.");
            return;
        }

        for (const shortName of shortNames) {
            try {
                const res = await fetch(
                    `/api/segmented_table?project=${encodeURIComponent(project)}&short_name=${encodeURIComponent(shortName)}`
                );
                const data = await res.json();
                if (!res.ok || !data.segmented_table) {
                    throw new Error(data.error || "Could not resolve table name.");
                }
                await addItem(data.segmented_table);
            } catch (err) {
                alert(err.message);
                console.error(err);
            }
        }
    });
}

const addGainsSelectedBtn = document.getElementById("add-gains-selected-btn");

if (addGainsSelectedBtn) {
    addGainsSelectedBtn.addEventListener("click", async () => {
        const project = gainsSchemaSelect.value;
        const shortNames = Array.from(gainsTableSelect.selectedOptions)
            .map((opt) => opt.value)
            .filter(Boolean);

        if (!project || shortNames.length === 0) {
            alert("Select a project and at least one model run first.");
            return;
        }

        for (const shortName of shortNames) {
            try {
                const res = await fetch(
                    `/api/gains_table?project=${encodeURIComponent(project)}&short_name=${encodeURIComponent(shortName)}`
                );
                const data = await res.json();
                if (!res.ok || !data.gains_table) {
                    throw new Error(data.error || "Could not resolve gains table.");
                }
                await addGainItem(data.gains_table);
            } catch (err) {
                alert(err.message);
                console.error(err);
            }
        }
    });
}

const addModelSelectedBtn = document.getElementById("add-model-selected-btn");

if (addModelSelectedBtn) {
    addModelSelectedBtn.addEventListener("click", async () => {
        const project = featureSchemaSelect.value;
        const shortNames = Array.from(modelTableSelect.selectedOptions)
            .map((opt) => opt.value)
            .filter(Boolean);

        if (!project || shortNames.length === 0) {
            alert("Select a project and at least one model run first.");
            return;
        }

        for (const shortName of shortNames) {
            try {
                const res = await fetch(
                    `/api/feature_table?project=${encodeURIComponent(project)}&short_name=${encodeURIComponent(shortName)}`
                );
                const data = await res.json();
                if (!res.ok || !data.segmented_table) {
                    throw new Error(data.error || "Could not resolve feature table.");
                }
                await addFeatureItem(data.segmented_table);
            } catch (err) {
                alert(err.message);
                console.error(err);
            }
        }
    });
}

const schemaStatus = document.getElementById("schema-status");
const featureSchemaStatus = document.getElementById("feature-schema-status");
const gainsSchemaStatus = document.getElementById("gains-schema-status");

async function loadSchemas(searchTerm = "", options = {}) {
    const {
        select = schemaSelect,
        statusEl = schemaStatus,
        activity = "S",
        onClear,
    } = options;
    if (!select) return;

    const previous = select.value;
    try {
        const params = new URLSearchParams({ activity });
        if (searchTerm) params.set("search", searchTerm);
        const res = await fetch(`/api/schemas?${params.toString()}`);
        const schemas = await res.json();
        if (!res.ok || !Array.isArray(schemas)) {
            throw new Error((schemas && schemas.error) || "Request failed");
        }

        select.innerHTML = "";
        const placeholder = document.createElement("option");
        placeholder.value = "";
        placeholder.textContent = schemas.length ? "Select a project" : "No projects found";
        select.appendChild(placeholder);

        schemas.forEach((schema) => {
            const option = document.createElement("option");
            option.value = schema;
            option.textContent = schema;
            select.appendChild(option);
        });

        if (previous && schemas.includes(previous)) {
            select.value = previous;
        } else {
            select.value = "";
            if (onClear) onClear();
        }

        const label = searchTerm ? ` matching “${searchTerm}”` : "";
        if (statusEl) {
            statusEl.textContent = `${schemas.length} project${schemas.length === 1 ? "" : "s"}${label}`;
        }
    } catch (err) {
        select.innerHTML = '<option value="">Failed to load schemas</option>';
        if (statusEl) statusEl.textContent = err.message || "Failed to load schemas";
        console.error(err);
    }
}

if (searchBtn) {
    searchBtn.addEventListener("click", () => {
        loadSchemas(searchInput.value.trim(), {
            select: schemaSelect,
            statusEl: schemaStatus,
            activity: "S",
            onClear: () => loadTables(""),
        });
    });
}

if (searchInput) {
    searchInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            searchBtn.click();
        }
    });
    let searchTimer;
    searchInput.addEventListener("input", () => {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(() => searchBtn.click(), 250);
    });
}

if (featureSearchBtn) {
    featureSearchBtn.addEventListener("click", () => {
        loadSchemas(featureSearchInput.value.trim(), {
            select: featureSchemaSelect,
            statusEl: featureSchemaStatus,
            activity: "M",
            onClear: () => loadModels("", modelTableSelect),
        });
    });
}

if (gainsSearchBtn) {
    gainsSearchBtn.addEventListener("click", () => {
        loadSchemas(gainsSearchInput.value.trim(), {
            select: gainsSchemaSelect,
            statusEl: gainsSchemaStatus,
            activity: "M",
            onClear: () => loadModels("", gainsTableSelect),
        });
    });
}

if (featureSearchInput) {
    featureSearchInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            featureSearchBtn.click();
        }
    });
    let featureSearchTimer;
    featureSearchInput.addEventListener("input", () => {
        clearTimeout(featureSearchTimer);
        featureSearchTimer = setTimeout(() => featureSearchBtn.click(), 250);
    });
}

if (gainsSearchInput) {
    gainsSearchInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            gainsSearchBtn.click();
        }
    });
    let gainsSearchTimer;
    gainsSearchInput.addEventListener("input", () => {
        clearTimeout(gainsSearchTimer);
        gainsSearchTimer = setTimeout(() => gainsSearchBtn.click(), 250);
    });
}

function renderItems(items) {
    currentItems = items;
    if (!list) return;
    list.innerHTML = "";
    items.forEach((item, index) => {
        const li = document.createElement("li");
        const span = document.createElement("span");
        span.textContent = item;
        const btn = document.createElement("button");
        btn.textContent = "✕";
        btn.className = "delete-btn";
        btn.dataset.index = index;
        btn.addEventListener("click", () => deleteItem(index));
        li.appendChild(span);
        li.appendChild(btn);
        list.appendChild(li);
    });
}

function renderFeatureItems(items) {
    currentFeatureItems = items;
    if (!featureList) return;
    featureList.innerHTML = "";
    items.forEach((item, index) => {
        const li = document.createElement("li");
        const span = document.createElement("span");
        span.textContent = item;
        const btn = document.createElement("button");
        btn.textContent = "✕";
        btn.className = "delete-feature-btn";
        btn.dataset.index = index;
        btn.addEventListener("click", () => deleteFeatureItem(index));
        li.appendChild(span);
        li.appendChild(btn);
        featureList.appendChild(li);
    });
}

function renderGainItems(items) {
    currentGainItems = items;
    if (!gainsList) return;
    gainsList.innerHTML = "";
    items.forEach((item, index) => {
        const li = document.createElement("li");
        const span = document.createElement("span");
        span.textContent = item;
        const btn = document.createElement("button");
        btn.textContent = "✕";
        btn.className = "delete-gains-btn";
        btn.dataset.index = index;
        btn.addEventListener("click", () => deleteGainItem(index));
        li.appendChild(span);
        li.appendChild(btn);
        gainsList.appendChild(li);
    });
}

async function addItem(text) {
    const res = await fetch("/api/items", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
    });
    if (res.ok) {
        const data = await res.json();
        renderItems(data.items);
    }
}

async function deleteItem(index) {
    const res = await fetch(`/api/items/${index}`, { method: "DELETE" });
    if (res.ok) {
        const data = await res.json();
        renderItems(data.items);
    }
}

async function addFeatureItem(text) {
    const res = await fetch("/api/feature_items", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
    });
    if (res.ok) {
        const data = await res.json();
        renderFeatureItems(data.items);
    }
}

async function deleteFeatureItem(index) {
    const res = await fetch(`/api/feature_items/${index}`, { method: "DELETE" });
    if (res.ok) {
        const data = await res.json();
        renderFeatureItems(data.items);
    }
}

async function addGainItem(text) {
    const res = await fetch("/api/gain_items", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
    });
    if (res.ok) {
        const data = await res.json();
        renderGainItems(data.items);
    }
}

async function deleteGainItem(index) {
    const res = await fetch(`/api/gain_items/${index}`, { method: "DELETE" });
    if (res.ok) {
        const data = await res.json();
        renderGainItems(data.items);
    }
}

if (form) {
    form.addEventListener("submit", (e) => {
        e.preventDefault();
        const text = input.value.trim();
        if (text) {
            addItem(text);
            input.value = "";
        }
    });
}

document.querySelectorAll(".delete-btn").forEach((btn) => {
    btn.addEventListener("click", () => deleteItem(Number(btn.dataset.index)));
});

document.querySelectorAll(".delete-feature-btn").forEach((btn) => {
    btn.addEventListener("click", () => deleteFeatureItem(Number(btn.dataset.index)));
});

document.querySelectorAll(".delete-gains-btn").forEach((btn) => {
    btn.addEventListener("click", () => deleteGainItem(Number(btn.dataset.index)));
});

if (connectBtn) {
    connectBtn.addEventListener("click", async () => {
        const dsn = dsnInput.value.trim();
        const username = usernameInput.value.trim();

        if (!dsn) {
            connectStatus.textContent = "Enter your System DSN name first.";
            return;
        }

        connectBtn.disabled = true;
        connectStatus.textContent = "Connecting — a browser window may open for you to sign in...";

        try {
            const res = await fetch("/api/connect", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ dsn, username }),
            });
            const data = await res.json();

            if (!res.ok) {
                connectStatus.textContent = data.error || "Failed to connect.";
                return;
            }

            connectStatus.textContent = `Connected via ${data.dsn}${data.username ? " as " + data.username : ""}.`;
            if (schemaSelect) {
                loadSchemas(searchInput ? searchInput.value.trim() : "", {
                    select: schemaSelect,
                    statusEl: schemaStatus,
                    activity: "S",
                    onClear: () => loadTables(""),
                });
            }
            if (featureSchemaSelect) {
                loadSchemas(featureSearchInput ? featureSearchInput.value.trim() : "", {
                    select: featureSchemaSelect,
                    statusEl: featureSchemaStatus,
                    activity: "M",
                    onClear: () => loadModels("", modelTableSelect),
                });
            }
            if (gainsSchemaSelect) {
                loadSchemas(gainsSearchInput ? gainsSearchInput.value.trim() : "", {
                    select: gainsSchemaSelect,
                    statusEl: gainsSchemaStatus,
                    activity: "M",
                    onClear: () => loadModels("", gainsTableSelect),
                });
            }
        } catch (err) {
            connectStatus.textContent = "Connection failed. Check the console for details.";
            console.error(err);
        } finally {
            connectBtn.disabled = false;
        }
    });
}

if (runAnalysisBtn) {
    runAnalysisBtn.addEventListener("click", async () => {
        if (currentItems.length < 2) {
            analysisStatus.textContent = "Add at least two tables to the list before running analysis.";
            return;
        }

        runAnalysisBtn.disabled = true;
        analysisStatus.textContent = `Running analysis on ${currentItems.length} tables — this may take a while depending on how many pairs are being compared...`;

        try {
            const res = await fetch("/api/run_analysis", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ tables: currentItems }),
            });
            const data = await res.json();

            if (!res.ok) {
                analysisStatus.textContent = data.error || "Analysis failed.";
                return;
            }

            analysisStatus.innerHTML =
                `Done! Generated ${data.pair_count} pairwise comparison(s). ` +
                `<a href="${data.pdf_url}" target="_blank">Download PDF</a>`;
        } catch (err) {
            analysisStatus.textContent = "Analysis failed. Check the server console for details.";
            console.error(err);
        } finally {
            runAnalysisBtn.disabled = false;
        }
    });
}

function escapeHtml(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

function csvEscape(value) {
    const text = value == null ? "" : String(value);
    if (/[",\n\r]/.test(text)) {
        return `"${text.replace(/"/g, '""')}"`;
    }
    return text;
}

function buildFeatureCsv(columns, rows) {
    const header = columns.map(csvEscape).join(",");
    const body = rows
        .map((row) =>
            row
                .map((value, index) => {
                    if (index === 0) return csvEscape(value);
                    if (value == null || value === "") return "";
                    return csvEscape(Number(value).toFixed(6));
                })
                .join(",")
        )
        .join("\r\n");
    return `${header}\r\n${body}\r\n`;
}

const DATABAR_COLORS = [
    "rgba(45, 108, 223, 0.38)",
    "rgba(200, 16, 46, 0.32)",
    "rgba(26, 143, 76, 0.35)",
    "rgba(196, 120, 16, 0.38)",
    "rgba(102, 51, 153, 0.32)",
    "rgba(0, 128, 128, 0.32)",
];

function columnMaxes(rows) {
    const maxes = [];
    if (!rows.length) return maxes;
    const width = rows[0].length;
    for (let index = 1; index < width; index += 1) {
        let max = 0;
        rows.forEach((row) => {
            const value = row[index];
            if (value == null || value === "") return;
            const number = Number(value);
            if (!Number.isNaN(number) && number > max) max = number;
        });
        maxes[index] = max;
    }
    return maxes;
}

function renderComparisonTable(columns, rows, csvUrl, ids, downloadName, options = {}) {
    const wrap = document.getElementById(ids.wrap);
    const table = document.getElementById(ids.table);
    const downloadLink = document.getElementById(ids.download);
    if (!wrap || !table) return;

    const mode = options.mode || "overlap";
    const maxes = mode === "databars" ? columnMaxes(rows) : [];
    const head = columns.map((col) => `<th>${escapeHtml(col)}</th>`).join("");
    const body = rows
        .map((row) => {
            const overlapCount = row
                .slice(1)
                .filter((value) => value != null && value !== "")
                .length;
            const hasOverlap = mode === "overlap" && overlapCount > 1;
            const cells = row
                .map((value, index) => {
                    if (index === 0) {
                        const cls = hasOverlap ? ' class="overlap-feature"' : "";
                        return `<td${cls}>${escapeHtml(value)}</td>`;
                    }
                    const empty = value == null || value === "";
                    const num = empty ? "" : Number(value).toFixed(4);
                    if (mode === "databars") {
                        if (empty) return `<td class="num"></td>`;
                        const max = maxes[index] || 0;
                        const pct = max > 0 ? Math.max(0, Math.min(100, (Number(value) / max) * 100)) : 0;
                        const color = DATABAR_COLORS[(index - 1) % DATABAR_COLORS.length];
                        return `<td class="num databar"><span class="databar-fill" style="width:${pct.toFixed(1)}%;background:${color}"></span><span class="databar-value">${num}</span></td>`;
                    }
                    const cls = ["num"];
                    if (hasOverlap && !empty) cls.push("overlap");
                    return `<td class="${cls.join(" ")}">${num}</td>`;
                })
                .join("");
            return `<tr${hasOverlap ? ' class="has-overlap"' : ""}>${cells}</tr>`;
        })
        .join("");
    table.innerHTML = `<thead><tr>${head}</tr></thead><tbody>${body}</tbody>`;

    if (downloadLink) {
        if (downloadLink.dataset.objectUrl) {
            URL.revokeObjectURL(downloadLink.dataset.objectUrl);
            delete downloadLink.dataset.objectUrl;
        }
        if (csvUrl) {
            downloadLink.href = csvUrl;
        } else {
            const blob = new Blob([buildFeatureCsv(columns, rows)], { type: "text/csv;charset=utf-8" });
            const objectUrl = URL.createObjectURL(blob);
            downloadLink.href = objectUrl;
            downloadLink.dataset.objectUrl = objectUrl;
        }
        downloadLink.setAttribute("download", downloadName);
        downloadLink.hidden = false;
    }

    wrap.hidden = false;
}

function renderFeatureTable(columns, rows, csvUrl) {
    renderComparisonTable(
        columns,
        rows,
        csvUrl,
        {
            wrap: "features-table-wrap",
            table: "features-table",
            download: "features-download-link",
        },
        "feature_importance.csv"
    );
}

function renderGainsTable(columns, rows, csvUrl) {
    renderComparisonTable(
        columns,
        rows,
        csvUrl,
        {
            wrap: "gains-table-wrap",
            table: "gains-table",
            download: "gains-download-link",
        },
        "gains_comparison.csv",
        { mode: "databars" }
    );
}

if (runFeaturesBtn) {
    runFeaturesBtn.addEventListener("click", async () => {
        if (currentFeatureItems.length < 1) {
            featuresStatus.textContent = "Add at least one model before running comparison.";
            return;
        }

        runFeaturesBtn.disabled = true;
        featuresStatus.textContent = `Loading top-20 importance for ${currentFeatureItems.length} model${currentFeatureItems.length === 1 ? "" : "s"}...`;
        const wrap = document.getElementById("features-table-wrap");
        const downloadLink = document.getElementById("features-download-link");
        if (wrap) wrap.hidden = true;
        if (downloadLink) downloadLink.hidden = true;

        try {
            const res = await fetch("/api/run_features", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ tables: currentFeatureItems }),
            });
            const data = await res.json();

            if (!res.ok) {
                featuresStatus.textContent = data.error || "Comparison failed.";
                return;
            }

            renderFeatureTable(data.columns, data.rows, data.csv_url);
            featuresStatus.innerHTML =
                `${data.feature_count} features across ${data.model_count} model${data.model_count === 1 ? "" : "s"}.` +
                (data.csv_url ? ` <a href="${data.csv_url}">Download CSV</a>` : "");
        } catch (err) {
            featuresStatus.textContent = "Comparison failed. Check the server console for details.";
            console.error(err);
        } finally {
            runFeaturesBtn.disabled = false;
        }
    });
}

if (runGainsBtn) {
    runGainsBtn.addEventListener("click", async () => {
        if (currentGainItems.length < 1) {
            gainsStatus.textContent = "Add at least one model before running comparison.";
            return;
        }

        runGainsBtn.disabled = true;
        gainsStatus.textContent = `Loading validation gains for ${currentGainItems.length} model${currentGainItems.length === 1 ? "" : "s"}...`;
        const wrap = document.getElementById("gains-table-wrap");
        const downloadLink = document.getElementById("gains-download-link");
        if (wrap) wrap.hidden = true;
        if (downloadLink) downloadLink.hidden = true;

        try {
            const res = await fetch("/api/run_gains", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ tables: currentGainItems }),
            });
            const data = await res.json();

            if (!res.ok) {
                gainsStatus.textContent = data.error || "Comparison failed.";
                return;
            }

            renderGainsTable(data.columns, data.rows, data.csv_url);
            gainsStatus.innerHTML =
                `${data.segment_count} segments across ${data.model_count} model${data.model_count === 1 ? "" : "s"}.` +
                (data.csv_url ? ` <a href="${data.csv_url}">Download CSV</a>` : "");
        } catch (err) {
            gainsStatus.textContent = "Comparison failed. Check the server console for details.";
            console.error(err);
        } finally {
            runGainsBtn.disabled = false;
        }
    });
}

if (window.__ACTIVE_VIEW__ === "comparison" && schemaSelect) {
    loadSchemas(searchInput ? searchInput.value.trim() : "", {
        select: schemaSelect,
        statusEl: schemaStatus,
        activity: "S",
        onClear: () => loadTables(""),
    });
}

if (window.__ACTIVE_VIEW__ === "features" && featureSchemaSelect) {
    loadSchemas(featureSearchInput ? featureSearchInput.value.trim() : "", {
        select: featureSchemaSelect,
        statusEl: featureSchemaStatus,
        activity: "M",
        onClear: () => loadModels("", modelTableSelect),
    });
}

if (window.__ACTIVE_VIEW__ === "gains" && gainsSchemaSelect) {
    loadSchemas(gainsSearchInput ? gainsSearchInput.value.trim() : "", {
        select: gainsSchemaSelect,
        statusEl: gainsSchemaStatus,
        activity: "M",
        onClear: () => loadModels("", gainsTableSelect),
    });
}
