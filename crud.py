"""Generic, metadata-driven CRUD screens used by every entity page.

A page describes its table with a TableSpec (columns, display SQL, hooks) and calls
render_crud(spec).  The engine renders View / Add / Edit-Delete tabs, validates,
writes inside a single transaction and records every change in AUDIT_LOG.
"""
import datetime as dt
import re
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional

import streamlit as st

from db import friendly_error, log_action, query_all, query_df, query_one, to_date, transaction

MIN_DATE = dt.date(1990, 1, 1)
MAX_DATE = dt.date(2100, 12, 31)

VIEW_SECTION = "📋 View"

LETTER = r"[^\W\d_]"  # any Unicode letter
# rule name -> (regex, min length, max length, what the rule allows)
TEXT_RULES = {
    "person": (re.compile(rf"^{LETTER}+(?:[ .'-]+{LETTER}+)*\.?$"), 2, 100,
               "may contain only letters, spaces, dots, apostrophes and hyphens"),
    "title": (re.compile(rf"^(?=.*{LETTER})[^\W_][\w &(),.'/+%-]*$"), 2, 120,
              "must start with a letter or digit, include at least one letter, and may only use "
              "letters, digits, spaces and & ( ) , . ' / + % -"),
    "code": (re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9/-]*[A-Za-z0-9])?$"), 3, 40,
             "may contain only letters, digits, hyphens and slashes, and must start and end with a letter or digit"),
}


@dataclass
class Col:
    name: str
    label: Optional[str] = None
    kind: str = "text"  # text | textarea | int | float | date | select | fk
    required: bool = False
    options: Optional[list] = None  # for kind="select"
    fk_sql: Optional[str] = None  # for kind="fk": SELECT <id> AS id, <label> AS label ...
    default: Any = None
    help: Optional[str] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    disabled: bool = False
    rule: Optional[str] = None  # key of TEXT_RULES: person | title | code

    @property
    def title(self):
        text = self.label or self.name.replace("_", " ")
        return text + (" *" if self.required else "")


@dataclass
class TableSpec:
    table: str
    pk: str
    title: str
    columns: List[Col]
    view_sql: Optional[str] = None  # SELECT used for the View tab (joins for readable names)
    label_sql: Optional[str] = None  # SQL expression used to label records in the edit picker
    filters: List[str] = field(default_factory=list)  # view columns offered as multiselect filters
    validate: Optional[Callable] = None  # (values, mode, old, conn) -> list[str]
    prepare: Optional[Callable] = None  # (values, extra, mode, old) -> None; may add/alter values
    extra_form: Optional[Callable] = None  # (mode, record, values, key) -> dict
    validate_extra: Optional[Callable] = None  # (extra, mode) -> list[str]
    after_save: Optional[Callable] = None  # (conn, pk_value, values, extra, mode, old) -> None
    before_delete: Optional[Callable] = None  # (conn, record) -> error message or None
    extra_tabs: list = field(default_factory=list)  # [(tab title, render function)]
    tabs_first: bool = False  # put extra tabs before the CRUD tabs
    can_add: bool = True
    can_edit: bool = True
    can_delete: bool = True
    edit_where: str = ""  # e.g. "WHERE User_ID = ?" to restrict editable records
    edit_params: tuple = ()
    audit_maintenance: bool = False  # link audit rows to MAINTENANCE_ID
    add_label: str = "Add"


# ---------------------------------------------------------------------------
# Flash messages (survive st.rerun)
# ---------------------------------------------------------------------------
def flash(kind, message):
    st.session_state.setdefault("_flash", []).append((kind, message))


def show_flash():
    # Success/info become toasts so they don't push the page layout around.
    icons = {"success": "✅", "info": "ℹ️"}
    for kind, message in st.session_state.pop("_flash", []):
        if kind in icons:
            st.toast(message, icon=icons[kind])
        else:
            getattr(st, kind)(message)


SECTION_CSS = """
<style>
[class*="st-key-secnav_"] div[role="radiogroup"] { gap: 2px; border-bottom: 1px solid rgba(128,128,128,.25);
                                                   flex-wrap: wrap; }
[class*="st-key-secnav_"] div[role="radiogroup"] > label { margin: 0; padding: 7px 14px 8px;
    border-bottom: 2px solid transparent; border-radius: 8px 8px 0 0; cursor: pointer; }
[class*="st-key-secnav_"] div[role="radiogroup"] > label > div:first-child { display: none; }
[class*="st-key-secnav_"] div[role="radiogroup"] > label:hover { background: rgba(42,120,214,.06); }
[class*="st-key-secnav_"] div[role="radiogroup"] > label:has(input:checked) {
    border-bottom-color: #2a78d6; background: rgba(42,120,214,.09); }
[class*="st-key-secnav_"] div[role="radiogroup"] > label:has(input:checked) p { color: #1c5cab; font-weight: 600; }
</style>
"""


