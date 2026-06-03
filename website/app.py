from flask import Flask, render_template, request, redirect, url_for
import json
import os

app = Flask(__name__)

def load_config(guild_id):
    try:
        with open(f"../configs/{guild_id}.json", "r") as f:
            return json.load(f)
    except:
        return {}

def save_config(guild_id, data):
    os.makedirs("../configs", exist_ok=True)
    with open(f"../configs/{guild_id}.json", "w") as f:
        json.dump(data, f, indent=2)

# DASHBOARD HOME
@app.route("/dashboard/<guild_id>")
def dashboard(guild_id):
    cfg = load_config(guild_id)
    return render_template("dashboard.html", guild_id=guild_id, config=cfg)

# UPDATE SETTINGS
@app.route("/update/<guild_id>", methods=["POST"])
def update(guild_id):
    cfg = load_config(guild_id)
    # Anti-Raid
    cfg["anti_raid"]["enabled"] = request.form.get("anti_raid_enabled") == "on"
    cfg["anti_raid"]["join_limit"] = int(request.form.get("join_limit", 5))
    cfg["anti_raid"]["action"] = request.form.get("raid_action", "ban")
    # AutoMod / Anti-Spam
    cfg["automod"]["enabled"] = request.form.get("automod_enabled") == "on"
    cfg["automod"]["spam_threshold"] = int(request.form.get("spam_threshold", 5))
    cfg["automod"]["invite_block"] = request.form.get("invite_block") == "on"
    # Anti-Nuke
    cfg["anti_nuke"]["enabled"] = request.form.get("anti_nuke_enabled") == "on"
    cfg["anti_nuke"]["panic_mode"] = request.form.get("panic_mode") == "on"
    # Join Gate
    cfg["join_gate"]["enabled"] = request.form.get("join_gate_enabled") == "on"
    cfg["join_gate"]["min_account_age_days"] = int(request.form.get("min_age", 7))
    # Verification
    cfg["verification"]["enabled"] = request.form.get("verification_enabled") == "on"

    save_config(guild_id, cfg)
    return redirect(url_for("dashboard", guild_id=guild_id))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
    
