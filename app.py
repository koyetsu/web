import json
import os
import shutil
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

BASE_DIR = Path(__file__).parent.resolve()
DEFAULT_WEBROOT = BASE_DIR / "webroot"
WEBROOT_PATH = Path(os.environ.get("WEBROOT_PATH", DEFAULT_WEBROOT))
CONTENT_FILE = WEBROOT_PATH / "content.json"
UPLOAD_FOLDER = WEBROOT_PATH / "uploads"

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "printstudio")
SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-please")

app = Flask(__name__)
app.config.update(SECRET_KEY=SECRET_KEY)


def ensure_webroot() -> None:
    WEBROOT_PATH.mkdir(parents=True, exist_ok=True)
    UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
    if not CONTENT_FILE.exists():
        if WEBROOT_PATH != DEFAULT_WEBROOT and (DEFAULT_WEBROOT / "content.json").exists():
            shutil.copy(DEFAULT_WEBROOT / "content.json", CONTENT_FILE)
        else:
            default_content = load_default_content()
            save_content(default_content)


def load_default_content() -> dict:
    with (DEFAULT_WEBROOT / "content.json").open("r", encoding="utf-8") as fh:
        return json.load(fh)


def load_content() -> dict:
    ensure_webroot()
    with CONTENT_FILE.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def save_content(data: dict) -> None:
    ensure_webroot()
    with CONTENT_FILE.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


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


@app.route("/")
def home():
    content = load_content()
    return render_template(
        "index.html",
        content=content,
        theme=content["site"]["colors"],
        home=content["pages"]["home"],
        page_title=page_title(content, "home"),
    )


@app.route("/services")
def services_page():
    content = load_content()
    return render_template(
        "services.html",
        content=content,
        theme=content["site"]["colors"],
        services=content["pages"]["services"],
        page_title=page_title(content, "services"),
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
        if password == ADMIN_PASSWORD:
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
            updated = update_content_from_form(content, request.form)
            save_content(updated)
            session["admin_message"] = "Changes saved successfully."
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
    )


def update_content_from_form(content: dict, form: "MultiDict") -> dict:
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

    return content


def parse_cards_with_bullets(form, prefix: str, include_price: bool = False) -> list[dict]:
    titles = form.getlist(f"{prefix}_title")
    descriptions = form.getlist(f"{prefix}_description")
    bullets_raw = form.getlist(f"{prefix}_bullets")
    prices = form.getlist(f"{prefix}_price") if include_price else []
    items: list[dict] = []
    for index, values in enumerate(zip(titles, descriptions, bullets_raw)):
        title, description, bullet_text = [value.strip() for value in values]
        price = prices[index].strip() if include_price and index < len(prices) else ""
        if not any([title, description, bullet_text, price]):
            continue
        entry = {"title": title, "description": description, "bullets": split_lines(bullet_text)}
        if include_price:
            entry["price"] = price
        items.append(entry)
    return items


def parse_cards(form, prefix: str) -> list[dict]:
    titles = form.getlist(f"{prefix}_title")
    descriptions = form.getlist(f"{prefix}_description")
    items: list[dict] = []
    for title, description in zip(titles, descriptions):
        title = title.strip()
        description = description.strip()
        if not any([title, description]):
            continue
        items.append({"title": title, "description": description})
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
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host=host, port=port)