def section_switcher(key, options):
    """Tab-like selector whose choice survives reruns (st.tabs resets to the first tab on every rerun)."""
    if st.session_state.get(key) not in options:
        st.session_state[key] = options[0]
    st.markdown(SECTION_CSS, unsafe_allow_html=True)
    with st.container(key=f"secnav_{key}"):
        return st.radio("Section", options, key=key, horizontal=True, label_visibility="collapsed")


# ---------------------------------------------------------------------------
# Field widgets
# ---------------------------------------------------------------------------
def fk_options(sql, params=()):
    rows = query_all(sql, params)
    return [r["id"] for r in rows], {r["id"]: str(r["label"]) for r in rows}


def render_field(col: Col, value, key):
    """Render one input widget and return its (python) value."""
    help_text = col.help
    if value is None and col.default is not None:
        value = col.default() if callable(col.default) else col.default

    if col.kind == "fk":
        ids, labels = fk_options(col.fk_sql)
        if col.required and not ids:
            st.warning(f"No options available for {col.title.rstrip(' *')} — create one first.")
            return None
        opts = ids if col.required else [None] + ids
        # A required choice with no current value starts empty, forcing a deliberate pick.
        index = opts.index(value) if value in opts else (None if col.required else 0)
        return st.selectbox(col.title, opts, index=index, key=key, help=help_text, disabled=col.disabled,
                            placeholder="Select…",
                            format_func=lambda x: "—" if x is None else labels.get(x, str(x)))

    if col.kind == "select":
        opts = list(col.options) if col.required else [None] + list(col.options)
        if value not in opts and value is not None:
            opts.append(value)
        index = opts.index(value) if value in opts else (None if col.required else 0)
        return st.selectbox(col.title, opts, index=index, key=key, help=help_text, disabled=col.disabled,
                            placeholder="Select…", format_func=lambda x: "—" if x is None else str(x))

    if col.kind == "int":
        v = int(value) if value not in (None, "") else (None if not col.required else int(col.min_value or 0))
        return st.number_input(col.title, value=v, step=1, key=key, help=help_text, disabled=col.disabled,
                               min_value=None if col.min_value is None else int(col.min_value),
                               max_value=None if col.max_value is None else int(col.max_value))

    if col.kind == "float":
        v = float(value) if value not in (None, "") else (None if not col.required else float(col.min_value or 0))
        return st.number_input(col.title, value=v, step=1.0, format="%.2f", key=key, help=help_text,
                               disabled=col.disabled,
                               min_value=None if col.min_value is None else float(col.min_value),
                               max_value=None if col.max_value is None else float(col.max_value))

    if col.kind == "date":
        v = to_date(value)
        if v is None and col.required:
            v = dt.date.today()
        return st.date_input(col.title, value=v, min_value=MIN_DATE, max_value=MAX_DATE, key=key,
                             help=help_text, disabled=col.disabled, format="YYYY-MM-DD")

    if col.kind == "textarea":
        return st.text_area(col.title, value="" if value is None else str(value), key=key, help=help_text,
                            disabled=col.disabled, height=90)

    return st.text_input(col.title, value="" if value is None else str(value), key=key, help=help_text,
                         disabled=col.disabled)


def normalize(value):
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def render_fields(columns, record, key, ncols=2):
    """Render a grid of fields; returns {column: normalized value}."""
    values = {}
    grid = st.columns(ncols)
    for i, col in enumerate(columns):
        with grid[i % ncols]:
            values[col.name] = normalize(render_field(col, (record or {}).get(col.name), f"{key}_{col.name}"))
    return values


def required_errors(columns, values):
    return [f"{c.title.rstrip(' *')} is required." for c in columns
            if c.required and values.get(c.name) in (None, "")]


def rule_errors(columns, values):
    """Character / length checks for text fields that declare a rule."""
    errors = []
    for c in columns:
        value = values.get(c.name)
        if not c.rule or value in (None, ""):
            continue
        pattern, low, high, allowed = TEXT_RULES[c.rule]
        name = c.title.rstrip(" *")
        if not low <= len(value) <= high:
            errors.append(f"{name} must be {low}–{high} characters long.")
        elif not pattern.match(value):
            errors.append(f"{name} {allowed}.")
    return errors


