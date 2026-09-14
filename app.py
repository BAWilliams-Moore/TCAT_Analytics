import os
import re
import traceback
import uuid
from decimal import Decimal
import pandas as pd
import matplotlib


matplotlib.use("Agg")  # headless backend — no display available on the server
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import seaborn as sns
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, send_from_directory

try:
    import pyodbc
except ImportError:
    pyodbc = None

# Load credentials from a local .env file (see .env.example for the format).
# This keeps secrets out of the source code and out of shared environment variables.
load_dotenv()

app = Flask(__name__)

# In-memory data store (replace with a database for real use)
items = []
feature_items = []

# Where generated analysis PDFs get saved so they can be downloaded
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generated")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Holds the DSN name / username entered in the GUI's connection form,
# so get_snowflake_connection() knows what to use.
_connection_config = {"dsn": None, "username": None}

_cached_conn = None
TABLE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*){2}$")


def extract_abbr(fully_qualified_name):
    """
    Pull a short label out of a fully-qualified table name for use in
    pair labels, e.g. 'TCAT_PROD_2.SHRINERS_DAF__S001.S540_SEGMENTED' -> 'S001'
    """
    parts = fully_qualified_name.split(".")
    schema_part = parts[1] if len(parts) > 1 else fully_qualified_name
    return fully_qualified_name.split(".")[1]
    # return schema_part.split("__")[-1] if "__" in schema_part else schema_part


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

    if pyodbc is None:
        raise RuntimeError("pyodbc is not available. Install the Snowflake ODBC driver.")

    dsn_name = _connection_config["dsn"] or os.environ.get("SNOWFLAKE_DSN", "Snowflake_SSO")
    username = _connection_config["username"] or os.environ.get("SNOWFLAKE_USER")

    conn_str = f"DSN={dsn_name}"
    if username:
        conn_str += f";UID={username}"

    _cached_conn = pyodbc.connect(conn_str, autocommit=True)
    return _cached_conn


def _nav_status():
    dsn = _connection_config["dsn"] or os.environ.get("SNOWFLAKE_DSN", "")
    username = _connection_config["username"] or os.environ.get("SNOWFLAKE_USER", "")
    connected = bool(_cached_conn)
    return {
        "connected": connected,
        "dsn": dsn,
        "username": username or "",
        "mode": "Snowflake connected" if connected else "Not connected",
    }


@app.context_processor
def inject_nav():
    status = _nav_status()
    return {
        "snowflake_connected": bool(_cached_conn),
        "nav_status": status,
    }


def _page(active):
    status = _nav_status()
    form = {
        "dsn": status["dsn"] or os.environ.get("SNOWFLAKE_DSN", "Snowflake_SSO"),
        "username": status["username"],
    }
    return render_template(
        "index.html",
        active=active,
        items=items,
        feature_items=feature_items,
        form=form,
        status=status,
        nav_status=status,
    )


@app.route("/")
def index():
    return _page("connection")


@app.route("/connection")
def connection():
    return _page("connection")


@app.route("/comparison")
def comparison():
    return _page("comparison")


@app.route("/features")
def features():
    return _page("features")


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


@app.route("/api/disconnect", methods=["POST"])
def disconnect():
    global _cached_conn
    if _cached_conn is not None:
        try:
            _cached_conn.close()
        except Exception:
            pass
        _cached_conn = None
    return jsonify({"connected": False})


@app.route("/api/status", methods=["GET"])
def status():
    return jsonify(_nav_status())


