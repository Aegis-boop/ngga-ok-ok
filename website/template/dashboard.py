<!DOCTYPE html>
<html>
<head>
    <title>Aizen Dashboard</title>
    <style>
        * { font-family: Arial; margin:0; padding:0; box-sizing:border-box; }
        body { background:#1a1a1a; color:#fff; display:flex; }
        .sidebar { width:250px; background:#222; height:100vh; padding:20px; }
        .sidebar h2 { color:#2ecc71; margin-bottom:30px; }
        .sidebar a { display:block; color:#ccc; padding:12px; text-decoration:none; margin:5px 0; border-radius:5px; }
        .sidebar a:hover, .sidebar a.active { background:#2ecc71; color:#000; }
        .content { flex:1; padding:30px; }
        .card { background:#222; padding:25px; border-radius:10px; margin-bottom:20px; }
        input, select, button { padding:8px; margin:8px 0; width:100%; background:#333; color:#fff; border:none; border-radius:4px; }
        button { background:#2ecc71; cursor:pointer; font-weight:bold; }
    </style>
</head>
<body>
    <div class="sidebar">
        <h2>🛡️ Aizen</h2>
        <a href="#" class="active">Overview</a>
        <a href="#">Auto Mod</a>
        <a href="#">Anti Nuke</a>
        <a href="#">Anti Raid</a>
        <a href="#">Join Gate</a>
        <a href="#">Verification</a>
        <a href="#">Logging</a>
        <a href="#">Backups</a>
        <a href="#">Lockdown</a>
    </div>
    <div class="content">
        <h1>⚙️ Server Settings</h1>
        <form method="POST" action="/update/{{ guild_id }}">
            <div class="card">
                <h3>🚨 Anti Raid</h3>
                <label><input type="checkbox" name="anti_raid_enabled" {% if config.anti_raid.enabled %}checked{% endif %}> Enable Anti Raid</label>
                <p>Join limit: <input type="number" name="join_limit" value="{{ config.anti_raid.join_limit }}"></p>
                <p>Action: <select name="raid_action"><option value="ban" {% if config.anti_raid.action=='ban' %}selected{% endif %}>Ban</option><option value="kick" {% if config.anti_raid.action=='kick' %}selected{% endif %}>Kick</option></select></p>
            </div>

            <div class="card">
                <h3>⚙️ Auto Mod / Anti Spam</h3>
                <label><input type="checkbox" name="automod_enabled" {% if config.automod.enabled %}checked{% endif %}> Enable Auto Mod</label>
                <p>Spam threshold: <input type="number" name="spam_threshold" value="{{ config.automod.spam_threshold }}"></p>
                <label><input type="checkbox" name="invite_block" {% if config.automod.invite_block %}checked{% endif %}> Block Invites</label>
            </div>

            <div class="card">
                <h3>🛡️ Anti Nuke</h3>
                <label><input type="checkbox" name="anti_nuke_enabled" {% if config.anti_nuke.enabled %}checked{% endif %}> Enable Anti Nuke</label>
                <label><input type="checkbox" name="panic_mode" {% if config.anti_nuke.panic_mode %}checked{% endif %}> Panic Mode</label>
            </div>

            <div class="card">
                <h3>🚪 Join Gate</h3>
                <label><input type="checkbox" name="join_gate_enabled" {% if config.join_gate.enabled %}checked{% endif %}> Enable Join Gate</label>
                <p>Min account age (days): <input type="number" name="min_age" value="{{ config.join_gate.min_account_age_days }}"></p>
            </div>

            <div class="card">
                <h3>✅ Verification</h3>
                <label><input type="checkbox" name="verification_enabled" {% if config.verification.enabled %}checked{% endif %}> Enable Verification</label>
            </div>

            <button type="submit">💾 SAVE ALL SETTINGS</button>
        </form>
    </div>
</body>
                         </html>
                         
