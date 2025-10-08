import argparse
import json
import os
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
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

app = Flask(__name__)
app.config.update(SECRET_KEY=SECRET_KEY)

Base = declarative_base()
engine = None
SessionLocal = None


class Setting(Base):
    __tablename__ = "settings"

    key = Column(String(100), primary_key=True)
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


def ensure_content_defaults(content: dict) -> dict:
    site = content.setdefault("site", {})
    flags = site.setdefault("flags", {})
    flags.setdefault("show_admin_border", False)
    return content


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


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_authenticated"):
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def split_lines(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


def page_title(content: dict, page_key: str) -> str:
    meta = content["pages"].get(page_key, {}).get("meta", {})
    return meta.get("title") or content["site"].get("tagline") or content["site"]["name"]


def compose_body_class(content: dict, *extra_classes: str) -> str:
    ensure_content_defaults(content)
    classes = [cls for cls in extra_classes if cls]
    if content["site"]["flags"].get("show_admin_border"):
        classes.append("admin-border")
    return " ".join(classes).strip()


@app.route("/")
def home():
    content = load_content()
    if should_use_mobile_alt(request):
        return render_mobile_home(content)
    return render_template(
        "index.html",
        content=content,
        theme=content["site"]["colors"],
        home=content["pages"]["home"],
        page_title=page_title(content, "home"),
        body_class=compose_body_class(content),
    )


@app.route("/mobile")
def mobile_home():
    content = load_content()
    return render_mobile_home(content)


@app.route("/services")
def services_page():
    content = load_content()
    return render_template(
        "services.html",
        content=content,
        theme=content["site"]["colors"],
        services=content["pages"]["services"],
        page_title=page_title(content, "services"),
        body_class=compose_body_class(content),
    )


@app.route("/contact")
def contact_page():
    content = load_content()
    return render_template(
        "contact.html",
        content=content,
        theme=content["site"]["colors"],
        contact=content["pages"]["contact"],
        page_title=page_title(content, "contact"),
        body_class=compose_body_class(content),
    )


@app.route("/uploads/<path:filename>")
def uploaded_file(filename: str):
    ensure_webroot()
    return send_from_directory(UPLOAD_FOLDER, filename)


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("admin_authenticated"):
        return redirect(url_for("admin_dashboard"))

    error = None
    if request.method == "POST":
        password = request.form.get("password", "")
        if password == load_admin_password():
            session["admin_authenticated"] = True
            next_url = request.args.get("next") or url_for("admin_dashboard")
            return redirect(next_url)
        error = "Incorrect password."
    content = load_content()
    return render_template(
        "login.html",
        content=content,
        theme=content["site"]["colors"],
        page_title="Admin",
        error=error,
        body_class=compose_body_class(content),
    )


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_authenticated", None)
    return redirect(url_for("home"))


@app.route("/admin", methods=["GET", "POST"])
@login_required
def admin_dashboard():
    content = load_content()
    message = session.pop("admin_message", None)

    if request.method == "POST":
        action = request.form.get("action")
        if action == "update_content":
            updated, password_changed = update_content_from_form(content, request.form)
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

    uploads = sorted(
        [f.name for f in UPLOAD_FOLDER.iterdir() if f.is_file() and not f.name.startswith(".")]
    )
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
    )


def update_content_from_form(content: dict, form: "MultiDict") -> tuple[dict, bool]:
    ensure_content_defaults(content)
    password_changed = False
    new_password = form.get("admin_password", "").strip()
    if new_password:
        save_admin_password(new_password)
        password_changed = True
    content["site"]["name"] = form.get("site_name", content["site"]["name"]).strip()
    content["site"]["tagline"] = form.get("site_tagline", "").strip()
    content["site"]["footer"]["description"] = form.get("footer_description", "").strip()
    content["site"]["flags"]["show_admin_border"] = bool(
        form.get("site_show_admin_border")
    )
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

    # Home page
    home = content["pages"]["home"]
    home["hero"]["badge"] = form.get("home_hero_badge", "").strip()
    home["hero"]["title"] = form.get("home_hero_title", "").strip()
    home["hero"]["description"] = form.get("home_hero_description", "").strip()
    home["hero"]["cta_text"] = form.get("home_hero_cta_text", "").strip()
    home["hero"]["cta_link"] = form.get("home_hero_cta_link", "").strip()
    home["hero"]["image"] = form.get("home_hero_image", "").strip()
    home["hero"]["image_alt"] = form.get("home_hero_image_alt", "").strip()

    home["what_we_print"]["title"] = form.get("home_what_we_print_heading", "").strip()
    home["what_we_print"]["items"] = parse_cards_with_bullets(
        form, "home_what_we_print"
    )
    home["why_choose"]["title"] = form.get("home_why_choose_heading", "").strip()
    home["why_choose"]["items"] = parse_cards(form, "home_why_choose")
    home["testimonials"]["title"] = form.get("home_testimonials_heading", "").strip()
    home["testimonials"]["items"] = parse_testimonials(form)

    # Services page
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

    # Contact page
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
