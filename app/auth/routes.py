from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from app.extensions import get_supabase
from app.constants import COUNTRIES

auth_bp = Blueprint("auth", __name__, url_prefix="/auth", template_folder="../templates/auth")


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        full_name = request.form.get("full_name", "")
        country = request.form.get("country", "")
        role = request.form.get("role")

        if role not in ("developer", "grower"):
            flash("Please choose whether you're a builder or a grower.", "error")
            return render_template("auth/signup.html", countries=COUNTRIES)

        is_developer = role == "developer"
        is_grower = role == "grower"

        supabase = get_supabase()
        result = supabase.auth.sign_up({
            "email": email,
            "password": password,
            "options": {
                "data": {
                    "full_name": full_name,
                    "is_developer": is_developer,
                    "is_grower": is_grower,
                    "country": country,
                }
            },
        })

        if result.user is None:
            flash("Couldn't create that account — check your details and try again.", "error")
            return render_template("auth/signup.html", countries=COUNTRIES)

        flash("Check your email to confirm your account.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/signup.html", countries=COUNTRIES)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        supabase = get_supabase()
        try:
            result = supabase.auth.sign_in_with_password({"email": email, "password": password})
        except Exception:
            flash("Incorrect email or password.", "error")
            return render_template("auth/login.html")

        session["access_token"] = result.session.access_token
        session["refresh_token"] = result.session.refresh_token
        session["user_id"] = result.user.id

        return redirect(url_for("dashboard.index"))

    return render_template("auth/login.html")


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))