# ---------------------------------------------------------------------------
# View tab
# ---------------------------------------------------------------------------
def render_table(df, key, filters=(), file_name="export.csv", search=True):
    """Filterable dataframe with CSV export. Returns the filtered frame."""
    if df.empty:
        st.info("No records yet.")
        return df
    fcols = [f for f in filters if f in df.columns]
    n = len(fcols) + (1 if search else 0)
    if n:
        boxes = st.columns(max(n, 1))
        i = 0
        if search:
            term = boxes[0].text_input("Search", key=f"{key}_search", placeholder="Type to filter any column…")
            if term:
                mask = df.astype(str).apply(lambda s: s.str.contains(term, case=False, na=False, regex=False))
                df = df[mask.any(axis=1)]
            i = 1
        for f in fcols:
            options = sorted(df[f].dropna().astype(str).unique().tolist())
            chosen = boxes[i].multiselect(f.replace("_", " "), options, key=f"{key}_f_{f}")
            if chosen:
                df = df[df[f].astype(str).isin(chosen)]
            i += 1
    st.dataframe(df, hide_index=True, width="stretch")
    left, right = st.columns([3, 1])
    left.caption(f"{len(df)} record(s)")
    right.download_button("⬇ Export CSV", df.to_csv(index=False).encode("utf-8"), file_name=file_name,
                          mime="text/csv", key=f"{key}_csv", width="stretch")
    return df


def _view_tab(spec):
    df = query_df(spec.view_sql or f"SELECT * FROM {spec.table} ORDER BY {spec.pk} DESC")
    render_table(df, f"{spec.table}_view", spec.filters, f"{spec.table.lower()}.csv")


# ---------------------------------------------------------------------------
# Add / Edit / Delete
# ---------------------------------------------------------------------------
def _summary(values, limit=4):
    parts = [f"{k}={v}" for k, v in values.items() if v not in (None, "") and k != "Password_Hash"]
    return ", ".join(parts[:limit])


def _save(spec, mode, values, extra, old=None):
    """Validate and persist; returns (ok, message)."""
    for c in spec.columns:
        if c.rule == "code" and values.get(c.name):
            values[c.name] = values[c.name].upper()
        elif c.rule and values.get(c.name):
            values[c.name] = " ".join(values[c.name].split())  # collapse repeated spaces
    errors = required_errors(spec.columns, values) + rule_errors(spec.columns, values)
    if spec.validate_extra:
        errors += spec.validate_extra(extra, mode) or []
    if errors:
        return False, errors
    try:
        with transaction() as conn:
            if spec.validate:
                errors = spec.validate(values, mode, old, conn) or []
                if errors:
                    return False, errors
            if spec.prepare:
                spec.prepare(values, extra, mode, old)
            if mode == "add":
                cols = list(values.keys())
                sql = (f"INSERT INTO {spec.table} ({', '.join(cols)}) "
                       f"VALUES ({', '.join('?' for _ in cols)})")
                pk_value = conn.execute(sql, [values[c] for c in cols]).lastrowid
                remarks = f"{spec.pk}={pk_value}: {_summary(values)}"
                action = f"CREATE {spec.table}"
            else:
                pk_value = old[spec.pk]
                cols = list(values.keys())
                sql = f"UPDATE {spec.table} SET {', '.join(c + ' = ?' for c in cols)} WHERE {spec.pk} = ?"
                conn.execute(sql, [values[c] for c in cols] + [pk_value])
                changes = [f"{c}: {old.get(c)} → {values[c]}" for c in cols
                           if c != "Password_Hash" and str(old.get(c)) != str(values[c])]
                if "Password_Hash" in values and values["Password_Hash"] != old.get("Password_Hash"):
                    changes.append("password changed")
                remarks = f"{spec.pk}={pk_value}: " + ("; ".join(changes) if changes else "no field changes")
                action = f"UPDATE {spec.table}"
            if spec.after_save:
                spec.after_save(conn, pk_value, values, extra, mode, old)
            log_action(action, remarks, conn=conn,
                       maintenance_id=pk_value if spec.audit_maintenance else None)
        return True, pk_value
    except Exception as exc:  # sqlite3 errors and trigger RAISE(ABORT)
        return False, [friendly_error(exc)]


