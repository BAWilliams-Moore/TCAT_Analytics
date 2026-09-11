# My Python Web App

A minimal Flask web app with a simple browser-based GUI: an input box to add items and a list with delete buttons.

## Structure
```
webapp/
├── app.py                 # Flask server + routes
├── requirements.txt       # Python dependencies
├── templates/
│   └── index.html         # Main page (Jinja2 template)
└── static/
    ├── css/style.css      # Styling
    └── js/main.js         # Frontend logic (fetch calls to the API)
```

## Setup

1. (Optional) Create a virtual environment:
   ```
   python3 -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Run the app:
   ```
   python app.py
   ```

4. Open your browser to `http://127.0.0.1:5000`

## Notes
- Data is stored in memory (`items` list in `app.py`) and resets when the server restarts. Swap in SQLite/SQLAlchemy for persistence.
- `app.py` exposes a small JSON API (`/api/items`) that the frontend JS calls — you can build on this for more complex features.
- Debug mode is on by default (`debug=True`); turn it off for production, and use a proper WSGI server like Gunicorn.
