import argparse
import json
import os
import re
from copy import deepcopy
from functools import wraps
from math import ceil
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.utils import secure_filename
from sqlalchemy import Column, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

BASE_DIR = Path(__file__).parent.resolve()
DEFAULT_WEBROOT = BASE_DIR / "webroot"
WEBROOT_PATH = Path(os.environ.get("WEBROOT_PATH", DEFAULT_WEBROOT))
UPLOAD_FOLDER = WEBROOT_PATH / "uploads"

DEFAULT_ADMIN_PASSWORD = "printstudio"
SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-please")
DATABASE_FILE = WEBROOT_PATH / "site.db"
DEFAULT_PRINTER_INVENTORY = DEFAULT_WEBROOT / "printer_inventory.json"
DEFAULT_CONTENT_FILE = DEFAULT_WEBROOT / "content.json"


def _load_default_store_assets() -> tuple[dict, dict]:
    fallback_store = {
        "meta": {"title": "Printer Store"},
        "hero": {
            "badge": "Printer Store",
            "title": "Shop enterprise-ready laser printers",
            "description": "Explore curated HP, Canon, Kyocera, and Toshiba models with toner pairings we trust for reliable office output.",
            "cta_text": "Talk with a print specialist",
            "cta_link": "/contact",
        },
        "promises": {
            "title": "Every order includes",
            "items": [
                {
                    "title": "Configured for your workflow",
                    "description": "We stage firmware updates, network settings, and driver bundles so installations are plug-and-play.",
                },
                {
                    "title": "Guaranteed supply matching",
                    "description": "Each listing includes the toner SKUs we stock, so you never guess about refills.",
                },
                {
                    "title": "Local service and delivery",
                    "description": "Our technicians can deliver, install, and keep your fleet humming across the Coastal Bend.",
                },
            ],
        },
        "support": {
            "title": "Need a tailored print plan?",
            "description": "Bundle printers, managed supplies, and priority service into one agreement built for your team.",
            "cta_text": "Request a custom quote",
            "cta_link": "/contact",
        },
    }
    try:
        with DEFAULT_CONTENT_FILE.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return fallback_store, {"label": "Store", "url": "/store"}

    navigation = data.get("site", {}).get("navigation", [])
    store_nav = next((item for item in navigation if item.get("url") == "/store"), None)
    store_page = data.get("pages", {}).get("store") or fallback_store
    return store_page, store_nav or {"label": "Store", "url": "/store"}


def _build_default_printer_image_map() -> dict[tuple[str | None, str | None], dict[str, str]]:
    try:
        with DEFAULT_PRINTER_INVENTORY.open("r", encoding="utf-8") as fh:
            inventory = json.load(fh)
    except FileNotFoundError:
        return {}

    mapping: dict[tuple[str | None, str | None], dict[str, str]] = {}
    for manufacturer in inventory.get("manufacturers", []):
        name = manufacturer.get("name")
        for model in manufacturer.get("models", []):
            mapping[(name, model.get("model"))] = {
                "image": model.get("image", ""),
                "image_alt": model.get("image_alt", ""),
                "image_gallery": model.get("image_gallery") or [],
                "fallback_image": model.get("fallback_image", ""),
            }
    return mapping


DEFAULT_STORE_PAGE_TEMPLATE, DEFAULT_STORE_NAV_ITEM = _load_default_store_assets()
DEFAULT_PRINTER_IMAGE_MAP = _build_default_printer_image_map()
LEGACY_PRINTER_IMAGE_PATTERNS: dict[tuple[str | None, str | None], list[str]] = {
    (
        "HP",
        "LaserJet Pro M404n",
    ): [
        "hp.com/is/image/hp/hp-laserjet-pro-m404n-printer",
        "static/img/printers/hp-laserjet-pro-m404n.svg",
    ],
    (
        "HP",
        "LaserJet Pro M203dw",
    ): [
        "hp.com/is/image/hp/hp-laserjet-pro-m203dw-printer",
        "static/img/printers/hp-laserjet-pro-m203dw.svg",
    ],
    (
        "HP",
        "LaserJet Enterprise M507dn",
    ): [
        "hp.com/is/image/hp/hp-laserjet-enterprise-m507dn-printer",
    ],
    (
        "HP",
        "Color LaserJet Pro M454dw",
    ): [
        "hp.com/is/image/hp/hp-color-laserjet-pro-m454dw-printer",
    ],
    (
        "Canon",
        "imageCLASS LBP6230dw",
    ): [
        "usa.canon.com/content/dam/usa/en/products/printers/imageclass/lbp6230dw",
    ],
    (
        "Canon",
        "imageCLASS MF445dw",
    ): [
        "usa.canon.com/content/dam/usa/en/products/printers/imageclass/mf445dw",
    ],
    (
        "Canon",
        "imageCLASS LBP226dw",
    ): [
        "usa.canon.com/content/dam/usa/en/products/printers/imageclass/lbp226dw",
    ],
    (
        "Canon",
        "imageCLASS MF269dw II",
    ): [
        "usa.canon.com/content/dam/usa/en/products/printers/imageclass/mf269dw-ii",
        "rmsupport.canon.com",
    ],
    (
        "Kyocera",
        "ECOSYS P2040dw",
    ): [
        "kyoceradocumentsolutions.us/content/dam/kusa/en/products/printers/ecosys-p2040dw",
    ],
    (
        "Kyocera",
        "ECOSYS M5526cdw",
    ): [
        "kyoceradocumentsolutions.us/content/dam/kusa/en/products/mfps/ecosys-m5526cdw",
    ],
    (
        "Kyocera",
        "ECOSYS P3155dn",
    ): [
        "kyoceradocumentsolutions.us/content/dam/kusa/en/products/printers/ecosys-p3155dn",
    ],
    (
        "Kyocera",
        "ECOSYS P6235cdn",
    ): [
        "kyoceradocumentsolutions.us/content/dam/kusa/en/products/printers/ecosys-p6235cdn",
    ],
    (
        "Toshiba",
        "e-STUDIO 2515AC",
    ): [
        "business.toshiba.com/content/dam/tbs/products/mfp/e-studio2515ac",
    ],
    (
        "Toshiba",
        "e-STUDIO 330AC",
    ): [
        "business.toshiba.com/content/dam/tbs/products/mfp/e-studio330ac",
    ],
    (
        "Toshiba",
        "e-STUDIO 409p",
    ): [
        "business.toshiba.com/content/dam/tbs/products/printers/e-studio409p",
    ],
    (
        "Toshiba",
        "e-STUDIO 409s",
    ): [
        "business.toshiba.com/content/dam/tbs/products/mfp/e-studio409s",
    ],
}


