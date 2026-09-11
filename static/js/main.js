const form = document.getElementById("item-form");
const input = document.getElementById("item-input");
const list = document.getElementById("item-list");
const schemaSelect = document.getElementById("schema-select");
const searchInput = document.getElementById("search-input");
const searchBtn = document.getElementById("search-btn");
const tableSelect = document.getElementById("table-select");
const runAnalysisBtn = document.getElementById("run-analysis-btn");
const analysisStatus = document.getElementById("analysis-status");
const dsnInput = document.getElementById("dsn-input");
const usernameInput = document.getElementById("username-input");
const connectBtn = document.getElementById("connect-btn");
const connectStatus = document.getElementById("connect-status");

// Keep a client-side copy of the item list so Run Analysis can use it
// without an extra round-trip fetch.
let currentItems = window.__INITIAL_ITEMS__ || [];

async function loadTables(schemaValue) {
    if (!schemaValue) {
        tableSelect.innerHTML = '<option value="">Select a schema first</option>';
        return;
    }

    tableSelect.innerHTML = '<option value="">Loading tables...</option>';

    try {
        const res = await fetch(`/api/tables?schema=${encodeURIComponent(schemaValue)}`);
        if (!res.ok) throw new Error("Request failed");
        const tables = await res.json();

        tableSelect.innerHTML = "";
        if (tables.length === 0) {
            tableSelect.innerHTML = '<option value="">No tables found</option>';
            return;
        }

        tables.forEach((code) => {
            const option = document.createElement("option");
            option.value = code;
            option.textContent = code;
            tableSelect.appendChild(option);
        });
    } catch (err) {
        tableSelect.innerHTML = '<option value="">Failed to load tables</option>';
        console.error(err);
    }
}

schemaSelect.addEventListener("change", () => {
    loadTables(schemaSelect.value);
});

const addSelectedBtn = document.getElementById("add-selected-btn");

addSelectedBtn.addEventListener("click", () => {
    const schema = schemaSelect.value;
    const selectedCodes = Array.from(tableSelect.selectedOptions)
        .map((opt) => opt.value)
        .filter(Boolean);

    if (!schema || selectedCodes.length === 0) {
        alert("Select a schema and at least one table first.");
        return;
    }

    selectedCodes.forEach((code) => {
        const fullyQualifiedName = `TCAT_PROD_2.${schema}__${code}.S540_SEGMENTED`;
        addItem(fullyQualifiedName);
    });
});

async function loadSchemas(searchTerm = "") {
    try {
        const url = searchTerm
            ? `/api/schemas?search=${encodeURIComponent(searchTerm)}`
            : "/api/schemas";
        const res = await fetch(url);
        if (!res.ok) throw new Error("Request failed");
        const schemas = await res.json();

        schemaSelect.innerHTML = "";
        if (schemas.length === 0) {
            schemaSelect.innerHTML = '<option value="">No schemas found</option>';
            return;
        }

        schemas.forEach((schema) => {
            const option = document.createElement("option");
            option.value = schema;
            option.textContent = schema;
            schemaSelect.appendChild(option);
        });
    } catch (err) {
        schemaSelect.innerHTML = '<option value="">Failed to load schemas</option>';
        console.error(err);
    }
}

searchBtn.addEventListener("click", () => {
    loadSchemas(searchInput.value.trim()).then(() => loadTables(schemaSelect.value));
});

searchInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
        e.preventDefault();
        loadSchemas(searchInput.value.trim()).then(() => loadTables(schemaSelect.value));
    }
});

function renderItems(items) {
    currentItems = items;
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

form.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (text) {
        addItem(text);
        input.value = "";
    }
});

// Attach handlers to any server-rendered items on load
document.querySelectorAll(".delete-btn").forEach((btn) => {
    btn.addEventListener("click", () => deleteItem(Number(btn.dataset.index)));
});

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

        // Now that we're connected, populate the schema dropdown
        loadSchemas().then(() => loadTables(schemaSelect.value));
    } catch (err) {
        connectStatus.textContent = "Connection failed. Check the console for details.";
        console.error(err);
    } finally {
        connectBtn.disabled = false;
    }
});

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
