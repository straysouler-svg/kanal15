"""One-off: nameless foreign drivers passing by, one line in their own language (reactions.foreign.<lang>).
They are 'extra' actors: not simulated on the highway, not in the deck, can't be called by name."""
import json
from pathlib import Path

F = Path(__file__).resolve().parents[1] / "phrases" / "level3_eleven.json"
d = json.loads(F.read_text(encoding="utf-8"))
X = {
    "de": ("ash", "немецкий дальнобойщик средних лет, деловитый, говорит быстро", [
        "Achtung, Kollegen, Polizei hinter der Brücke!", "Guten Abend, Kanal. Alles ruhig hier.",
        "Schon wieder Stau. Na toll."]),
    "pl": ("echo", "польский водитель фуры, весёлый, говорит быстро и по-свойски", [
        "Dzień dobry, panowie, jak tam droga?", "Uwaga, policja na parkingu, z radarem!",
        "Znowu korek. Szerokiej drogi, panowie!"]),
    "fr": ("verse", "французский водитель грузовика, лёгкий, с юмором", [
        "Salut les routiers, ça roule?", "Attention, contrôle de police après le pont!", "Bonne route, les gars!"]),
    "es": ("ballad", "испанский водитель грузовика, эмоциональный и громкий", [
        "Hola, compañeros, ¿qué tal la carretera?", "Cuidado, radar a la salida del pueblo.", "Buen viaje, amigos."]),
    "it": ("onyx", "итальянский водитель грузовика, темпераментный, жестикулирует голосом", [
        "Ciao ragazzi, tutto bene sulla strada?", "Attenzione, polizia dopo il ponte!", "Buon viaggio a tutti!"]),
    "nl": ("alloy", "нидерландский водитель грузовика, спокойный, дружелюбный", [
        "Goedenavond, collega's. Rustig op de weg?", "Pas op, flitser na de brug!", "Goede reis, jongens!"]),
    "cs": ("sage", "чешская водительница грузовика, приветливая", [
        "Ahoj, kluci, jak je na silnici?", "Pozor, policie za mostem!", "Šťastnou cestu!"]),
}
fg = d["reactions"].setdefault("foreign", {"_": "foreign passers-by: one line in their language; the language "
                                                "follows the country you drive in (sometimes an international "
                                                "truck from elsewhere)."})
for lang, (voice, style, lines) in X.items():
    key = "x_" + lang
    d["actors"].setdefault(key, {
        "name": f"иностранец ({lang})", "extra": True, "lang": lang, "engine": "gpt-audio", "voice": voice,
        "voice_id": f"gpt-audio:{voice}:{lang}", "style": style,
        "radio": {"noise_db": -27, "drive": 2.0, "roger_beep": False},
        "cab": {"_": "проезжий", "road_db": -18, "window": 0.5, "wind_db": -21, "traffic": 0.1, "traffic_db": -18,
                "horn_chance": 0.1, "engine_db": -25, "rpm": 1450},
        "phrases": []})
    lst = fg.setdefault(lang, [])
    for t in lines:
        if {"actor": key, "text": t} not in lst:
            lst.append({"actor": key, "text": t})

src = Path(__file__).with_name("add_night_cast.py").read_text(encoding="utf-8")
ns = {"json": json}
exec(src[src.index("def dump("):src.index("F.write_text(")], ns)
F.write_text(ns["dump"](d) + "\n", encoding="utf-8")
json.loads(F.read_text(encoding="utf-8"))
print("foreign:", {k: len(v) for k, v in fg.items() if not k.startswith("_")})