def _merge_defaults(target: dict, defaults: dict) -> dict:
    for key, value in defaults.items():
        if key not in target:
            target[key] = deepcopy(value)
        elif isinstance(value, dict) and isinstance(target[key], dict):
            _merge_defaults(target[key], value)
    return target

app = Flask(__name__)
app.config.update(SECRET_KEY=SECRET_KEY)

Base = declarative_base()
engine = None
SessionLocal = None


class Setting(Base):
    __tablename__ = "settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)


class Draft(Base):
    __tablename__ = "drafts"

    id = Column(String(64), primary_key=True)
    value = Column(Text, nullable=False)


def ensure_directories() -> None:
    WEBROOT_PATH.mkdir(parents=True, exist_ok=True)
    UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)


def init_db() -> None:
    ensure_directories()
    global engine, SessionLocal
    if engine is None or SessionLocal is None:
        database_uri = f"sqlite:///{DATABASE_FILE}"
        engine = create_engine(
            database_uri, future=True, connect_args={"check_same_thread": False}
        )
        SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)
        Base.metadata.create_all(engine)

    assert SessionLocal is not None
    with SessionLocal() as session:
        created_defaults = False
        if session.get(Setting, "admin_password") is None:
            session.add(Setting(key="admin_password", value=json.dumps(DEFAULT_ADMIN_PASSWORD)))
            created_defaults = True
        if session.get(Setting, "content") is None:
            default_content = load_default_content()
            session.add(Setting(key="content", value=json.dumps(default_content)))
            created_defaults = True
        if session.get(Setting, "printer_inventory") is None:
            default_inventory = load_default_printer_inventory()
            session.add(
                Setting(key="printer_inventory", value=json.dumps(default_inventory))
            )
            created_defaults = True
        if created_defaults:
            session.commit()


def ensure_webroot() -> None:
    init_db()


def load_admin_password() -> str:
    ensure_webroot()
    assert SessionLocal is not None
    with SessionLocal() as session:
        record = session.get(Setting, "admin_password")
        if record is None:
            save_admin_password(DEFAULT_ADMIN_PASSWORD)
            return DEFAULT_ADMIN_PASSWORD
        return json.loads(record.value)


def save_admin_password(value: str) -> None:
    ensure_webroot()
    stored_value = json.dumps(value)
    assert SessionLocal is not None
    with SessionLocal() as session:
        record = session.get(Setting, "admin_password")
        if record is None:
            session.add(Setting(key="admin_password", value=stored_value))
        else:
            record.value = stored_value
        session.commit()


def load_default_content() -> dict:
    with (DEFAULT_WEBROOT / "content.json").open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    return ensure_content_defaults(data)


def load_default_printer_inventory() -> dict:
    with DEFAULT_PRINTER_INVENTORY.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def ensure_content_defaults(content: dict) -> dict:
    site = content.setdefault("site", {})
    flags = site.setdefault("flags", {})
    if "show_admin_border" in flags:
        flags.pop("show_admin_border", None)
    navigation = site.setdefault("navigation", [])
    if not any(item.get("url") == "/store" for item in navigation):
        insert_at = next(
            (index for index, item in enumerate(navigation) if item.get("url") == "/contact"),
            len(navigation),
        )
        navigation.insert(insert_at, deepcopy(DEFAULT_STORE_NAV_ITEM))

    pages = content.setdefault("pages", {})
    store_defaults = deepcopy(DEFAULT_STORE_PAGE_TEMPLATE)
    store = pages.get("store")
    if not isinstance(store, dict):
        pages["store"] = store_defaults
    else:
        _merge_defaults(store, store_defaults)
        if isinstance(store.get("promises"), dict) and not store["promises"].get("items"):
            store["promises"]["items"] = deepcopy(store_defaults["promises"]["items"])
    return content


