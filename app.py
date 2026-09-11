import os
import uuid
import pyodbc
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # headless backend — no display available on the server
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import seaborn as sns
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, send_from_directory

# Load credentials from a local .env file (see .env.example for the format).
# This keeps secrets out of the source code and out of shared environment variables.
load_dotenv()

app = Flask(__name__)

# In-memory data store (replace with a database for real use)
items = []

# Where generated analysis PDFs get saved so they can be downloaded
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generated")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def extract_abbr(fully_qualified_name):
    """
    Pull a short label out of a fully-qualified table name for use in
    pair labels, e.g. 'TCAT_PROD_2.SHRINERS_DAF__S001.S540_SEGMENTED' -> 'S001'
    """
    parts = fully_qualified_name.split(".")
    schema_part = parts[1] if len(parts) > 1 else fully_qualified_name
    return fully_qualified_name.split(".")[1]
    #return schema_part.split("__")[-1] if "__" in schema_part else schema_part


def build_master_dataframe(tables, conn):
    """
    Run the pairwise MODEL_SEGMENT overlap query for every unique pair of
    tables in the given list, and concatenate the results into one dataframe.
    """
    df_list = []
    for i in range(len(tables)):
        for j in range(i + 1, len(tables)):
            table_a = tables[i]
            table_b = tables[j]
            abbr1 = extract_abbr(table_a)
            abbr2 = extract_abbr(table_b)

            sql = f"""
                SELECT
                    a.MODEL_SEGMENT     AS segment_a,
                    b.MODEL_SEGMENT     AS segment_b,
                    COUNT(*)            AS pid_count,
                    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2)  AS pct_of_overlap,
                    CASE WHEN a.MODEL_SEGMENT = b.MODEL_SEGMENT
                    THEN 'Match' ELSE 'Mismatch' END AS agreement,
                    '{abbr1} vs. {abbr2}' AS pair
                FROM {table_a} a
                INNER JOIN {table_b} b ON a.PID = b.PID
                GROUP BY a.MODEL_SEGMENT, b.MODEL_SEGMENT
            """
            df = pd.read_sql(sql, conn)
            df_list.append(df)

    if not df_list:
        return pd.DataFrame()
    return pd.concat(df_list, ignore_index=True)


def generate_heatmaps_pdf(master_df, output_path):
    """
    For every unique pair in the master dataframe, pivot into a segment x
    segment matrix and render a heatmap page into a single output PDF.
    """
    pairs = master_df["PAIR"].unique().tolist()
    with PdfPages(output_path) as pdf:
        for pair in pairs:
            df = master_df[master_df["PAIR"] == pair].copy()
            df["PID_COUNT"] = df["PID_COUNT"] / 10000

            matrix = df.pivot(
                index="SEGMENT_A", columns="SEGMENT_B", values="PID_COUNT"
            ).fillna(0)

            label_a, label_b = [p.strip() for p in pair.split("vs.")]
            matrix = matrix.rename_axis(
                index=f"{label_a}_Segments", columns=f"{label_b}_Segments"
            )

            mean_val = matrix.values.mean()
            fig, ax = plt.subplots(figsize=(14, 10))
            sns.heatmap(
                matrix,
                annot=True,
                cmap="coolwarm",
                annot_kws={"size": 6},
                square=False,
                center=mean_val,
                fmt=".0f",
                ax=ax,
            )
            fig.subplots_adjust(left=0.2, right=0.8, top=0.8, bottom=0.2)
            ax.set_title(f"{pair}")
            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)


def get_snowflake_connection():
    """
    Open a Snowflake connection via an ODBC System DSN. The DSN name and
    username come from what the user entered in the GUI's connection form
    (see /api/connect), falling back to environment variable defaults if
    they haven't entered anything yet.

    The connection is cached at module level and reused across requests,
    so the browser SSO prompt only appears once — either when the user
    clicks "Connect", or lazily on the first query if they skipped that
    step — not on every request.
    """
    global _cached_conn

    if _cached_conn is not None:
        try:
            # Cheap check that the cached connection is still alive
            _cached_conn.cursor().execute("SELECT 1")
            return _cached_conn
        except Exception:
            # Connection died / session expired — fall through and reconnect
            try:
                _cached_conn.close()
            except Exception:
                pass
            _cached_conn = None

    dsn_name = _connection_config["dsn"] or os.environ.get("SNOWFLAKE_DSN", "Snowflake_SSO")
    username = _connection_config["username"] or os.environ.get("SNOWFLAKE_USER")

    conn_str = f"DSN={dsn_name}"
    if username:
        conn_str += f";UID={username}"

    _cached_conn = pyodbc.connect(conn_str, autocommit=True)
    return _cached_conn


# Holds the DSN name / username entered in the GUI's connection form,
# so get_snowflake_connection() knows what to use.
_connection_config = {"dsn": None, "username": None}


_cached_conn = None


@app.route("/")
def index():
    """Render the main GUI page."""
    return render_template("index.html", items=items)