@app.route("/api/schemas", methods=["GET"])
def get_schemas():
    """
    Run a SQL query against Snowflake and return the results
    as JSON for the dropdown to consume. Optionally filters by
    a 'search' query string parameter, e.g. /api/schemas?search=Shriners
    """
    search_term = request.args.get("search", "").strip()
    activity = request.args.get("activity", "S").strip().upper() or "S"
    if activity not in ("S", "M"):
        activity = "S"

    query = """
        SELECT DISTINCT PROJECT FROM TCAT_CENTRAL.PUBLIC.RUNS WHERE ACTIVITY = ?
    """
    params = [activity]
    if search_term:
        # Placeholder filled in safely by the connector (prevents SQL injection).
        query += " AND UPPER(PROJECT) LIKE ?"
        params.append(f"%{search_term.upper()}%")

    query += " ORDER BY PROJECT;"
    params = tuple(params)

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
        SELECT
            SHORT_NAME,
            ACTIVITY || SHORT_NAME AS SCORING,
            DATABASE || '.' || PROJECT || '__' || ACTIVITY || SHORT_NAME || '.' || 'S540_SEGMENTED' AS SEGMENTED_TABLE
        FROM TCAT_CENTRAL.PUBLIC.RUNS
        WHERE PROJECT = ? AND ACTIVITY = 'S'
        ORDER BY SCORING
    """
    params = (schema.upper(),)

    try:
        conn = get_snowflake_connection()
        cur = conn.cursor()
        cur.execute(query, params)
        rows = [
            {
                "short_name": row[0],
                "scoring": row[1],
                "segmented_table": row[2],
            }
            for row in cur.fetchall()
        ]
        cur.close()
        return jsonify(rows)
    except Exception as e:
        app.logger.error(f"Snowflake query failed: {e}")
        return jsonify({"error": "Failed to load tables"}), 500


@app.route("/api/segmented_table", methods=["GET"])
def get_segmented_table():
    """
    PROJECT comes from #schema-select. SHORT_NAME comes from the selected
    #table-select option. ACTIVITY is scoring ('S').
    """
    project = request.args.get("project", "").strip()
    short_name = request.args.get("short_name", "").strip()
    if not project or not short_name:
        return jsonify({"error": "project and short_name are required."}), 400

    query = """
        SELECT DATABASE || '.' || PROJECT || '__' || ACTIVITY || SHORT_NAME || '.' || 'S540_SEGMENTED' AS SEGMENTED_TABLE
        FROM TCAT_CENTRAL.PUBLIC.RUNS
        WHERE PROJECT = ? AND ACTIVITY = 'S' AND SHORT_NAME = ?
    """
    try:
        conn = get_snowflake_connection()
        cur = conn.cursor()
        cur.execute(query, (project.upper(), short_name))
        row = cur.fetchone()
        cur.close()
        if not row or not row[0]:
            return jsonify({"error": "No segmented table for that project and short_name."}), 404
        return jsonify({"segmented_table": row[0]})
    except Exception as e:
        app.logger.error(f"Snowflake query failed: {e}")
        return jsonify({"error": "Failed to resolve segmented table"}), 500


@app.route("/api/models", methods=["GET"])
def get_models():
    """
    Like /api/tables, but ACTIVITY = 'M' and FEATURE_METRICS tables.
    PROJECT comes from #feature-schema-select.
    """
    schema = request.args.get("schema", "").strip()
    if not schema:
        return jsonify({"error": "Missing schema parameter"}), 400

    query = """
        SELECT
            SHORT_NAME,
            ACTIVITY || SHORT_NAME AS MODELING,
            DATABASE || '.' || PROJECT || '__' || ACTIVITY || SHORT_NAME || '.' || 'FEATURE_METRICS' AS SEGMENTED_TABLE
        FROM TCAT_CENTRAL.PUBLIC.RUNS
        WHERE PROJECT = ? AND ACTIVITY = 'M'
        ORDER BY MODELING
    """
    try:
        conn = get_snowflake_connection()
        cur = conn.cursor()
        cur.execute(query, (schema.upper(),))
        rows = [
            {
                "short_name": row[0],
                "modeling": row[1],
                "segmented_table": row[2],
            }
            for row in cur.fetchall()
        ]
        cur.close()
        return jsonify(rows)
    except Exception as e:
        app.logger.error(f"Snowflake query failed: {e}")
        return jsonify({"error": "Failed to load models"}), 500


@app.route("/api/feature_table", methods=["GET"])
def get_feature_table():
    """
    PROJECT comes from #feature-schema-select. SHORT_NAME comes from
    #model-table-select. ACTIVITY is modeling ('M').
    """
    project = request.args.get("project", "").strip()
    short_name = request.args.get("short_name", "").strip()
    if not project or not short_name:
        return jsonify({"error": "project and short_name are required."}), 400

    query = """
        SELECT DATABASE || '.' || PROJECT || '__' || ACTIVITY || SHORT_NAME || '.' || 'FEATURE_METRICS' AS SEGMENTED_TABLE
        FROM TCAT_CENTRAL.PUBLIC.RUNS
        WHERE PROJECT = ? AND ACTIVITY = 'M' AND SHORT_NAME = ?
    """
    try:
        conn = get_snowflake_connection()
        cur = conn.cursor()
        cur.execute(query, (project.upper(), short_name))
        row = cur.fetchone()
        cur.close()
        if not row or not row[0]:
            return jsonify({"error": "No feature table for that project and short_name."}), 404
        return jsonify({"segmented_table": row[0]})
    except Exception as e:
        app.logger.error(f"Snowflake query failed: {e}")
        return jsonify({"error": "Failed to resolve feature table"}), 500


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
    if text not in items:
        items.append(text)
    return jsonify({"items": items}), 201


@app.route("/api/items/<int:index>", methods=["DELETE"])
def delete_item(index):
    """Delete an item by its index."""
    if 0 <= index < len(items):
        items.pop(index)
        return jsonify({"items": items}), 200
    return jsonify({"error": "Invalid index"}), 404


@app.route("/api/feature_items", methods=["GET"])
def get_feature_items():
    return jsonify(feature_items)


@app.route("/api/feature_items", methods=["POST"])
def add_feature_item():
    data = request.get_json()
    text = (data or {}).get("text", "").strip()
    if not text:
        return jsonify({"error": "Text cannot be empty"}), 400
    if text not in feature_items:
        feature_items.append(text)
    return jsonify({"items": feature_items}), 201


@app.route("/api/feature_items/<int:index>", methods=["DELETE"])
def delete_feature_item(index):
    if 0 <= index < len(feature_items):
        feature_items.pop(index)
        return jsonify({"items": feature_items}), 200
    return jsonify({"error": "Invalid index"}), 404


FEATURE_IMPORTANCE_QUERIES = (
    """
    SELECT NAME AS FEATURE, VALUE AS IMPORTANCE
    FROM {table} F
    LEFT JOIN TCAT_CENTRAL.FEATURE_HANDLING.FEATURES_BACKPOPULATION D ON F.NAME = D.FEATURE_NAME
    WHERE METRIC = 'IMPORTANCE'
    QUALIFY ROW_NUMBER() OVER (PARTITION BY NAME ORDER BY IMPORTANCE DESC) = 1
    ORDER BY IMPORTANCE DESC
    LIMIT 20
    """
)


def _is_plain_sequence(value):
    if isinstance(value, (str, bytes, bytearray, dict)):
        return False
    try:
        iter(value)
    except TypeError:
        return False
    return True


def normalize_odbc_row(row, expected_width):
    """Turn a pyodbc/Snowflake row into a flat Python list of scalars."""
    if row is None:
        return [None] * expected_width

    values = None
    if expected_width:
        try:
            values = [row[i] for i in range(expected_width)]
        except Exception:
            values = None
    if values is None:
        try:
            values = list(row)
        except TypeError:
            values = [row]

    if expected_width and len(values) == 1 and _is_plain_sequence(values[0]):
        inner = list(values[0])
        if len(inner) == expected_width:
            values = inner

    if expected_width:
        if len(values) < expected_width:
            values = list(values) + [None] * (expected_width - len(values))
        return list(values[:expected_width])
    return list(values)


def dataframe_from_odbc_rows(rows, description):
    """
    Build a DataFrame from pyodbc/Snowflake rows without the
    "Shape of passed values is (20, 1), indices imply (20, 2)" error.
    """
    columns = [str(col[0]).strip().strip('"') for col in (description or [])]
    width = len(columns)
    records = [normalize_odbc_row(row, width) for row in rows]
    if not records:
        return pd.DataFrame(columns=[col.upper() for col in columns] or ["FEATURE", "IMPORTANCE"])

    # Infer shape from values first so pandas never gets a columns= mismatch.
    df = pd.DataFrame(records)
    if width and df.shape[1] == 1 and width > 1:
        unpacked = pd.DataFrame(df.iloc[:, 0].tolist())
        if unpacked.shape[1] == width:
            df = unpacked
    if df.shape[1] == 0:
        return pd.DataFrame(columns=[col.upper() for col in columns] or ["FEATURE", "IMPORTANCE"])

    names = columns[: df.shape[1]] if columns else []
    while len(names) < df.shape[1]:
        names.append(f"COL_{len(names)}")
    df.columns = [str(col).upper() for col in names]
    return df


def _normalize_feature_frame(df, table):
    df = df.copy()
    df.columns = [str(col).upper() for col in df.columns]
    if "FEATURE" not in df.columns or "IMPORTANCE" not in df.columns:
        raise ValueError(f"Unexpected columns from {table}: {list(df.columns)}")
    out = df[["FEATURE", "IMPORTANCE"]].copy()
    out["FEATURE"] = out["FEATURE"].map(lambda value: None if value is None else str(value))
    out["IMPORTANCE"] = pd.to_numeric(out["IMPORTANCE"], errors="coerce")
    return out.dropna(subset=["FEATURE"]).reset_index(drop=True)


def fetch_feature_importance(conn, table):
    """Top 20 IMPORTANCE rows for one FEATURE_METRICS table (notebook query)."""
    if not TABLE_NAME.match(table):
        raise ValueError(f"Invalid table name: {table}")

    errors = []
    
    query = FEATURE_IMPORTANCE_QUERIES.format(table=table)
    cursor = conn.cursor()
    try:
        cursor.execute(query)
        description = cursor.description
        rows = cursor.fetchall()
        df = dataframe_from_odbc_rows(rows, description)
        print(df)
        return _normalize_feature_frame(df, table)
    except Exception as exc:
        errors.append(str(exc))
        app.logger.warning(f"Feature query failed for {table}: {exc}")
    finally:
        try:
            cursor.close()
        except Exception:
            pass

    raise RuntimeError(f"Could not read feature importance from {table}: {' | '.join(errors)}")


def assemble_feature_importance_table(model_frames):
    """
    Notebook merge: grow a unique feature_list in first-seen order, left-join
    each model's FEATURE/IMPORTANCE frame, then rename columns to
    ['FEATURE', model_label_1, model_label_2, ...].
    """
    feature_list = []
    model_list = ["FEATURE"]
    frames = []
    used_labels = {}

    for label, df in model_frames:
        if label in used_labels:
            used_labels[label] += 1
            label = f"{label}_{used_labels[label]}"
        else:
            used_labels[label] = 1

        for item in df["FEATURE"].tolist():
            if item not in feature_list:
                feature_list.append(item)

        model_list.append(label)
        piece = df[["FEATURE", "IMPORTANCE"]].copy()
        piece.columns = ["FEATURE", label]
        frames.append(piece)
        print(frames)

    master_df = pd.DataFrame({"FEATURE": feature_list})
    for frame in frames:
        master_df = pd.merge(master_df, frame, on="FEATURE", how="left")
        print(master_df)
    return master_df


def build_feature_importance_master(tables, conn):
    """
    For each selected model, run the FEATURE_METRICS query, append unseen
    features, then join the per-model dataframes into one comparison table.
    """
    model_frames = []
    for table in tables:
        df = fetch_feature_importance(conn, table)
        model_frames.append((extract_abbr(table), df))
    return assemble_feature_importance_table(model_frames)

def json_safe_value(value):
    """Convert a pandas/numpy/Decimal cell into something Flask can jsonify."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, Decimal):
        value = float(value)
    elif hasattr(value, "item") and not isinstance(value, (bytes, str)):
        try:
            value = value.item()
        except (ValueError, AttributeError):
            pass
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            return None
        return round(float(value), 6)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, str):
        return value
    return str(value)

