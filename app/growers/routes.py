"""Old grower pages: the card-based Browse page and grower cards replace them."""
from flask import Blueprint, redirect, url_for

growers_bp = Blueprint("growers", __name__, url_prefix="/growers", template_folder="../templates/growers")


@growers_bp.route("/")
def browse():
    return redirect(url_for("browse.index", tab="growers"))


@growers_bp.route("/<grower_id>")
def detail(grower_id):
    return redirect(url_for("browse.grower_detail", grower_id=grower_id))