def ensure_printer_inventory_defaults(inventory: dict) -> tuple[dict, bool]:
    changed = False
    manufacturers = inventory.setdefault("manufacturers", [])
    for manufacturer in manufacturers:
        models = manufacturer.setdefault("models", [])
        for model in models:
            if not isinstance(model.get("cartridges"), list):
                model["cartridges"] = []
                changed = True
            manufacturer_name = manufacturer.get("name")
            model_name = model.get("model")
            defaults = DEFAULT_PRINTER_IMAGE_MAP.get((manufacturer_name, model_name))
            legacy_patterns = LEGACY_PRINTER_IMAGE_PATTERNS.get((manufacturer_name, model_name), [])
            if defaults:
                desired_image = defaults.get("image") or ""
                desired_alt = defaults.get("image_alt") or ""
                desired_gallery = defaults.get("image_gallery") or []
                desired_fallback = defaults.get("fallback_image") or ""
                current_image = model.get("image") or ""
                if desired_image:
                    should_override = False
                    if (
                        not current_image
                        or current_image.startswith("/static/img/printers/")
                        or current_image == desired_image
                    ):
                        should_override = True
                    elif any(pattern in current_image for pattern in legacy_patterns):
                        should_override = True
                    if should_override and current_image != desired_image:
                        model["image"] = desired_image
                        changed = True
                if desired_alt:
                    current_alt = model.get("image_alt") or ""
                    if (not current_alt or current_alt.startswith("Stylized illustration")) and current_alt != desired_alt:
                        model["image_alt"] = desired_alt
                        changed = True
                if desired_gallery:
                    current_gallery = model.get("image_gallery")
                    if not isinstance(current_gallery, list) or not current_gallery:
                        model["image_gallery"] = [url for url in desired_gallery if url]
                        changed = True
                if desired_fallback:
                    current_fallback = model.get("fallback_image") or ""
                    if (not current_fallback or current_fallback.startswith("/static/img/printers/")) and current_fallback != desired_fallback:
                        model["fallback_image"] = desired_fallback
                        changed = True
            if not isinstance(model.get("image_gallery"), list):
                model["image_gallery"] = []
                changed = True
            else:
                cleaned_gallery = [url for url in model["image_gallery"] if url]
                if cleaned_gallery != model["image_gallery"]:
                    model["image_gallery"] = cleaned_gallery
                    changed = True
            if not model.get("image"):
                slug_base = f"{manufacturer.get('name', '')} {model.get('model', '')}".strip().lower()
                slug = re.sub(r"[^a-z0-9]+", "-", slug_base).strip("-") or "printer"
                static_path = Path("static/img/printers") / f"{slug}.svg"
                candidate = BASE_DIR / static_path
                if candidate.exists():
                    model["image"] = f"/{static_path.as_posix()}"
                    changed = True
            primary_image = model.get("image") or ""
            gallery = model.get("image_gallery") or []
            if primary_image and (not gallery or primary_image not in gallery):
                model["image_gallery"] = [primary_image, *[url for url in gallery if url != primary_image]]
                changed = True
            if not model.get("image_alt") and model.get("model"):
                manufacturer_name = manufacturer.get("name", "").strip()
                model_name = model.get("model", "").strip()
                if manufacturer_name or model_name:
                    model["image_alt"] = (
                        f"Stylized illustration of the {manufacturer_name} {model_name} laser printer"
                    ).strip()
                    changed = True
            if desired_fallback := defaults.get("fallback_image") if defaults else "":
                if not model.get("fallback_image"):
                    model["fallback_image"] = desired_fallback
                    changed = True
            elif not model.get("fallback_image") and primary_image:
                slug_base = f"{manufacturer.get('name', '')} {model.get('model', '')}".strip().lower()
                slug = re.sub(r"[^a-z0-9]+", "-", slug_base).strip("-") or "printer"
                static_path = Path("static/img/printers") / f"{slug}.svg"
                candidate = BASE_DIR / static_path
                if candidate.exists():
                    model["fallback_image"] = f"/{static_path.as_posix()}"
                    changed = True
    return inventory, changed


def load_content() -> dict:
    ensure_webroot()
    assert SessionLocal is not None
    with SessionLocal() as session:
        record = session.get(Setting, "content")
        if record is None:
            default_content = load_default_content()
            session.add(Setting(key="content", value=json.dumps(default_content)))
            session.commit()
            return default_content
        return ensure_content_defaults(json.loads(record.value))


