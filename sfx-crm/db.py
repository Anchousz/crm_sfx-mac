# -*- coding: utf-8 -*-
"""Хранилище SFX CRM: каталог, комплекты, проекты, настройки (SQLite)."""
import json
import os
import sqlite3
from datetime import datetime

from paths import data_dir

DB_PATH = os.path.join(data_dir(), "crm.db")

DEFAULT_SETTINGS = {
    "company_name": "",
    "company_phone": "",
    "company_email": "",
    "company_extra": "",
}


def connect():
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA foreign_keys = ON")
    return con


def _columns(con, table):
    return {row[1] for row in con.execute(f"PRAGMA table_info({table})")}


def init_db():
    with connect() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS categories(
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            sort INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS items(
            id INTEGER PRIMARY KEY,
            category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            price REAL NOT NULL DEFAULT 0,
            sort INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS projects(
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            client TEXT NOT NULL DEFAULT '',
            days_json TEXT NOT NULL DEFAULT '[]',
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS presets(
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS preset_lines(
            id INTEGER PRIMARY KEY,
            preset_id INTEGER NOT NULL REFERENCES presets(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            qty REAL NOT NULL,
            unit TEXT NOT NULL DEFAULT 'шт',
            sort INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS settings(
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """)
        # миграции
        items_cols = _columns(con, "items")
        if "unit" not in items_cols:
            con.execute("ALTER TABLE items ADD COLUMN unit TEXT NOT NULL DEFAULT 'шт'")
        if "stock" not in items_cols:
            con.execute("ALTER TABLE items ADD COLUMN stock REAL")
        proj_cols = _columns(con, "projects")
        if "status" not in proj_cols:
            con.execute("ALTER TABLE projects ADD COLUMN status TEXT NOT NULL DEFAULT 'предварительная'")
        if "tax" not in proj_cols:
            con.execute("ALTER TABLE projects ADD COLUMN tax REAL NOT NULL DEFAULT 0")


def project_totals(days, tax_percent):
    positions = sum(l["price"] * l["qty"] for d in days for l in d["lines"] if not l.get("ot"))
    overtime = sum(l["price"] * l["qty"] for d in days for l in d["lines"] if l.get("ot"))
    before_tax = positions + overtime
    tax_amount = before_tax * (tax_percent or 0) / 100.0
    return {"positions": positions, "overtime": overtime,
            "before_tax": before_tax, "tax_amount": tax_amount,
            "final": before_tax + tax_amount}


def list_catalog():
    with connect() as con:
        cats = con.execute("SELECT id, name FROM categories ORDER BY sort, id").fetchall()
        result = []
        for cid, cname in cats:
            items = con.execute(
                "SELECT id, name, price, unit, stock FROM items "
                "WHERE category_id=? ORDER BY sort, id", (cid,)).fetchall()
            result.append((cid, cname, items))
        return result


def add_category(name):
    with connect() as con:
        cur = con.execute(
            "INSERT INTO categories(name, sort) VALUES(?, "
            "(SELECT COALESCE(MAX(sort),0)+1 FROM categories))", (name,))
        return cur.lastrowid


def list_categories():
    with connect() as con:
        return con.execute(
            "SELECT id, name FROM categories ORDER BY sort, id").fetchall()


def find_or_create_category(name):
    """id категории по имени (без учёта регистра); создаёт, если такой нет.

    Сравниваем в Python: lower() в SQLite умеет только латиницу.
    """
    name = name.strip()
    key = name.casefold()
    for cid, cname in list_categories():
        if cname.strip().casefold() == key:
            return cid
    return add_category(name)


def rename_category(category_id, name):
    with connect() as con:
        con.execute("UPDATE categories SET name=? WHERE id=?", (name.strip(), category_id))


def delete_category(category_id):
    with connect() as con:
        con.execute("DELETE FROM categories WHERE id=?", (category_id,))


def category_item_count(category_id):
    with connect() as con:
        return con.execute("SELECT COUNT(*) FROM items WHERE category_id=?",
                           (category_id,)).fetchone()[0]


def item_exists(category_id, name, exclude_id=None):
    """Есть ли в категории позиция с таким именем (регистр не важен)."""
    key = name.strip().casefold()
    with connect() as con:
        rows = con.execute("SELECT id, name FROM items WHERE category_id=?",
                           (category_id,)).fetchall()
    return any(iid != exclude_id and iname.strip().casefold() == key
               for iid, iname in rows)


def get_item(item_id):
    with connect() as con:
        row = con.execute(
            "SELECT i.name, i.price, i.unit, i.stock, c.name "
            "FROM items i JOIN categories c ON c.id=i.category_id "
            "WHERE i.id=?", (item_id,)).fetchone()
    if not row:
        return None
    return {"name": row[0], "price": row[1], "unit": row[2],
            "stock": row[3], "category": row[4]}


def add_item(category_id, name, price, unit="шт", stock=None):
    with connect() as con:
        cur = con.execute(
            "INSERT INTO items(category_id, name, price, unit, stock, sort) "
            "VALUES(?,?,?,?,?, (SELECT COALESCE(MAX(sort),0)+1 FROM items "
            "WHERE category_id=?))",
            (category_id, name, price, unit, stock, category_id))
        return cur.lastrowid


def update_item(item_id, **fields):
    allowed = {"name", "price", "unit", "stock", "category_id"}
    sets = {k: v for k, v in fields.items() if k in allowed}
    if not sets:
        return
    with connect() as con:
        cols = ", ".join(f"{k}=?" for k in sets)
        con.execute(f"UPDATE items SET {cols} WHERE id=?", (*sets.values(), item_id))


def delete_item(item_id):
    with connect() as con:
        con.execute("DELETE FROM items WHERE id=?", (item_id,))


def clear_catalog():
    with connect() as con:
        con.execute("DELETE FROM items")
        con.execute("DELETE FROM categories")


def stock_map():
    with connect() as con:
        rows = con.execute("SELECT name, stock, unit FROM items WHERE stock IS NOT NULL").fetchall()
    return {name.strip(): (stock, unit) for name, stock, unit in rows}


def unit_map():
    with connect() as con:
        rows = con.execute("SELECT name, unit FROM items").fetchall()
    return {name.strip(): unit for name, unit in rows}


def list_presets():
    with connect() as con:
        rows = con.execute("SELECT id, name FROM presets ORDER BY name").fetchall()
        result = []
        for pid, name in rows:
            lines = [{"name": n, "price": p, "qty": q, "unit": u}
                     for n, p, q, u in con.execute(
                         "SELECT name, price, qty, unit FROM preset_lines "
                         "WHERE preset_id=? ORDER BY sort, id", (pid,))]
            total = sum(l["price"] * l["qty"] for l in lines)
            result.append({"id": pid, "name": name, "lines": lines, "total": total})
        return result


def save_preset(name, lines):
    with connect() as con:
        cur = con.execute("INSERT INTO presets(name) VALUES(?)", (name,))
        pid = cur.lastrowid
        for i, l in enumerate(lines):
            con.execute(
                "INSERT INTO preset_lines(preset_id, name, price, qty, unit, sort) "
                "VALUES(?,?,?,?,?,?)",
                (pid, l["name"], l["price"], l["qty"], l.get("unit", "шт"), i))
        return pid


def delete_preset(preset_id):
    with connect() as con:
        con.execute("DELETE FROM presets WHERE id=?", (preset_id,))


def save_project(name, client, days, status="предварительная", tax=0.0, project_id=None):
    payload = json.dumps(days, ensure_ascii=False)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    with connect() as con:
        if project_id:
            con.execute(
                "UPDATE projects SET name=?, client=?, days_json=?, status=?, "
                "tax=?, updated_at=? WHERE id=?",
                (name, client, payload, status, tax, now, project_id))
            return project_id
        cur = con.execute(
            "INSERT INTO projects(name, client, days_json, status, tax, updated_at) "
            "VALUES(?,?,?,?,?,?)", (name, client, payload, status, tax, now))
        return cur.lastrowid


def list_projects():
    with connect() as con:
        rows = con.execute(
            "SELECT id, name, client, days_json, status, tax, updated_at "
            "FROM projects ORDER BY updated_at DESC").fetchall()
    result = []
    for pid, name, client, days_json, status, tax, updated in rows:
        days = json.loads(days_json)
        totals = project_totals(days, tax)
        result.append({"id": pid, "name": name, "client": client,
                       "status": status, "tax": tax, "updated": updated,
                       "days": days, "totals": totals})
    return result


def load_project(project_id):
    with connect() as con:
        row = con.execute(
            "SELECT id, name, client, days_json, status, tax FROM projects "
            "WHERE id=?", (project_id,)).fetchone()
    if not row:
        return None
    return {"id": row[0], "name": row[1], "client": row[2],
            "days": json.loads(row[3]), "status": row[4], "tax": row[5]}


def delete_project(project_id):
    with connect() as con:
        con.execute("DELETE FROM projects WHERE id=?", (project_id,))


def usage_by_date(exclude_project_id=None):
    from excel_io import parse_date
    usage = {}
    with connect() as con:
        rows = con.execute("SELECT id, name, days_json FROM projects").fetchall()
    for pid, pname, days_json in rows:
        if exclude_project_id and pid == exclude_project_id:
            continue
        for day in json.loads(days_json):
            d = parse_date(day["label"])
            if not d:
                continue
            key = d.date().isoformat()
            for l in day["lines"]:
                if l.get("ot"):
                    continue
                usage.setdefault(key, []).append((l["name"].strip(), l["qty"], pname))
    return usage


def get_settings():
    result = dict(DEFAULT_SETTINGS)
    with connect() as con:
        for k, v in con.execute("SELECT key, value FROM settings"):
            result[k] = v
    return result


def set_setting(key, value):
    with connect() as con:
        con.execute(
            "INSERT INTO settings(key, value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))