@app.route("/api/connect", methods=["POST"])
def connect():
    """
    Accept a DSN name and username entered in the GUI, store them for
    get_snowflake_connection() to use, and immediately open a connection
    (triggering the one browser SSO prompt now, up front, rather than
    lazily on the first query).
    """
    global _cached_conn

    data = request.get_json()
    dsn = (data or {}).get("dsn", "").strip()
    username = (data or {}).get("username", "").strip()

    if not dsn:
        return jsonify({"error": "DSN name is required."}), 400

    # Changing connection settings invalidates any existing cached connection
    if _cached_conn is not None:
        try:
            _cached_conn.close()
        except Exception:
            pass
        _cached_conn = None

    _connection_config["dsn"] = dsn
    _connection_config["username"] = username or None

    try:
        get_snowflake_connection()  # opens (and caches) the connection now
        return jsonify({"connected": True, "dsn": dsn, "username": username})
    except Exception as e:
        app.logger.error(f"Connection failed: {e}")
        return jsonify({"error": "Failed to connect. Check the DSN name and try again."}), 500


@app.route("/api/schemas", methods=["GET"])
def get_schemas():
    """
    Run a SQL query against Snowflake and return the results
    as JSON for the dropdown to consume. Optionally filters by
    a 'search' query string parameter, e.g. /api/schemas?search=Shriners
    """
    search_term = request.args.get("search", "").strip()

    query = """
        SELECT DISTINCT PROJECT FROM TCAT_CENTRAL.PUBLIC.RUNS WHERE ACTIVITY = 'S' 
    """
    params = ()
    if search_term:
        # %s is a placeholder filled in safely by the connector (prevents SQL injection).
        # Uppercasing here since the example schema (SHRINERS%) is upper-case; adjust
        # or drop .upper() if your schema names use mixed case.
        query += " AND PROJECT LIKE ?"
        params = (f"{search_term.upper()}%",)

    query += " ORDER BY PROJECT;"

    try:
        conn = get_snowflake_connection()
        cur = conn.cursor()
        cur.execute(query, params)
        rows = [row[0] for row in cur.fetchall()]
        cur.close()
        return jsonify(rows)
    except Exception as e:
        # Log the real error server-side; return a generic message to the client
        app.logger.error(f"Snowflake query failed: {e}")
        return jsonify({"error": "Failed to load schemas"}), 500


@app.route("/api/tables", methods=["GET"])
def get_tables():
    """
    Given a schema prefix (from the dropdown selection), return the
    distinct suffix codes (e.g. M001, M002) for schemas under that
    prefix that have a matching %S540_SEGMENTED table.
    e.g. /api/tables?schema=SHRINERS_DAF
    """
    schema = request.args.get("schema", "").strip()
    print(schema)
    if not schema:
        return jsonify({"error": "Missing schema parameter"}), 400

    query = """
        SELECT 'S' || SHORT_NAME AS SCORING FROM TCAT_CENTRAL.PUBLIC.RUNS WHERE ACTIVITY = 'S' AND PROJECT = ? ORDER BY SCORING;
    """
    params = (f"{schema.upper()}",)

    try:
        conn = get_snowflake_connection()
        cur = conn.cursor()
        cur.execute(query, params)
        rows = [row[0] for row in cur.fetchall()]
        cur.close()
        return jsonify(rows)
    except Exception as e:
        app.logger.error(f"Snowflake query failed: {e}")
        return jsonify({"error": "Failed to load tables"}), 500


@app.route("/api/items", methods=["GET"])
def get_items():
    """Return all items as JSON."""
    return jsonify(items)


@app.route("/api/items", methods=["POST"])
def add_item():
    """Add a new item from the GUI."""
    data = request.get_json()
    text = (data or {}).get("text", "").strip()
    if not text:
        return jsonify({"error": "Text cannot be empty"}), 400
    items.append(text)
    return jsonify({"items": items}), 201


@app.route("/api/items/<int:index>", methods=["DELETE"])
def delete_item(index):
    """Delete an item by its index."""
    if 0 <= index < len(items):
        items.pop(index)
        return jsonify({"items": items}), 200
    return jsonify({"error": "Invalid index"}), 404


@app.route("/api/run_analysis", methods=["POST"])
def run_analysis():
    """
    Given a list of fully-qualified table names, run the pairwise
    MODEL_SEGMENT overlap query for every combination, build the master
    dataframe, and generate a heatmap PDF (one page per pair).
    """
    data = request.get_json()
    tables = (data or {}).get("tables", [])

    print(data)
    print(tables)

    if len(tables) < 2:
        return jsonify({"error": "Select at least two tables to compare."}), 400

    try:
        conn = get_snowflake_connection()
        master_df = build_master_dataframe(tables, conn)
        print(master_df)

        if master_df.empty:
            return jsonify({"error": "No overlapping data found for the selected tables."}), 400

        filename = f"pid_counts_{uuid.uuid4().hex[:8]}.pdf"
        output_path = os.path.join(OUTPUT_DIR, filename)
        generate_heatmaps_pdf(master_df, output_path)

        pair_count = master_df["PAIR"].nunique()
        return jsonify({"pdf_url": f"/download/{filename}", "pair_count": pair_count})
    except Exception as e:
        app.logger.error(f"Analysis failed: {e}")
        return jsonify({"error": "Analysis failed. Check the server console for details."}), 500


@app.route("/download/<path:filename>")
def download_file(filename):
    """Serve a generated analysis PDF for download."""
    return send_from_directory(OUTPUT_DIR, filename, as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True)
