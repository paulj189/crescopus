from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.extensions import get_supabase
from app.utils import login_required, current_profile

connection_requests_bp = Blueprint(
    "connection_requests", __name__, url_prefix="/connect", template_folder="../templates/connection_requests"
)


def connection_state(supabase, listing_id, grower_id, viewer_id):
    """Where this grower and this app stand, from the viewer's side:
    open (a live partnership), sent (the viewer's request is waiting),
    incoming (the other person's request is waiting for the viewer) or connect."""
    live = (supabase.table("partnerships").select("id")
            .eq("listing_id", listing_id).eq("grower_id", grower_id)
            .in_("status", ["trial", "formalised"]).execute().data)
    if live:
        return {"kind": "open", "partnership_id": live[0]["id"]}
    pending = (supabase.table("connection_requests").select("*")
               .eq("listing_id", listing_id).eq("grower_id", grower_id)
               .eq("status", "pending").order("created_at", desc=True).execute().data)
    if pending:
        req = pending[0]
        return {"kind": "sent" if req["initiated_by"] == viewer_id else "incoming", "request": req}
    return {"kind": "connect"}


def _already_connected(state, listing, grower=None):
    """The page to show instead of the intro form when a request or plan already exists."""
    if state["kind"] == "open":
        flash("You already have a CrescoPlan together.", "success")
        return redirect(url_for("plans.view", partnership_id=state["partnership_id"]))
    if state["kind"] == "incoming":
        flash("They've already asked to start a CrescoPlan with you. You can accept it here.", "success")
        return redirect(url_for("connection_requests.respond", request_id=state["request"]["id"]))
    if state["kind"] == "sent":
        return render_template("connection_requests/sent.html", req=state["request"], listing=listing, grower=grower)
    return None


@connection_requests_bp.route("/listing/<listing_id>/new", methods=["GET", "POST"])
@login_required
def new_from_listing(listing_id):
    """A grower reaches out to a builder about one of the builder's listings."""
    profile = current_profile()
    if not profile or not profile.get("is_grower"):
        flash("Only grower accounts can send a connection request.", "error")
        return redirect(url_for("listings.detail", listing_id=listing_id))

    supabase = get_supabase()
    listing = supabase.table("listings").select("*").eq("id", listing_id).single().execute().data
    if listing.get("withdrawn_at"):
        flash("This app has been withdrawn from Crescopus, so it isn't taking new connections.", "error")
        return redirect(url_for("browse.index"))
    if profile.get("grower_withdrawn_at"):
        flash("Your card is withdrawn. Restore it from your dashboard to send connection requests.", "error")
        return redirect(url_for("dashboard.index"))

    page = _already_connected(connection_state(supabase, listing_id, profile["id"], profile["id"]), listing)
    if page:
        return page

    if request.method == "POST":
        if not request.form.get("consent_acknowledged"):
            flash("Please confirm you understand Crescopus's role before sending this.", "error")
            return render_template("connection_requests/new.html", listing=listing)

        supabase.table("connection_requests").insert({
            "listing_id": listing_id,
            "grower_id": profile["id"],
            "initiated_by": profile["id"],
            "message": request.form["message"],
            "status": "pending",
        }).execute()
        flash("Request sent.", "success")
        return redirect(url_for("connection_requests.new_from_listing", listing_id=listing_id))

    return render_template("connection_requests/new.html", listing=listing)


@connection_requests_bp.route("/grower/<grower_id>/listing/<listing_id>/new", methods=["GET", "POST"])
@login_required
def new_from_grower(grower_id, listing_id):
    """A builder reaches out to a grower about one of their own listings."""
    profile = current_profile()
    supabase = get_supabase()
    listing = supabase.table("listings").select("*").eq("id", listing_id).single().execute().data

    if not profile or not listing or listing["developer_id"] != profile["id"]:
        flash("Only the listing's developer can reach out about it.", "error")
        return redirect(url_for("growers.detail", grower_id=grower_id))

    grower = supabase.table("profiles").select("*").eq("id", grower_id).single().execute().data
    if listing.get("withdrawn_at"):
        flash("That app card is withdrawn. Restore it from your dashboard to send connection requests about it.", "error")
        return redirect(url_for("dashboard.index"))
    if grower.get("grower_withdrawn_at"):
        flash("This grower has withdrawn their card from Crescopus, so they aren't taking new connections.", "error")
        return redirect(url_for("browse.index", tab="growers"))

    page = _already_connected(connection_state(supabase, listing_id, grower_id, profile["id"]), listing, grower)
    if page:
        return page

    if request.method == "POST":
        if not request.form.get("consent_acknowledged"):
            flash("Please confirm you understand Crescopus's role before sending this.", "error")
            return render_template("connection_requests/new.html", listing=listing, grower=grower)

        supabase.table("connection_requests").insert({
            "listing_id": listing_id,
            "grower_id": grower_id,
            "initiated_by": profile["id"],
            "message": request.form["message"],
            "status": "pending",
        }).execute()
        flash("Request sent.", "success")
        return redirect(url_for("connection_requests.new_from_grower", grower_id=grower_id, listing_id=listing_id))

    return render_template("connection_requests/new.html", listing=listing, grower=grower)