def _add_tab(spec):
    counter = st.session_state.setdefault(f"{spec.table}_add_n", 0)
    key = f"{spec.table}_add_{counter}"
    values = render_fields(spec.columns, None, key)
    extra = spec.extra_form("add", None, values, key) if spec.extra_form else {}
    if st.button(f"💾 Save new record", key=f"{key}_save", type="primary"):
        ok, result = _save(spec, "add", values, extra)
        if ok:
            st.session_state[f"{spec.table}_add_n"] = counter + 1
            flash("success", f"Record #{result} created in {spec.table}.")
            st.rerun()
        for e in result:
            st.error(e)


def _edit_tab(spec):
    label_sql = spec.label_sql or spec.pk
    rows = query_all(f"SELECT {spec.pk} AS id, {label_sql} AS label FROM {spec.table} {spec.edit_where} "
                     f"ORDER BY {spec.pk} DESC", spec.edit_params)
    if not rows:
        st.info("No records available to edit.")
        return
    labels = {r["id"]: f"#{r['id']} — {r['label']}" for r in rows}
    pick = st.selectbox("Select record", list(labels), format_func=labels.get, key=f"{spec.table}_edit_pick")
    record = query_one(f"SELECT * FROM {spec.table} WHERE {spec.pk} = ?", (pick,))
    if record is None:
        st.warning("Record no longer exists.")
        return
    counter = st.session_state.setdefault(f"{spec.table}_edit_n", 0)
    key = f"{spec.table}_edit_{pick}_{counter}"
    if spec.can_edit:
        values = render_fields(spec.columns, record, key)
        extra = spec.extra_form("edit", record, values, key) if spec.extra_form else {}
        if st.button("💾 Update record", key=f"{key}_update", type="primary"):
            ok, result = _save(spec, "edit", values, extra, old=record)
            if ok:
                st.session_state[f"{spec.table}_edit_n"] = counter + 1
                flash("success", f"Record #{pick} updated.")
                st.rerun()
            for e in result:
                st.error(e)
    if spec.can_delete:
        st.button("🗑 Delete record", key=f"{key}_delete", on_click=_request_delete, args=(spec.table, pick))
        # The dialog stays open across reruns until it is confirmed, cancelled or dismissed.
        if st.session_state.get("_pending_delete") == (spec.table, pick):
            _confirm_delete(spec, pick, record, labels[pick])
    err = st.session_state.pop(f"{spec.table}_delete_error", None)
    if err:
        st.error(err)


def _request_delete(table, pick):
    st.session_state["_pending_delete"] = (table, pick)


def _clear_delete():
    st.session_state.pop("_pending_delete", None)


@st.dialog("Delete record?", on_dismiss=_clear_delete)
def _confirm_delete(spec, pick, record, label):
    st.write(f"**{label}** will be permanently deleted from `{spec.table}`. This cannot be undone.")
    left, right = st.columns(2)
    if left.button("Delete", type="primary", width="stretch", key="dlg_delete"):
        try:
            with transaction() as conn:
                if spec.before_delete:
                    err = spec.before_delete(conn, record)
                    if err:
                        raise ValueError(err)
                conn.execute(f"DELETE FROM {spec.table} WHERE {spec.pk} = ?", (pick,))
                log_action(f"DELETE {spec.table}", f"{spec.pk}={pick}: {_summary(record)}", conn=conn)
            st.session_state.pop(f"{spec.table}_edit_pick", None)
            st.session_state[f"{spec.table}_after_delete"] = True
            flash("success", f"Record #{pick} deleted.")
        except Exception as exc:
            st.session_state[f"{spec.table}_delete_error"] = friendly_error(exc)
        _clear_delete()
        st.rerun()
    if right.button("Cancel", width="stretch", key="dlg_cancel"):
        _clear_delete()
        st.rerun()


def render_crud(spec: TableSpec):
    show_flash()
    sections = [(VIEW_SECTION, lambda: _view_tab(spec))]
    if spec.can_add:
        sections.append((f"➕ {spec.add_label}", lambda: _add_tab(spec)))
    if spec.can_edit or spec.can_delete:
        sections.append(("✏️ Edit / Delete" if spec.can_edit else "🗑 Delete", lambda: _edit_tab(spec)))
    sections = (spec.extra_tabs + sections) if spec.tabs_first else (sections + spec.extra_tabs)
    funcs = dict(sections)
    if st.session_state.pop(f"{spec.table}_after_delete", False):
        # Back to the entity's list after a delete, so the removal is visible.
        st.session_state[f"{spec.table}_section"] = VIEW_SECTION
    choice = section_switcher(f"{spec.table}_section", list(funcs))
    st.write("")
    funcs[choice]()
