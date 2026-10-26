import json
import os
import sqlite3
from flask import Flask, jsonify, request, send_from_directory

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.environ.get("DB_PATH", "/app/data/tracker.db")
CONTAINER_STATIC = "/app/static"
LOCAL_STATIC = os.path.join(BASE_DIR, "frontend")
STATIC_DIR = os.environ.get("STATIC_DIR") or (CONTAINER_STATIC if os.path.isdir(CONTAINER_STATIC) else LOCAL_STATIC)

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="/static")


def get_db():
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


SCHEMA = """
CREATE TABLE IF NOT EXISTS persons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS episodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    season INTEGER NOT NULL,
    number INTEGER NOT NULL,
    title TEXT NOT NULL,
    title_en TEXT NOT NULL DEFAULT '',
    "references" TEXT NOT NULL DEFAULT '',
    UNIQUE (season, number)
);
CREATE TABLE IF NOT EXISTS scores (
    person_id INTEGER NOT NULL,
    episode_id INTEGER NOT NULL,
    value INTEGER NOT NULL CHECK (value BETWEEN 1 AND 10),
    PRIMARY KEY (person_id, episode_id),
    FOREIGN KEY (person_id) REFERENCES persons(id) ON DELETE CASCADE,
    FOREIGN KEY (episode_id) REFERENCES episodes(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS person_references (
    person_id INTEGER NOT NULL,
    episode_id INTEGER NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (person_id, episode_id),
    FOREIGN KEY (person_id) REFERENCES persons(id) ON DELETE CASCADE,
    FOREIGN KEY (episode_id) REFERENCES episodes(id) ON DELETE CASCADE
);
"""


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    db = get_db()
    db.executescript(SCHEMA)
    db.commit()
    # Idempotente: agrega solo los episodios de la semilla que falten.
    # Al actualizar la app se suman temporadas nuevas sin borrar personas,
    # puntuaciones ni referencias existentes.
    seed_episodes(db)
    db.close()