def save_content(data: dict) -> None:
    ensure_webroot()
    assert SessionLocal is not None
    stored_value = json.dumps(data, ensure_ascii=False, indent=2)
    with SessionLocal() as session:
        record = session.get(Setting, "content")
        if record is None:
            session.add(Setting(key="content", value=stored_value))
        else:
            record.value = stored_value
        session.commit()


def load_printer_inventory() -> dict:
    ensure_webroot()
    assert SessionLocal is not None
    with SessionLocal() as session:
        record = session.get(Setting, "printer_inventory")
        if record is None:
            default_inventory = load_default_printer_inventory()
            default_inventory, _ = ensure_printer_inventory_defaults(default_inventory)
            session.add(
                Setting(
                    key="printer_inventory",
                    value=json.dumps(default_inventory, ensure_ascii=False),
                )
            )
            session.commit()
            return default_inventory
        data = json.loads(record.value)
        data, changed = ensure_printer_inventory_defaults(data)
        if changed:
            record.value = json.dumps(data, ensure_ascii=False)
            session.commit()
        return data


def flatten_printer_inventory(inventory: dict) -> tuple[list[dict], list[dict]]:
    printers: list[dict] = []
    manufacturer_notes: list[dict] = []
    for manufacturer in inventory.get("manufacturers", []):
        name = manufacturer.get("name")
        note = manufacturer.get("note")
        models = manufacturer.get("models", [])
        if note and not models:
            manufacturer_notes.append({"manufacturer": name, "note": note})
        for model in models:
            entry = deepcopy(model)
            entry["manufacturer"] = name
            entry.setdefault("cartridges", [])
            printers.append(entry)

    printers.sort(
        key=lambda item: (
            item.get("manufacturer") or "",
            -1 * (item.get("release_year") or 0),
            item.get("model") or "",
        )
    )
    return printers, manufacturer_notes


def is_admin_authenticated() -> bool:
    return bool(session.get("admin_authenticated"))


def is_admin_mode() -> bool:
    return bool(session.get("admin_mode"))


def ensure_draft_session() -> str:
    ensure_webroot()
    draft_id = session.get("draft_id")
    assert SessionLocal is not None
    with SessionLocal() as db:
        record = db.get(Draft, draft_id) if draft_id else None
        if record is None:
            draft_id = uuid4().hex
            content = load_content()
            db.add(Draft(id=draft_id, value=json.dumps(content, ensure_ascii=False)))
            db.commit()
        session["draft_id"] = draft_id
        session.modified = True
        return draft_id


def load_draft_content() -> dict:
    draft_id = ensure_draft_session()
    assert SessionLocal is not None
    with SessionLocal() as db:
        record = db.get(Draft, draft_id)
        if record is None:
            return ensure_content_defaults(load_content())
        return ensure_content_defaults(json.loads(record.value))


def save_draft_content(data: dict) -> None:
    draft_id = ensure_draft_session()
    assert SessionLocal is not None
    stored_value = json.dumps(data, ensure_ascii=False)
    with SessionLocal() as db:
        record = db.get(Draft, draft_id)
        if record is None:
            db.add(Draft(id=draft_id, value=stored_value))
        else:
            record.value = stored_value
        db.commit()


def clear_draft_content() -> None:
    ensure_webroot()
    draft_id = session.pop("draft_id", None)
    session.pop("admin_mode", None)
    if not draft_id:
        return
    assert SessionLocal is not None
    with SessionLocal() as db:
        record = db.get(Draft, draft_id)
        if record is not None:
            db.delete(record)
            db.commit()


def get_request_content() -> dict:
    if is_admin_mode():
        try:
            return load_draft_content()
        except Exception:
            return load_content()
    return load_content()


def list_uploads() -> list[str]:
    ensure_webroot()
    if not UPLOAD_FOLDER.exists():
        return []
    return sorted(
        [f.name for f in UPLOAD_FOLDER.iterdir() if f.is_file() and not f.name.startswith(".")]
    )


@app.route("/api/printers")
def api_printer_inventory() -> "Response":
    return jsonify(load_printer_inventory())


def safe_next_url(candidate: str | None) -> str:
    if not candidate:
        return url_for("home")
    parsed = urlparse(candidate)
    if parsed.scheme or parsed.netloc:
        return url_for("home")
    if not candidate.startswith("/"):
        candidate = f"/{candidate}"
    return candidate


def enter_admin_mode() -> None:
    session["admin_mode"] = True
    session.modified = True
    ensure_draft_session()


def exit_admin_mode(save_changes: bool) -> None:
    if save_changes:
        draft_content = load_draft_content()
        save_content(draft_content)
    clear_draft_content()


