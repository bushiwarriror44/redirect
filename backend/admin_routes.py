import logging
import os
import re
import secrets
import string
from functools import wraps
from urllib.parse import urlparse

from flask import (
    Blueprint,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)

from models import RedirectLink, db

admin_bp = Blueprint("admin", __name__)
security_logger = logging.getLogger("security")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
SLUG_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def is_logged_in():
    return session.get("admin_logged_in", False)


def require_login(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_logged_in():
            return redirect(url_for("admin.admin_login"))
        return f(*args, **kwargs)

    return decorated_function


def is_valid_target_url(value):
    if not value:
        return False
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def normalize_slug(value):
    return (value or "").strip()


def generate_unique_slug(length=7):
    alphabet = string.ascii_letters + string.digits
    for _ in range(20):
        slug = "".join(secrets.choice(alphabet) for _ in range(length))
        exists = RedirectLink.query.filter_by(slug=slug).first()
        if not exists:
            return slug
    raise RuntimeError("Unable to generate unique slug")


def serialize_redirect(link):
    return {
        "id": link.id,
        "slug": link.slug,
        "target_url": link.target_url,
        "click_count": link.click_count,
        "created_at": link.created_at.isoformat() if link.created_at else None,
        "updated_at": link.updated_at.isoformat() if link.updated_at else None,
        "redirect_url": f"{request.host_url.rstrip('/')}/r/{link.slug}",
    }


@admin_bp.route("/admin-static/<path:filename>")
def admin_static(filename):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    admin_static_dir = os.path.join(base_dir, "views", "src")
    return send_from_directory(admin_static_dir, filename)


@admin_bp.route("/admin")
@admin_bp.route("/admin/")
def admin_redirect():
    return redirect(url_for("admin.admin_panel"))


@admin_bp.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if is_logged_in():
        return redirect(url_for("admin.admin_panel"))

    error = None
    if request.method == "POST":
        password = request.form.get("password", "")
        client_ip = request.remote_addr

        if password == ADMIN_PASSWORD:
            session.clear()
            session["admin_logged_in"] = True
            session.permanent = True
            security_logger.info("Successful admin login from IP: %s", client_ip)
            return redirect(url_for("admin.admin_panel"))

        security_logger.warning("Failed admin login attempt from IP: %s", client_ip)
        error = "Неверный пароль"

    return render_template("admin_login.html", error=error)


@admin_bp.route("/admin/panel")
@require_login
def admin_panel():
    response = make_response(render_template("admin_panel.html"))
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@admin_bp.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("admin.admin_login"))


@admin_bp.route("/admin/api/redirects", methods=["GET"])
@require_login
def list_redirects():
    links = RedirectLink.query.order_by(RedirectLink.created_at.desc()).all()
    return jsonify({"success": True, "redirects": [serialize_redirect(link) for link in links]})


@admin_bp.route("/admin/api/redirects", methods=["POST"])
@require_login
def create_redirect():
    data = request.get_json(silent=True) or {}
    target_url = (data.get("target_url") or "").strip()
    manual_slug = normalize_slug(data.get("slug"))

    if not is_valid_target_url(target_url):
        return jsonify({"success": False, "message": "Укажите корректный URL с http:// или https://"}), 400

    if manual_slug:
        if not SLUG_RE.match(manual_slug):
            return jsonify({"success": False, "message": "Slug может содержать только A-Z, a-z, 0-9, - и _"}), 400
        slug = manual_slug
    else:
        slug = generate_unique_slug()

    if RedirectLink.query.filter_by(slug=slug).first():
        return jsonify({"success": False, "message": "Такой slug уже существует"}), 409

    link = RedirectLink(slug=slug, target_url=target_url)
    db.session.add(link)
    db.session.commit()
    security_logger.info("Redirect created slug=%s ip=%s", slug, request.remote_addr)
    return jsonify({"success": True, "redirect": serialize_redirect(link)}), 201


@admin_bp.route("/admin/api/redirects/<int:link_id>", methods=["PUT"])
@require_login
def update_redirect(link_id):
    link = RedirectLink.query.get(link_id)
    if not link:
        return jsonify({"success": False, "message": "Редирект не найден"}), 404

    data = request.get_json(silent=True) or {}
    target_url = (data.get("target_url") or "").strip()
    slug = normalize_slug(data.get("slug"))

    if not is_valid_target_url(target_url):
        return jsonify({"success": False, "message": "Укажите корректный URL с http:// или https://"}), 400
    if not slug:
        return jsonify({"success": False, "message": "Slug не может быть пустым"}), 400
    if not SLUG_RE.match(slug):
        return jsonify({"success": False, "message": "Slug может содержать только A-Z, a-z, 0-9, - и _"}), 400

    duplicate = RedirectLink.query.filter(RedirectLink.slug == slug, RedirectLink.id != link_id).first()
    if duplicate:
        return jsonify({"success": False, "message": "Такой slug уже существует"}), 409

    link.slug = slug
    link.target_url = target_url
    db.session.commit()
    security_logger.info("Redirect updated id=%s slug=%s ip=%s", link_id, slug, request.remote_addr)
    return jsonify({"success": True, "redirect": serialize_redirect(link)})


@admin_bp.route("/admin/api/redirects/<int:link_id>", methods=["DELETE"])
@require_login
def delete_redirect(link_id):
    link = RedirectLink.query.get(link_id)
    if not link:
        return jsonify({"success": False, "message": "Редирект не найден"}), 404

    db.session.delete(link)
    db.session.commit()
    security_logger.info("Redirect deleted id=%s ip=%s", link_id, request.remote_addr)
    return jsonify({"success": True, "message": "Редирект удален"})


@admin_bp.route("/r/<slug>", methods=["GET"])
def handle_redirect(slug):
    link = RedirectLink.query.filter_by(slug=slug).first()
    if not link:
        return "Redirect not found", 404

    link.click_count += 1
    db.session.commit()
    return redirect(link.target_url, code=302)
