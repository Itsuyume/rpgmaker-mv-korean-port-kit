"""The sole core display-selection allowlist; no language-dependent monkeypatch."""
DISPLAY_COMMAND_FIELDS = {
    401: (0, "dialogue"), 405: (0, "scrolling_text"),
    320: (1, "actor_name_change"), 324: (1, "actor_nickname_change"),
    325: (1, "actor_profile_change"),
}
DATABASE_FIELDS = {
    "Actors.json": ("name", "nickname", "profile"),
    "Armors.json": ("name", "description"), "Classes.json": ("name",),
    "Enemies.json": ("name",), "Items.json": ("name", "description"),
    "Skills.json": ("name", "description", "message1", "message2"),
    "States.json": ("name", "message1", "message2", "message3", "message4"),
    "Weapons.json": ("name", "description"),
}
SYSTEM_ARRAYS = ("armorTypes", "elements", "equipTypes", "skillTypes", "weaponTypes")
SYSTEM_SCALARS = ("currencyUnit", "gameTitle")