def update_site_settings_from_form(content: dict, form: "MultiDict") -> tuple[dict, bool]:
    ensure_content_defaults(content)
    password_changed = False
    new_password = form.get("admin_password", "").strip()
    if new_password:
        save_admin_password(new_password)
        password_changed = True
    content["site"]["name"] = form.get("site_name", content["site"]["name"]).strip()
    content["site"]["tagline"] = form.get("site_tagline", "").strip()
    content["site"]["footer"]["description"] = form.get("footer_description", "").strip()

    colors = content["site"].setdefault("colors", {})
    colors["primary"] = form.get("color_primary", colors.get("primary", "#1d4ed8"))
    colors["primary_dark"] = form.get(
        "color_primary_dark", colors.get("primary_dark", "#1e40af")
    )
    colors["accent"] = form.get("color_accent", colors.get("accent", "#f59e0b"))
    colors["background"] = form.get(
        "color_background", colors.get("background", "#f8fafc")
    )
    colors["text"] = form.get("color_text", colors.get("text", "#1f2937"))
    colors["muted"] = form.get("color_muted", colors.get("muted", "#64748b"))

    visit_lines = split_lines(form.get("footer_visit_lines", ""))
    content["site"]["footer"]["visit"]["lines"] = visit_lines

    contact_lines_raw = split_lines(form.get("footer_contact_lines", ""))
    contact_lines = []
    for line in contact_lines_raw:
        if "|" in line:
            label, url = line.split("|", 1)
            label = label.strip()
            url = url.strip()
        else:
            label, url = line.strip(), ""
        if not label:
            continue
        line_dict = {"label": label}
        if url:
            line_dict["url"] = url
        contact_lines.append(line_dict)
    content["site"]["footer"]["contact"]["lines"] = contact_lines
    return content, password_changed


def update_home_page_from_form(content: dict, form: "MultiDict") -> dict:
    home = content["pages"]["home"]
    home["hero"]["badge"] = form.get("home_hero_badge", "").strip()
    home["hero"]["title"] = form.get("home_hero_title", "").strip()
    home["hero"]["description"] = form.get("home_hero_description", "").strip()
    home["hero"]["cta_text"] = form.get("home_hero_cta_text", "").strip()
    home["hero"]["cta_link"] = form.get("home_hero_cta_link", "").strip()
    home["hero"]["image"] = form.get("home_hero_image", "").strip()
    home["hero"]["image_alt"] = form.get("home_hero_image_alt", "").strip()

    home["what_we_print"]["title"] = form.get("home_what_we_print_heading", "").strip()
    home["what_we_print"]["items"] = parse_cards_with_bullets(form, "home_what_we_print")
    home["why_choose"]["title"] = form.get("home_why_choose_heading", "").strip()
    home["why_choose"]["items"] = parse_cards(form, "home_why_choose")
    home["testimonials"]["title"] = form.get("home_testimonials_heading", "").strip()
    home["testimonials"]["items"] = parse_testimonials(form)
    return home


def update_services_page_from_form(content: dict, form: "MultiDict") -> dict:
    services = content["pages"]["services"]
    services["hero"]["badge"] = form.get("services_hero_badge", "").strip()
    services["hero"]["title"] = form.get("services_hero_title", "").strip()
    services["hero"]["description"] = form.get("services_hero_description", "").strip()

    services["capabilities"]["title"] = form.get("services_capabilities_heading", "").strip()
    services["capabilities"]["items"] = parse_cards_with_bullets(
        form, "services_capabilities"
    )
    services["bundles"]["title"] = form.get("services_bundles_heading", "").strip()
    services["bundles"]["items"] = parse_cards_with_bullets(
        form, "services_bundles", include_price=True
    )
    services["process"]["title"] = form.get("services_process_heading", "").strip()
    services["process"]["steps"] = parse_cards(form, "services_process")
    services["process"]["cta"]["title"] = form.get("services_process_cta_title", "").strip()
    services["process"]["cta"]["description"] = form.get(
        "services_process_cta_description", ""
    ).strip()
    services["process"]["cta"]["text"] = form.get("services_process_cta_text", "").strip()
    services["process"]["cta"]["link"] = form.get("services_process_cta_link", "").strip()
    return services


def update_contact_page_from_form(content: dict, form: "MultiDict") -> dict:
    contact = content["pages"]["contact"]
    contact["hero"]["badge"] = form.get("contact_hero_badge", "").strip()
    contact["hero"]["title"] = form.get("contact_hero_title", "").strip()
    contact["hero"]["description"] = form.get("contact_hero_description", "").strip()

    contact["studio"]["visit_title"] = form.get("contact_visit_title", "").strip()
    contact["studio"]["address"] = split_lines(form.get("contact_address_lines", ""))
    contact["studio"]["hours_title"] = form.get("contact_hours_title", "").strip()
    contact["studio"]["hours"] = split_lines(form.get("contact_hours_lines", ""))
    contact["studio"]["phone_title"] = form.get("contact_phone_title", "").strip()
    contact["studio"]["phone"] = form.get("contact_phone", "").strip()
    contact["studio"]["phone_href"] = form.get("contact_phone_href", "").strip()
    contact["studio"]["email_title"] = form.get("contact_email_title", "").strip()
    contact["studio"]["email"] = form.get("contact_email", "").strip()

    contact["form"]["title"] = form.get("contact_form_title", "").strip()
    contact["form"]["submit_text"] = form.get("contact_form_submit", "").strip()
    contact["form"]["fields"] = parse_form_fields(form)

    contact["about"]["title"] = form.get("contact_about_title", "").strip()
    contact["about"]["description"] = form.get("contact_about_description", "").strip()
    contact["about"]["cards"] = parse_about_cards(form)
    return contact