def seed_episodes(db):
    seed_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "episodes_seed.json")
    with open(seed_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Migración idempotente: bases creadas antes de existir title_en.
    columns = [row[1] for row in db.execute("PRAGMA table_info(episodes)")]
    if "title_en" not in columns:
        db.execute("ALTER TABLE episodes ADD COLUMN title_en TEXT NOT NULL DEFAULT ''")

    for season in data.get("seasons", []):
        for ep in season.get("episodes", []):
            season_no = int(season["number"])
            number = int(ep["number"])
            title = (ep.get("title") or "").strip()
            title_en = (ep.get("title_en") or "").strip()
            refs = ep.get("references") or ""
            db.execute(
                'INSERT OR IGNORE INTO episodes (season, number, title, title_en, "references") '
                "VALUES (?, ?, ?, ?, ?)",
                (season_no, number, title, title_en, refs),
            )
            # Actualiza títulos (ahora en español) y refresca las sinopsis que
            # vienen de la semilla. Respeta sinopsis editadas a mano y
            # referencias personales (que viven en otra tabla).
            db.execute(
                'UPDATE episodes SET title = ?, title_en = ?, '
                '"references" = CASE '
                'WHEN COALESCE("references", \'\') = \'\' THEN ? '
                'WHEN title_en = ? THEN ? '
                'ELSE "references" END '
                'WHERE season = ? AND number = ?',
                (title, title_en, refs, title_en, refs, season_no, number),
            )
    db.commit()


init_db()


@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.get("/api/persons")
def api_persons():
    db = get_db()
    persons = [
        {"id": r["id"], "name": r["name"]}
        for r in db.execute("SELECT id, name FROM persons ORDER BY id")
    ]
    db.close()
    return jsonify(persons)


@app.post("/api/persons")
def api_person_create():
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    if not name:
        return jsonify({"error": "El nombre es obligatorio"}), 400
    db = get_db()
    try:
        cur = db.execute("INSERT INTO persons (name) VALUES (?)", (name,))
        db.commit()
        person = {"id": cur.lastrowid, "name": name}
    except sqlite3.IntegrityError:
        db.close()
        return jsonify({"error": "Ya existe una persona con ese nombre"}), 409
    db.close()
    return jsonify(person), 201


@app.delete("/api/persons/<int:pid>")
def api_person_delete(pid):
    db = get_db()
    db.execute("DELETE FROM persons WHERE id = ?", (pid,))
    db.commit()
    db.close()
    return jsonify({"ok": True})


@app.get("/api/seasons")
def api_seasons():
    db = get_db()
    seasons = [
        {"number": r["number"], "episode_count": r["count"]}
        for r in db.execute(
            "SELECT season AS number, COUNT(*) AS count FROM episodes GROUP BY season ORDER BY season"
        )
    ]
    db.close()
    return jsonify(seasons)


@app.get("/api/seasons/<int:number>/episodes")
def api_season_episodes(number):
    db = get_db()
    episodes = [
        dict(r)
        for r in db.execute(
            "SELECT id, season, number, title, \"references\" FROM episodes WHERE season = ? ORDER BY number",
            (number,),
        )
    ]
    scores = {}
    for r in db.execute(
        """SELECT e.season, e.number, s.person_id, s.value
           FROM scores s JOIN episodes e ON e.id = s.episode_id
           WHERE e.season = ?""",
        (number,),
    ):
        scores.setdefault((r["season"], r["number"]), {})[r["person_id"]] = r["value"]
    refs = {}
    for r in db.execute(
        """SELECT e.season, e.number, pr.person_id, pr.body
           FROM person_references pr JOIN episodes e ON e.id = pr.episode_id
           WHERE e.season = ?""",
        (number,),
    ):
        refs.setdefault((r["season"], r["number"]), {})[r["person_id"]] = r["body"]
    persons = [
        {"id": r["id"], "name": r["name"]}
        for r in db.execute("SELECT id, name FROM persons ORDER BY id")
    ]
    db.close()
    out = []
    for e in episodes:
        out.append({
            "id": e["id"],
            "season": e["season"],
            "number": e["number"],
            "title": e["title"],
            "references": e["references"],
            "refs": refs.get((e["season"], e["number"]), {}),
            "scores": scores.get((e["season"], e["number"]), {}),
        })
    return jsonify({"season": number, "episodes": out, "persons": persons})


@app.post("/api/episodes")
def api_episode_upsert():
    body = request.get_json(silent=True) or {}
    season = int(body.get("season") or 0)
    number = int(body.get("number") or 0)
    title = body.get("title") or ""
    references = body.get("references") or ""
    db = get_db()
    db.execute(
        """INSERT INTO episodes (season, number, title, \"references\") VALUES (?, ?, ?, ?)
           ON CONFLICT(season, number) DO UPDATE SET title = excluded.title, \"references\" = excluded.\"references\"""",
        (season, number, title, references),
    )
    db.commit()
    db.close()
    return jsonify({"ok": True})


@app.post("/api/references")
def api_reference_save():
    body = request.get_json(silent=True) or {}
    pid = _get_pid(body.get("person_id"))
    season = _get_pid(body.get("season"))
    number = _get_pid(body.get("number"))
    text = (body.get("references") or "").strip()
    if not pid or not season or not number:
        return jsonify({"error": "Faltan datos de persona o episodio"}), 400
    db = get_db()
    ep = db.execute("SELECT id FROM episodes WHERE season = ? AND number = ?", (season, number)).fetchone()
    if not ep:
        db.close()
        return jsonify({"error": "Episodio no encontrado"}), 404
    person = db.execute("SELECT id FROM persons WHERE id = ?", (pid,)).fetchone()
    if not person:
        db.close()
        return jsonify({"error": "Persona no encontrada"}), 404
    if text:
        db.execute(
            """INSERT INTO person_references (person_id, episode_id, body) VALUES (?, ?, ?)
               ON CONFLICT(person_id, episode_id) DO UPDATE SET body = excluded.body""",
            (pid, ep["id"], text),
        )
    else:
        db.execute(
            "DELETE FROM person_references WHERE person_id = ? AND episode_id = ?",
            (pid, ep["id"]),
        )
    db.commit()
    db.close()
    return jsonify({"ok": True})


@app.post("/api/scores")
def api_score_save():
    body = request.get_json(silent=True) or {}
    pid = int(body.get("person_id") or 0)
    season = int(body.get("season") or 0)
    number = int(body.get("episode_number") or 0)
    value = body.get("value")
    if value is None:
        return jsonify({"error": "El valor es obligatorio"}), 400
    value = int(value)
    if not 1 <= value <= 10:
        return jsonify({"error": "La puntuacion debe estar entre 1 y 10"}), 400
    db = get_db()
    ep = db.execute("SELECT id FROM episodes WHERE season = ? AND number = ?", (season, number)).fetchone()
    if not ep:
        db.close()
        return jsonify({"error": "Episodio no encontrado"}), 404
    db.execute(
        """INSERT INTO scores (person_id, episode_id, value) VALUES (?, ?, ?)
           ON CONFLICT(person_id, episode_id) DO UPDATE SET value = excluded.value""",
        (pid, ep["id"], value),
    )
    db.commit()
    db.close()
    return jsonify({"ok": True})


@app.delete("/api/scores")
def api_score_delete():
    q = request.args
    pid = int(q.get("person_id") or 0)
    season = int(q.get("season") or 0)
    number = int(q.get("episode_number") or 0)
    db = get_db()
    ep = db.execute("SELECT id FROM episodes WHERE season = ? AND number = ?", (season, number)).fetchone()
    if ep:
        db.execute("DELETE FROM scores WHERE person_id = ? AND episode_id = ?", (pid, ep["id"]))
        db.commit()
    db.close()
    return jsonify({"ok": True})


def _get_pid(value, default: int = 0) -> int:
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


@app.get("/api/averages")
def api_averages():
    pa = _get_pid(request.args.get("person_a"))
    pb = _get_pid(request.args.get("person_b"))
    seasons_filter = request.args.getlist("season")
    db = get_db()
    if seasons_filter:
        placeholders = ",".join("?" for _ in seasons_filter)
        rows = db.execute(
            f"""SELECT e.season, e.number, e.title, e."references", s1.value AS v1, s2.value AS v2
                FROM episodes e
                LEFT JOIN scores s1 ON s1.episode_id = e.id AND s1.person_id = ?
                LEFT JOIN scores s2 ON s2.episode_id = e.id AND s2.person_id = ?
                WHERE e.season IN ({placeholders}) ORDER BY e.season, e.number""",
            [pa, pb] + [int(s) for s in seasons_filter],
        ).fetchall()
    else:
        rows = db.execute(
            """SELECT e.season, e.number, e.title, e."references", s1.value AS v1, s2.value AS v2
               FROM episodes e
               LEFT JOIN scores s1 ON s1.episode_id = e.id AND s1.person_id = ?
               LEFT JOIN scores s2 ON s2.episode_id = e.id AND s2.person_id = ?
               ORDER BY e.season, e.number""",
            [pa, pb],
        ).fetchall()
    refs = {}
    for r in db.execute(
        """SELECT e.season, e.number, pr.person_id, pr.body
           FROM person_references pr JOIN episodes e ON e.id = pr.episode_id
           WHERE pr.person_id IN (?, ?)""",
        (pa, pb),
    ):
        refs.setdefault((r["season"], r["number"]), {})[r["person_id"]] = r["body"]
    seasons = {}
    order = []
    for r in rows:
        s = r["season"]
        if s not in seasons:
            seasons[s] = {"number": s, "episodes": []}
            order.append(s)
        avg = None if (r["v1"] is None or r["v2"] is None) else round((r["v1"] + r["v2"]) / 2, 2)
        seasons[s]["episodes"].append({
            "id": None,
            "season": s,
            "number": r["number"],
            "title": r["title"],
            "references": r["references"],
            "refs": refs.get((s, r["number"]), {}),
            "scores": {pa: r["v1"], pb: r["v2"]},
            "average": avg,
        })
    db.close()
    return jsonify({"person_a": pa, "person_b": pb, "seasons": [seasons[s] for s in order]})


@app.get("/api/episodes/all")
def api_episodes_all():
    pid = _get_pid(request.args.get("person"))
    db = get_db()
    seasons_map = {}
    order = []
    refs = {}
    for r in db.execute(
        """SELECT e.season, e.number, pr.body
           FROM person_references pr JOIN episodes e ON e.id = pr.episode_id
           WHERE pr.person_id = ?""",
        (pid,),
    ):
        refs[(r["season"], r["number"])] = r["body"]
    rows = db.execute(
        """SELECT e.season, e.number, e.title, e."references", s.value AS value
           FROM episodes e
           LEFT JOIN scores s ON s.episode_id = e.id AND s.person_id = ?
           ORDER BY e.season, e.number""",
        (pid,),
    ).fetchall()
    for r in rows:
        s = r["season"]
        if s not in seasons_map:
            seasons_map[s] = {"number": s, "episodes": []}
            order.append(s)
        body = refs.get((s, r["number"]))
        seasons_map[s]["episodes"].append({
            "id": None,
            "season": s,
            "number": r["number"],
            "title": r["title"],
            "references": r["references"],
            "refs": {pid: body} if body is not None else {},
            "scores": {pid: r["value"]} if r["value"] is not None else {},
            "average": r["value"],
        })
    db.close()
    return jsonify({"person": pid, "seasons": [seasons_map[s] for s in order]})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
