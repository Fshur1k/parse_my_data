import requests
import json

# Це відкрите API Leaguepedia, токени не потрібні!
url = "https://lol.fandom.com/api.php"

# Пишемо "запит", схожий на SQL, щоб витягнути потрібні колонки з таблиці ScoreboardGames
params = {
    "action": "cargoquery",
    "format": "json",
    "tables": "ScoreboardGames=SG",
    # Вибираємо колонки: Турнір, Дата, Команди, Вбивства, Час, First Blood, Перша Вежа, Дракони тощо
    "fields": "SG.Tournament, SG.DateTime_UTC, SG.Team1, SG.Team2, SG.Winner, SG.Team1Kills, SG.Team2Kills, SG.Gamelength_Number, SG.FirstBlood, SG.FirstTower, SG.Team1Dragons, SG.Team2Dragons",
    # Фільтруємо, наприклад, лігу LPL у 2026 році (або 2024, якщо поточний сезон)
    "where": "SG.Tournament LIKE '%LPL%'",
    "order_by": "SG.DateTime_UTC DESC", # Сортуємо від найсвіжіших
    "limit": "3" # Беремо 3 останні карти
}

print("Роблю запит до Leaguepedia...")
response = requests.get(url, params=params)

if response.status_code == 200:
    data = response.json()
    games = data.get("cargoquery", [])
    
    for item in games:
        game = item["title"]
        print(f"\n--- {game['Tournament']} | {game['DateTime_UTC']} ---")
        print(f"Матч: {game['Team1']} vs {game['Team2']}")
        print(f"Рахунок вбивств: {game['Team1Kills']} - {game['Team2Kills']}")
        print(f"Тривалість (хвилин): {game['Gamelength_Number']}")
        print(f"First Blood: Команда {game['FirstBlood']}")
        print(f"Перша Вежа: Команда {game['FirstTower']}")
        print(f"Дракони: {game['Team1']} ({game['Team1Dragons']}) - {game['Team2']} ({game['Team2Dragons']})")
else:
    print(f"Помилка {response.status_code}")