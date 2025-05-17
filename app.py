import os
import requests
from flask import Flask, jsonify
from openai import OpenAI
from datetime import datetime, timedelta, timezone

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

def convert_utc_to_local(utc_timestamp, timezone_offset_seconds):
    # Crée un datetime UTC "aware"
    utc_dt = datetime.fromtimestamp(utc_timestamp, tz=timezone.utc)
    # Applique le décalage horaire pour obtenir l'heure locale
    local_dt = utc_dt + timedelta(seconds=timezone_offset_seconds)
    return local_dt

def va_pleuvoir_dans_12h():
    print("OpenWeatherMap")
    url = f"https://api.openweathermap.org/data/2.5/forecast?lat={LAT}&lon={LON}&appid={WEATHER_API_KEY}&units=metric"
    r = requests.get(url, timeout=5)
    r.raise_for_status()
    data = r.json()
    mm_pluie = 0

    # Chaque entrée représente une prévision toutes les 3 heures => 4 entrées pour 12h
    for heure in data.get("list", [])[:4]:
        pluie = heure.get("rain", {}).get("3h", 0)
        local_dt = convert_utc_to_local(heure["dt"], data["city"]["timezone"])

        print("Ville: " + data["city"]["name"])
        print("Heure: " + local_dt.strftime('%Y-%m-%d %H:%M'))
        print("Pluit " + str(pluie) + "mm")
        mm_pluie = mm_pluie + pluie
    
    return mm_pluie


def decision_par_openai(humidite, va_pleuvoir):
    print("OpenAI")
    prompt = (
        f"Le taux d'humidité du sol est de {humidite} %.\n"
        f"Il va pleuvoir {va_pleuvoir} mm dans les 12 prochaines heures.\n"
        f"Basé sur les prédictions météo, le taux d'humidité dans l'air, \n"
        "Doit-on arroser le jardin ? Réponds uniquement en JSON sous la forme {\"arrosage\": \"oui/non\", \"duree\": minutes, \"raison\": raison en 10 mots max}."
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

        print("Humidite: " + str(humidite))
        print("pluie_attendue: " + str(pluie_attendue) + "mm")

        if humidite >= SEUIL_ARROSAGE:
            return jsonify({
                "humidite": humidite,
                "arrosage": "non",
                "raison": f"Taux d’humidité suffisant ({humidite} %)"
            })

        # if pluie_attendue:
        #     return jsonify({
        #         "humidite": humidite,
        #         "arrosage": "non",
        #         "raison": "Le sol est sec, mais il va pleuvoir sous peu"
        #     })

        # Sinon, on délègue à OpenAI
        gpt_response = decision_par_openai(humidite, pluie_attendue)
        return gpt_response, 200, {"Content-Type": "application/json"}

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