def master_df_to_table_payload(master_df):
    """Turn the joined importance table into JSON columns/rows."""
    columns = [str(col) for col in master_df.columns]
    rows = []
    for record in master_df.itertuples(index=False, name=None):
        rows.append([json_safe_value(value) for value in record])
    return columns, rows


@app.route("/api/run_features", methods=["POST"])
def run_features():
    """
    Run the FEATURE_METRICS importance query for each selected model,
    append unique features, join the per-model frames, and return a table.
    """
    data = request.get_json()
    tables = (data or {}).get("tables", [])

    if len(tables) < 2:
        return jsonify({"error": "Select at least two model to compare."}), 400

    try:
        conn = get_snowflake_connection()
        master_df = build_feature_importance_master(tables, conn)
        if master_df.empty:
            return jsonify({"error": "No feature importance rows found for the selected models."}), 400

        filename = f"feature_importance_{uuid.uuid4().hex[:8]}.csv"
        output_path = os.path.join(OUTPUT_DIR, filename)
        master_df.to_csv(output_path, index=False, encoding="utf-8-sig")

        
        columns, rows = master_df_to_table_payload(master_df)

        return jsonify({
            "columns": columns,
            "rows": rows,
            "model_count": len(tables),
            "feature_count": int(len(master_df)),
            "csv_url": f"/download/{filename}",
        })
    except Exception as e:
        app.logger.error(f"Feature comparison failed: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Feature comparison failed: {e}"}), 500


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
        return jsonify({
            "pdf_url": f"/download/{filename}",
            "pair_count": pair_count,
        })
    except Exception as e:
        app.logger.error(f"Analysis failed: {e}")
        return jsonify({"error": "Analysis failed. Check the server console for details."}), 500


@app.route("/download/<path:filename>")
def download_file(filename):
    """Serve a generated analysis PDF or feature-importance CSV."""
    return send_from_directory(OUTPUT_DIR, filename, as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True)
