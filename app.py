import os
import requests
from flask import Flask, jsonify
from openai import OpenAI
from datetime import datetime, timedelta, timezone

app = Flask(__name__)

# Config depuis les variables d’environnement
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
SONDE_IP = os.getenv("SONDE_IP", "")
VALEUR_SEC = float(os.getenv("VALEUR_SEC", "850"))
VALEUR_HUMIDE = float(os.getenv("VALEUR_HUMIDE", "400"))
SEUIL_ARROSAGE = float(os.getenv("SEUIL_ARROSAGE", "30"))
PORT = int(os.getenv("PORT", "8080"))
USE_CASE = os.getenv("USE_CASE", "jardin")

# Pour OpenWeatherMap
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "")
LAT = os.getenv("LAT", "")
LON = os.getenv("LON", "")

# Client OpenAI
if OPENAI_API_KEY != "":
    client = OpenAI(api_key=OPENAI_API_KEY)

def get_humidite():
    print("Lecture sonde humidite")
    if SONDE_IP != "":
        url = f"http://{SONDE_IP}/read"
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        analog_value = r.json().get("analogValue")
        if analog_value is None:
            raise ValueError("Valeur analogique manquante")
        humidite = round((VALEUR_SEC - analog_value) / (VALEUR_SEC - VALEUR_HUMIDE) * 100, 2)
        print(" => Humidité: \033[94m" + str(humidite) + "\033[0m")
        return humidite
    else:
        print(" => Sonde humidité \033[91mabsente\033[0m")
        return -1

def convert_utc_to_local(utc_timestamp, timezone_offset_seconds):
    # Crée un datetime UTC "aware"
    utc_dt = datetime.fromtimestamp(utc_timestamp, tz=timezone.utc)
    # Applique le décalage horaire pour obtenir l'heure locale
    local_dt = utc_dt + timedelta(seconds=timezone_offset_seconds)
    return local_dt

def va_pleuvoir_dans_12h():
    print("Service OpenWeatherMap")

    if WEATHER_API_KEY != "":
        url = f"https://api.openweathermap.org/data/2.5/forecast?lat={LAT}&lon={LON}&appid={WEATHER_API_KEY}&units=metric"
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        data = r.json()
        mm_pluie = 0

        # Chaque entrée représente une prévision toutes les 3 heures => 4 entrées pour 12h
        for heure in data.get("list", [])[:4]:
            pluie = heure.get("rain", {}).get("3h", 0)
            local_dt = convert_utc_to_local(heure["dt"], data["city"]["timezone"])

            print(" => Heure: " + local_dt.strftime('%Y-%m-%d %H:%M'))
            print(" ...Ville: " + data["city"]["name"])
            print(" ...Pluie: \033[94m" + str(pluie) + "mm\033[0m")
            mm_pluie = mm_pluie + pluie
        
        print(" => Total pluie 12h: \033[94m" + str(round(mm_pluie,2)) + "mm\033[0m")
        return round(mm_pluie,2)
    else:
        print(" => Service OpenWeatherMap \033[91mdésactivé. Cle absente.\033[0m")
        return -1

def decision_par_openai(humidite, va_pleuvoir):
    print("Service OpenAI")

    if OPENAI_API_KEY != "":
        prompt = (
            f"Le taux d'humidité du sol est de {humidite} %.\n"
            f"Il va pleuvoir {va_pleuvoir} mm dans les 12 prochaines heures.\n"
            f"Basé sur les prédictions météo,\n"
            "Doit-on arroser le " + USE_CASE + " ? Réponds uniquement en JSON (sans balises ```) sous la forme {\"arrosage\": \"oui/non\", \"duree\": minutes, \"pluie\": pluie attendue en mm, \"humidite\": humidite au sol, \"raison\": raison en 15 mots max}."
        )
        print(" => Prompt AI: " + prompt)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Tu es un assistant d’arrosage de " + USE_CASE + " intelligent."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        print(" => Réponse: " + response.choices[0].message.content.strip())
        return response.choices[0].message.content.strip()
    else:
        print(" => Service OpenAI desactive. Cle absente.")
        return jsonify({
                "humidite": humidite,
                "arrosage": "non",
                "pluie": va_pleuvoir,
                "raison": "Service OpenAI desactive. Cle absente."
            })
    
@app.route("/arrosage", methods=["GET"])
def calcul_arrosage():
    try:
        humidite = get_humidite()
        pluie_attendue = va_pleuvoir_dans_12h()

        if humidite == -1:
            return jsonify({
                "humidite": humidite,
                "arrosage": "non",
                "pluie": pluie_attendue,
                "raison": "Sonde humidite absente."
            })
        
        if humidite >= SEUIL_ARROSAGE:
            return jsonify({
                "humidite": humidite,
                "arrosage": "non",
                "pluie": pluie_attendue,
                "raison": f"Taux d’humidité suffisant ({humidite} %)"
            })

        if pluie_attendue == -1:
            return jsonify({
                "humidite": humidite,
                "arrosage": "non",
                "pluie": pluie_attendue,
                "raison": "Service OpenWeatherMap désactivé. Clé absente."
            })
        
        # Délègue à OpenAI
        gpt_response = decision_par_openai(humidite, pluie_attendue)
        return gpt_response, 200, {"Content-Type": "application/json"}

    except Exception as e:
        return jsonify({"error": str(e)}), 500

def service_check():
    print("Verification des services requis par Jardin-AI")
    if OPENAI_API_KEY != "":
        print(" => Service OpenAI: \033[92mactif\033[0m")
    else:
        print(" => Service OpenAI: \033[91mdésactivé. Clé absente\033[0m")
        
    if WEATHER_API_KEY != "":
        print(" => Service OpenWeatherMap: \033[92mactif\033[0m")
    else:
        print(" => Service OpenWeatherMap: \033[91mdésactivé. Clé absente\033[0m")

    if SONDE_IP != "":
        print(" => Sonde humidite:  \033[92mactive [" + SONDE_IP + "]\033[0m")
    else:
        print(" => Sonde humidite \033[91mdésactivée. Adresse IP absente\033[0m")
    
if __name__ == "__main__":
    service_check()
    app.run(host="0.0.0.0", port=PORT)