def update_store_page_from_form(content: dict, form: "MultiDict") -> dict:
    store = content["pages"].setdefault("store", deepcopy(DEFAULT_STORE_PAGE_TEMPLATE))

    hero_defaults = DEFAULT_STORE_PAGE_TEMPLATE.get("hero", {})
    hero = store.setdefault("hero", {})
    hero["badge"] = form.get("store_hero_badge", hero.get("badge", hero_defaults.get("badge", ""))).strip()
    hero["title"] = form.get("store_hero_title", hero.get("title", hero_defaults.get("title", ""))).strip()
    hero["description"] = form.get(
        "store_hero_description",
        hero.get("description", hero_defaults.get("description", "")),
    ).strip()
    hero["cta_text"] = form.get(
        "store_hero_cta_text", hero.get("cta_text", hero_defaults.get("cta_text", ""))
    ).strip()
    hero["cta_link"] = form.get(
        "store_hero_cta_link", hero.get("cta_link", hero_defaults.get("cta_link", ""))
    ).strip()

    promises_defaults = DEFAULT_STORE_PAGE_TEMPLATE.get("promises", {})
    promises = store.setdefault("promises", {})
    promises["title"] = form.get(
        "store_promises_heading",
        promises.get("title", promises_defaults.get("title", "")),
    ).strip()
    titles = form.getlist("store_promises_title")
    descriptions = form.getlist("store_promises_description")
    items: list[dict] = []
    for title, description in zip(titles, descriptions):
        title = title.strip()
        description = description.strip()
        if not any([title, description]):
            continue
        items.append({"title": title, "description": description})
    if items:
        promises["items"] = items
    elif not promises.get("items"):
        promises["items"] = deepcopy(promises_defaults.get("items", []))

    support_defaults = DEFAULT_STORE_PAGE_TEMPLATE.get("support", {})
    support = store.setdefault("support", {})
    support["title"] = form.get(
        "store_support_title", support.get("title", support_defaults.get("title", ""))
    ).strip()
    support["description"] = form.get(
        "store_support_description",
        support.get("description", support_defaults.get("description", "")),
    ).strip()
    support["cta_text"] = form.get(
        "store_support_cta_text", support.get("cta_text", support_defaults.get("cta_text", ""))
    ).strip()
    support["cta_link"] = form.get(
        "store_support_cta_link", support.get("cta_link", support_defaults.get("cta_link", ""))
    ).strip()

    return store


def apply_page_update(content: dict, form: "MultiDict", page_key: str) -> dict:
    if page_key == "home":
        return update_home_page_from_form(content, form)
    if page_key == "services":
        return update_services_page_from_form(content, form)
    if page_key == "contact":
        return update_contact_page_from_form(content, form)
    if page_key == "store":
        return update_store_page_from_form(content, form)
    raise ValueError(f"Unsupported page key: {page_key}")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not is_admin_authenticated():
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


@app.context_processor
def inject_admin_session_state() -> dict:
    return {"admin_authenticated": is_admin_authenticated()}


