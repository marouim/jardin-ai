import os
import requests
from flask import Flask, jsonify
from openai import OpenAI

app = Flask(__name__)

# Config depuis les variables d’environnement
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SONDE_IP = os.getenv("SONDE_IP")
VALEUR_SEC = float(os.getenv("VALEUR_SEC", "850"))
VALEUR_HUMIDE = float(os.getenv("VALEUR_HUMIDE", "400"))
SEUIL_ARROSAGE = float(os.getenv("SEUIL_ARROSAGE", "30"))
PORT = int(os.getenv("PORT", "5000"))

# Pour OpenWeatherMap
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
LAT = os.getenv("LAT")
LON = os.getenv("LON")

# Client OpenAI
client = OpenAI(api_key=OPENAI_API_KEY)

def get_humidite():
    url = f"http://{SONDE_IP}/read"
    r = requests.get(url, timeout=5)
    r.raise_for_status()
    analog_value = r.json().get("analogValue")
    if analog_value is None:
        raise ValueError("Valeur analogique manquante")
    humidite = round((VALEUR_SEC - analog_value) / (VALEUR_SEC - VALEUR_HUMIDE) * 100, 2)
    print("Humidité", humidite)
    return humidite

def va_pleuvoir_dans_12h():
    print("OpenWeatherMap")
    url = f"https://api.openweathermap.org/data/2.5/forecast?lat={LAT}&lon={LON}&appid={WEATHER_API_KEY}&units=metric"
    r = requests.get(url, timeout=5)
    r.raise_for_status()
    data = r.json()
    for heure in data.get("hourly", [])[:12]:
        if "rain" in heure and heure["rain"].get("1h", 0) > 0:
            print("Il pleut dans les prochaines heures")
            return True
    return False

def decision_par_openai(humidite, va_pleuvoir):
    print("OpenAI")
    prompt = (
        f"Le taux d'humidité du sol est de {humidite} %.\n"
        f"Il {'va' if va_pleuvoir else 'ne va pas'} pleuvoir dans les 12 prochaines heures.\n"
        f"Basé sur les prédictions météo, le taux d'humidité dans l'air, \n"
        "Doit-on arroser le jardin ? Réponds uniquement en JSON sous la forme {\"arrosage\": \"oui/non\", \"duree\": minutes}."
    )
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Tu es un assistant d’arrosage de jardin intelligent."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )
    print(response.choices)
    return response.choices[0].message.content.strip()

@app.route("/arrosage", methods=["GET"])
def calcul_arrosage():
    try:
        humidite = get_humidite()
        pluie_attendue = va_pleuvoir_dans_12h()

        if humidite >= SEUIL_ARROSAGE:
            return jsonify({
                "humidite": humidite,
                "arrosage": "non",
                "raison": f"Taux d’humidité suffisant ({humidite} %)"
            })

        if pluie_attendue:
            return jsonify({
                "humidite": humidite,
                "arrosage": "non",
                "raison": "Le sol est sec, mais il va pleuvoir sous peu"
            })

        # Sinon, on délègue à OpenAI
        gpt_response = decision_par_openai(humidite, pluie_attendue)
        return gpt_response, 200, {"Content-Type": "application/json"}

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