@connection_requests_bp.route("/<request_id>/respond", methods=["GET"])
@login_required
def respond(request_id):
    supabase = get_supabase()
    req = supabase.table("connection_requests").select("*").eq("id", request_id).single().execute().data
    listing = supabase.table("listings").select("*").eq("id", req["listing_id"]).single().execute().data
    grower = supabase.table("profiles").select("*").eq("id", req["grower_id"]).single().execute().data
    sender = supabase.table("profiles").select("*").eq("id", req["initiated_by"]).single().execute().data

    profile = current_profile()
    recipient_id = listing["developer_id"] if req["initiated_by"] == req["grower_id"] else req["grower_id"]

    if not profile or profile["id"] != recipient_id:
        flash("This connection request isn't addressed to you.", "error")
        return redirect(url_for("dashboard.index"))

    if req["status"] == "withdrawn":
        flash(f"{sender['full_name']} withdrew this request.", "error")
        return redirect(url_for("dashboard.index"))
    return render_template("connection_requests/respond.html", req=req, listing=listing, grower=grower, sender=sender)


@connection_requests_bp.route("/<request_id>/accept", methods=["POST"])
@login_required
def accept(request_id):
    supabase = get_supabase()
    req = supabase.table("connection_requests").select("*").eq("id", request_id).single().execute().data
    listing = supabase.table("listings").select("*").eq("id", req["listing_id"]).single().execute().data

    profile = current_profile()
    recipient_id = listing["developer_id"] if req["initiated_by"] == req["grower_id"] else req["grower_id"]
    if not profile or profile["id"] != recipient_id:
        flash("This connection request isn't addressed to you.", "error")
        return redirect(url_for("dashboard.index"))

    if req["status"] != "pending":
        flash("This request was withdrawn by the person who sent it." if req["status"] == "withdrawn"
              else "This connection request has already been responded to.", "error")
        return redirect(url_for("dashboard.index"))

    supabase.table("connection_requests").update({"status": "accepted"}).eq("id", request_id).execute()

    result = supabase.table("partnerships").insert({
        "listing_id": req["listing_id"],
        "connection_request_id": request_id,
        "grower_id": req["grower_id"],
        "developer_id": listing["developer_id"],
        "status": "trial",
    }).execute()

    partnership_id = result.data[0]["id"]
    flash("You're now connected. Start your CrescoPlan together, or say hello in Messages.", "success")
    return redirect(url_for("plans.view", partnership_id=partnership_id))


@connection_requests_bp.route("/<request_id>/withdraw", methods=["POST"])
@login_required
def withdraw(request_id):
    """The person who sent a request takes it back before it's answered."""
    supabase = get_supabase()
    rows = supabase.table("connection_requests").select("*").eq("id", request_id).execute().data
    profile = current_profile()
    if not rows or not profile or rows[0]["initiated_by"] != profile["id"]:
        flash("Only the person who sent a request can withdraw it.", "error")
        return redirect(url_for("dashboard.index"))
    if rows[0]["status"] != "pending":
        flash("This request has already been answered, so it can't be withdrawn.", "error")
        return redirect(url_for("dashboard.index"))
    supabase.table("connection_requests").update({"status": "withdrawn"}).eq("id", request_id).execute()
    flash("Request withdrawn.", "success")
    return redirect(url_for("dashboard.index"))


@connection_requests_bp.route("/<request_id>/reject", methods=["POST"])
@login_required
def reject(request_id):
    supabase = get_supabase()
    req = supabase.table("connection_requests").select("*").eq("id", request_id).single().execute().data
    listing = supabase.table("listings").select("*").eq("id", req["listing_id"]).single().execute().data

    profile = current_profile()
    recipient_id = listing["developer_id"] if req["initiated_by"] == req["grower_id"] else req["grower_id"]
    if not profile or profile["id"] != recipient_id:
        flash("This connection request isn't addressed to you.", "error")
        return redirect(url_for("dashboard.index"))

    if req["status"] != "pending":
        flash("This request was withdrawn by the person who sent it." if req["status"] == "withdrawn"
              else "This connection request has already been responded to.", "error")
        return redirect(url_for("dashboard.index"))

    supabase.table("connection_requests").update({
        "status": "rejected",
        "reject_reason": request.form.get("reject_reason"),
    }).eq("id", request_id).execute()

    flash("Connection request declined.", "success")
    return redirect(url_for("dashboard.index"))