def split_lines(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


def page_title(content: dict, page_key: str) -> str:
    meta = content["pages"].get(page_key, {}).get("meta", {})
    return meta.get("title") or content["site"].get("tagline") or content["site"]["name"]


def compose_body_class(content: dict, *extra_classes: str) -> str:
    ensure_content_defaults(content)
    classes = [cls for cls in extra_classes if cls]
    if is_admin_mode():
        classes.extend(["admin-border", "admin-mode-active"])
    seen: dict[str, None] = {}
    for cls in classes:
        if cls:
            seen.setdefault(cls, None)
    return " ".join(seen.keys()).strip()


@app.route("/")
def home():
    content = get_request_content()
    admin_mode = is_admin_mode()
    uploads = list_uploads() if admin_mode else []
    if should_use_mobile_alt(request):
        return render_mobile_home(content)
    return render_template(
        "index.html",
        content=content,
        theme=content["site"]["colors"],
        home=content["pages"]["home"],
        page_title=page_title(content, "home"),
        body_class=compose_body_class(content),
        admin_mode=admin_mode,
        editor_uploads=uploads,
        page_key="home",
    )


@app.route("/mobile")
def mobile_home():
    content = get_request_content()
    return render_mobile_home(content)


@app.route("/services")
def services_page():
    content = get_request_content()
    admin_mode = is_admin_mode()
    uploads = list_uploads() if admin_mode else []
    return render_template(
        "services.html",
        content=content,
        theme=content["site"]["colors"],
        services=content["pages"]["services"],
        page_title=page_title(content, "services"),
        body_class=compose_body_class(content),
        admin_mode=admin_mode,
        editor_uploads=uploads,
        page_key="services",
    )


@app.route("/store")
def store_page():
    content = get_request_content()
    admin_mode = is_admin_mode()
    uploads = list_uploads() if admin_mode else []
    inventory = load_printer_inventory()
    printers, manufacturer_notes = flatten_printer_inventory(inventory)

    per_page = 9
    total_printers = len(printers)
    total_pages = max(1, ceil(total_printers / per_page))
    page_number = request.args.get("page", type=int, default=1) or 1
    page_number = max(1, min(page_number, total_pages))
    start = (page_number - 1) * per_page
    end = start + per_page
    paginated = printers[start:end]

    pagination = {
        "page": page_number,
        "total_pages": total_pages,
        "has_prev": page_number > 1,
        "has_next": page_number < total_pages,
        "prev_page": page_number - 1,
        "next_page": page_number + 1,
        "pages": list(range(1, total_pages + 1)),
    }

    return render_template(
        "store.html",
        content=content,
        theme=content["site"]["colors"],
        store=content["pages"]["store"],
        printers=paginated,
        pagination=pagination,
        inventory_count=total_printers,
        manufacturer_notes=manufacturer_notes,
        page_title=page_title(content, "store"),
        body_class=compose_body_class(content),
        admin_mode=admin_mode,
        editor_uploads=uploads,
        page_key="store",
    )


@app.route("/contact")
def contact_page():
    content = get_request_content()
    admin_mode = is_admin_mode()
    uploads = list_uploads() if admin_mode else []
    return render_template(
        "contact.html",
        content=content,
        theme=content["site"]["colors"],
        contact=content["pages"]["contact"],
        page_title=page_title(content, "contact"),
        body_class=compose_body_class(content),
        admin_mode=admin_mode,
        editor_uploads=uploads,
        page_key="contact",
    )


@app.route("/uploads/<path:filename>")
def uploaded_file(filename: str):
    ensure_webroot()
    return send_from_directory(UPLOAD_FOLDER, filename)


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "GET":
        session.pop("admin_authenticated", None)
    if is_admin_authenticated():
        return redirect(url_for("admin_dashboard"))

    error = None
    if request.method == "POST":
        password = request.form.get("password", "")
        if password == load_admin_password():
            session["admin_authenticated"] = True
            next_url = request.args.get("next") or url_for("admin_dashboard")
            return redirect(next_url)
        error = "Incorrect password."
    content = get_request_content()
    return render_template(
        "login.html",
        content=content,
        theme=content["site"]["colors"],
        page_title="Admin",
        error=error,
        body_class=compose_body_class(content),
        admin_mode=is_admin_mode(),
    )


@app.route("/admin/logout")
def admin_logout():
    clear_draft_content()
    session.pop("admin_authenticated", None)
    return redirect(url_for("home"))


@app.route("/admin", methods=["GET", "POST"])
@login_required
def admin_dashboard():
    content = load_content()
    message = session.pop("admin_message", None)
    admin_mode_active = is_admin_mode()

    if request.method == "POST":
        action = request.form.get("action")
        if action == "update_site_settings":
            updated, password_changed = update_site_settings_from_form(
                content, request.form
            )
            save_content(updated)
            message_text = "Changes saved successfully."
            if password_changed:
                message_text += " Admin password updated."
            session["admin_message"] = message_text
            return redirect(url_for("admin_dashboard"))
        if action == "upload_media":
            file = request.files.get("media")
            if file and file.filename:
                filename = secure_filename(file.filename)
                destination = UPLOAD_FOLDER / filename
                file.save(destination)
                session["admin_message"] = f"Uploaded {filename}."
            else:
                session["admin_message"] = "Please choose an image to upload."
            return redirect(url_for("admin_dashboard"))

    uploads = list_uploads()
    password_value = load_admin_password()
    if not password_value:
        password_state = "empty"
    elif password_value == DEFAULT_ADMIN_PASSWORD:
        password_state = "default"
    else:
        password_state = "custom"
    return render_template(
        "admin.html",
        content=content,
        theme=content["site"]["colors"],
        home=content["pages"]["home"],
        services=content["pages"]["services"],
        contact=content["pages"]["contact"],
        page_title="Admin",
        message=message,
        uploads=uploads,
        webroot_path=str(WEBROOT_PATH),
        admin_password_state=password_state,
        body_class=compose_body_class(content),
        admin_mode=admin_mode_active,
    )


@app.route("/admin/mode", methods=["POST"])
@login_required
def admin_mode_toggle():
    action = request.form.get("action")
    next_url = safe_next_url(request.form.get("next") or request.referrer)
    if action == "enter":
        enter_admin_mode()
        session["admin_message"] = "Admin mode enabled. Edit pages directly and save when finished."
    elif action == "save_exit":
        exit_admin_mode(save_changes=True)
        session["admin_message"] = "Draft changes published and admin mode exited."
    elif action == "discard_exit":
        exit_admin_mode(save_changes=False)
        session["admin_message"] = "Draft discarded. Admin mode exited."
    return redirect(next_url)


@app.route("/admin/draft/<page_key>", methods=["POST"])
@login_required
def update_draft(page_key: str):
    if not is_admin_mode():
        return jsonify({"error": "Admin mode is not active."}), 400

    try:
        content = load_draft_content()
        apply_page_update(content, request.form, page_key)
        save_draft_content(content)
        page_data = content["pages"].get(page_key, {})
        return jsonify({"page": page_data, "site": content["site"]})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


def update_content_from_form(content: dict, form: "MultiDict") -> tuple[dict, bool]:
    content, password_changed = update_site_settings_from_form(content, form)
    update_home_page_from_form(content, form)
    update_services_page_from_form(content, form)
    update_contact_page_from_form(content, form)
    update_store_page_from_form(content, form)
    return content, password_changed


def render_mobile_home(content: dict):
    return render_template(
        "mobile_home.html",
        content=content,
        theme=content["site"]["colors"],
        home=content["pages"]["home"],
        page_title=page_title(content, "home"),
        body_class=compose_body_class(content, "mobile-alt"),
        using_mobile_alt=True,
        admin_mode=is_admin_mode(),
    )


def should_use_mobile_alt(req) -> bool:
    if req.args.get("full") == "1":
        return False
    user_agent = (req.user_agent.string or "").lower()
    if not user_agent:
        return False
    mobile_indicators = (
        "iphone",
        "android",
        "ipad",
        "mobile",
        "ipod",
        "windows phone",
        "blackberry",
    )
    return any(indicator in user_agent for indicator in mobile_indicators)


def parse_cards_with_bullets(form, prefix: str, include_price: bool = False) -> list[dict]:
    titles = form.getlist(f"{prefix}_title")
    descriptions = form.getlist(f"{prefix}_description")
    bullets_raw = form.getlist(f"{prefix}_bullets")
    images = form.getlist(f"{prefix}_image")
    image_alts = form.getlist(f"{prefix}_image_alt")
    prices = form.getlist(f"{prefix}_price") if include_price else []
    items: list[dict] = []
    for index, values in enumerate(zip(titles, descriptions, bullets_raw)):
        title, description, bullet_text = [value.strip() for value in values]
        price = prices[index].strip() if include_price and index < len(prices) else ""
        if not any([title, description, bullet_text, price]):
            continue
        entry = {"title": title, "description": description, "bullets": split_lines(bullet_text)}
        image = images[index].strip() if index < len(images) else ""
        image_alt = image_alts[index].strip() if index < len(image_alts) else ""
        entry["image"] = image
        entry["image_alt"] = image_alt
        if include_price:
            entry["price"] = price
        items.append(entry)
    return items


def parse_cards(form, prefix: str) -> list[dict]:
    titles = form.getlist(f"{prefix}_title")
    descriptions = form.getlist(f"{prefix}_description")
    images = form.getlist(f"{prefix}_image")
    image_alts = form.getlist(f"{prefix}_image_alt")
    items: list[dict] = []
    for index, (title, description) in enumerate(zip(titles, descriptions)):
        title = title.strip()
        description = description.strip()
        if not any([title, description]):
            continue
        image = images[index].strip() if index < len(images) else ""
        image_alt = image_alts[index].strip() if index < len(image_alts) else ""
        items.append(
            {
                "title": title,
                "description": description,
                "image": image,
                "image_alt": image_alt,
            }
        )
    return items


def parse_testimonials(form) -> list[dict]:
    quotes = form.getlist("home_testimonials_quote")
    authors = form.getlist("home_testimonials_author")
    testimonials: list[dict] = []
    for quote, author in zip(quotes, authors):
        quote = quote.strip()
        author = author.strip()
        if not quote:
            continue
        testimonials.append({"quote": quote, "author": author})
    return testimonials


def parse_form_fields(form) -> list[dict]:
    labels = form.getlist("contact_form_label")
    names = form.getlist("contact_form_name")
    types = form.getlist("contact_form_type")
    placeholders = form.getlist("contact_form_placeholder")
    fields: list[dict] = []
    for label, name, field_type, placeholder in zip(labels, names, types, placeholders):
        label = label.strip()
        name = name.strip()
        placeholder = placeholder.strip()
        field_type = field_type.strip() or "text"
        if not name:
            continue
        fields.append(
            {
                "label": label or name.title(),
                "name": name,
                "type": field_type,
                "placeholder": placeholder,
            }
        )
    return fields


def parse_about_cards(form) -> list[dict]:
    titles = form.getlist("contact_about_title_item")
    descriptions = form.getlist("contact_about_description_item")
    cards: list[dict] = []
    for title, description in zip(titles, descriptions):
        title = title.strip()
        description = description.strip()
        if not any([title, description]):
            continue
        cards.append({"title": title, "description": description})
    return cards


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the print studio admin site")
    parser.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"), help="Bind address")
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PORT", 5000)),
        help="Port to listen on",
    )
    parser.add_argument(
        "--clear-admin-password",
        action="store_true",
        help="Reset the admin password to the default value",
    )
    args = parser.parse_args()

    if args.clear_admin_password:
        save_admin_password(DEFAULT_ADMIN_PASSWORD)
        print("Admin password reset to default value.")

    app.run(debug=True, host=args.host, port=args.port)
