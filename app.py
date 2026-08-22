import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
import os

st.set_page_config(page_title="LoL Esports Auto-Exporter", layout="wide")

# ==========================================
# ⚙️ НАЛАШТУВАННЯ ЗА ЗАМОВЧУВАННЯМ
# ==========================================
# Ваше посилання на файл у Google Диску
# Замінюємо Google Drive на прямий сервер Oracle's Elixir
DEFAULT_GDRIVE_LINK = "https://oracleselixir-downloadable-match-data.s3-us-west-2.amazonaws.com/2026_LoL_esports_match_data_from_OraclesElixir.csv"
# Вставте ваші сталі дані Google Таблиці
DEFAULT_SHEET_URL = "https://docs.google.com/spreadsheets/d/1kjn9qTW1tgMNtqRwYCg0bQBWvjC9pJ6K-LZ6-G2o274/edit?gid=0#gid=0"
DEFAULT_SHEET_NAME = "Sheets1"

# Ініціалізація стану сесії, щоб URL та назва аркуша не зникали при взаємодії
if 'sheet_url' not in st.session_state:
    st.session_state['sheet_url'] = DEFAULT_SHEET_URL
if 'sheet_name' not in st.session_state:
    st.session_state['sheet_name'] = DEFAULT_SHEET_NAME

# ==========================================
# 1. ДОПОМІЖНІ ФУНКЦІЇ ТА СЕРВІСИ
# ==========================================
def convert_gdrive_url(url: str) -> str:
    """Перетворює посилання Google Диску на пряме посилання завантаження CSV"""
    match = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
    if match:
        file_id = match.group(1)
        return f'https://drive.google.com/uc?export=download&id={file_id}'
    return url

def get_gspread_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    # Беремо дані не з файлу, а зі схованого середовища Streamlit Secrets
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

def append_to_sheet(spreadsheet_url, sheet_name, data_rows):
    """Відправка готових карт у Google Таблицю"""
    try:
        client = get_gspread_client()
        sheet = client.open_by_url(spreadsheet_url).worksheet(sheet_name)
        
        existing_data = sheet.get_all_values()
        if not existing_data:
            headers = [
                'Patch', 'Date', 'Match start time', 'Tournament', 'Map number',
                'Team 1', 'Team 2', 'Team 1 baseline (%)', 'Map winner',
                'Team 1 kills', 'Team 2 kills', 'Total kills', 'Total minutes',
                'FB', 'F10', '1st tower', 'Total towers', '1st dragon',
                'Total dragons', '1st nashor', 'Total nashors', '1st inhibitor',
                'Total inhibitors', 'Last pick map winner', 'Red side map winner'
            ]
            sheet.append_row(headers)
        
        initial_count = len(sheet.get_all_values())
        rows_to_insert = [list(row.values()) for row in data_rows]
        sheet.append_rows(rows_to_insert)
            
        final_count = len(sheet.get_all_values())
        if final_count == initial_count + len(data_rows):
            return True, f"Успішно додано {len(data_rows)} карт(и) у Google Sheets!"
        else:
            return False, "Помилка запису: кількість рядків у таблиці не збігається."
            
    except Exception as e:
        return False, f"Помилка доступу до Google Sheets: {str(e)}"

def parse_selected_games(df_games):
    """Обробка всіх карт для кожного з обраних матчів"""
    parsed_rows = []
    grouped_matches = df_games.groupby('gameid')
    
    for game_id, match_data in grouped_matches:
        maps = match_data.groupby('game')
        
        for map_num, map_data in maps:
            blue = map_data[map_data['side'] == 'Blue'].iloc[0]
            red = map_data[map_data['side'] == 'Red'].iloc[0]
            
            team1 = blue['teamname']
            team2 = red['teamname']
            
            map_winner = team1 if blue['result'] == 1 else team2
            t1_kills = int(blue['kills'])
            t2_kills = int(red['kills'])
            
            # --- Логіка F10 (Перші 10 вбивств) ---
            if t1_kills >= 10 and t2_kills < 10:
                f10 = team1
            elif t2_kills >= 10 and t1_kills < 10:
                f10 = team2
            elif t1_kills < 10 and t2_kills < 10:
                f10 = 'None' # Жодна команда не досягла 10 вбивств
            else:
                f10 = 'N/A'  # Обидві команди мають 10+, потрібен таймлайн для визначення
                
            fb = team1 if blue['firstblood'] == 1 else (team2 if red['firstblood'] == 1 else 'None')
            f_tower = team1 if blue['firsttower'] == 1 else (team2 if red['firsttower'] == 1 else 'None')
            f_dragon = team1 if blue['firstdragon'] == 1 else (team2 if red['firstdragon'] == 1 else 'None')
            f_nashor = team1 if blue['firstbaron'] == 1 else (team2 if red['firstbaron'] == 1 else 'None')
            
            # --- Логіка First Inhibitor ---
            blue_first_inhib = blue.get('firstinhibitor', 0)
            red_first_inhib = red.get('firstinhibitor', 0)
            
            blue_inhib_count = int(blue.get('inhibitors', 0))
            red_inhib_count = int(red.get('inhibitors', 0))
            
            if blue_first_inhib == 1:
                f_inhib = team1
            elif red_first_inhib == 1:
                f_inhib = team2
            # Якщо немає прапорця firstinhibitor, але хтось знищив інгібітор, а інший - ні
            elif blue_inhib_count > 0 and red_inhib_count == 0:
                f_inhib = team1
            elif red_inhib_count > 0 and blue_inhib_count == 0:
                f_inhib = team2
            else:
                f_inhib = 'None'
            
            red_won = "YES" if red['result'] == 1 else "NO"
            
            date_str = str(blue['date'])
            date_part = date_str.split(' ')[0] if ' ' in date_str else date_str
            time_part = date_str.split(' ')[1] if ' ' in date_str else '12:00:00'
            
            # --- Форматування Patch (через крапку) ---
            patch_str = str(blue.get('patch', '')).replace(',', '.')
            
            # --- Форматування Total minutes (MM:SS) ---
            total_seconds = int(blue.get('gamelength', 0))
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            time_str = f"{minutes:02d}:{seconds:02d}"
            
            parsed_rows.append({
                'Patch': patch_str,
                'Date': date_part,
                'Match start time': time_part,
                'Tournament': blue['league'],
                'Map number': int(map_num),
                'Team 1': team1,
                'Team 2': team2,
                'Team 1 baseline (%)': '50%',
                'Map winner': map_winner,
                'Team 1 kills': t1_kills,
                'Team 2 kills': t2_kills,
                'Total kills': t1_kills + t2_kills,
                'Total minutes': time_str,
                'FB': fb,
                'F10': f10,
                '1st tower': f_tower,
                'Total towers': int(blue['towers'] + red['towers']),
                '1st dragon': f_dragon,
                'Total dragons': int(blue['dragons'] + red['dragons']),
                '1st nashor': f_nashor,
                'Total nashors': int(blue['barons'] + red['barons']),
                '1st inhibitor': f_inhib,
                'Total inhibitors': blue_inhib_count + red_inhib_count,
                'Last pick map winner': red_won,
                'Red side map winner': red_won
            })
            
    return parsed_rows

@st.cache_data(ttl=3600)  # Збільшуємо кеш до 1 години
def load_and_process_csv(source_input):
    # Pandas вміє сам завантажувати CSV за прямим URL!
    data = pd.read_csv(source_input, low_memory=False)
        
    # Перевірка наявності потрібної колонки
    if 'position' not in data.columns:
        raise KeyError("Колонку 'position' не знайдено. Перевір формат отриманого файлу.")
        
    # Залишаємо тільки записи для команд (без окремих гравців)
    teams_df = data[data['position'] == 'team'].copy()
    
    # Парсинг дати
    teams_df['parsed_datetime'] = pd.to_datetime(teams_df['date'], errors='coerce')
    teams_df['date_only'] = teams_df['parsed_datetime'].dt.date
    
    return teams_df

# ==========================================
# 2. ОСНОВНИЙ ІНТЕРФЕЙС STREAMLIT
# ==========================================
st.title("🎮 LoL Esports Multi-Match Exporter")

st.sidebar.header("📁 Джерело даних")
source_mode = st.sidebar.radio("Оберіть спосіб завантаження:", ["Google Диск (Посилання)", "Локальний CSV файл"])

df = None

try:
    if source_mode == "Google Диск (Посилання)":
        gdrive_url = st.sidebar.text_input("URL файлу з Google Диску:", value=DEFAULT_GDRIVE_LINK)
        if gdrive_url:
            with st.spinner("Завантаження CSV файлу з Google Диску..."):
                df = load_and_process_csv(gdrive_url)
                st.sidebar.success("Дані успішно завантажено!")
    else:
        uploaded_file = st.sidebar.file_uploader("Завантажте CSV-файл", type=['csv'])
        if uploaded_file is not None:
            df = load_and_process_csv(uploaded_file)
except Exception as e:
    st.error(f"Помилка зчитування файлу: {e}")

if df is not None:
    # --- Створюємо дві вкладки ---
    tab1, tab2 = st.tabs(["📊 Експорт матчів", "🧮 Калькулятор піків"])
    
    # ==========================================
    # Вкладка 1: Твій старий експортер
    # ==========================================
    with tab1:
        # 1. Список усіх турнірів із CSV
        all_tournaments = sorted(df['league'].dropna().unique().tolist())
        selected_tournaments = st.selectbox(
            "🏆 Оберіть турнір(и):", 
            options=all_tournaments, 
            key="tab1_tournaments"
        )
        
        # ... ТУТ МАЄ БУТИ ВВЕСЬ ТВІЙ СТАРИЙ КОД ФІЛЬТРАЦІЇ ...
        # (від вибору дат до кнопки "Відправити в Google Sheets")
        # Просто переконайся, що він має відступ всередині блоку `with tab1:`


    # ==========================================
    # Вкладка 2: Новий Калькулятор Піків
    # ==========================================
    with tab2:
        st.header("🧮 Аналіз піків та гравців")
        
        # Витягуємо дані лише по гравцях (виключаємо командну статистику)
        players_df = df[df['position'] != 'team'].copy()
        
        # Форматуємо патчі, щоб графік малювався коректно (замінюємо коми на крапки)
        players_df['patch'] = players_df['patch'].astype(str).str.replace(',', '.')
        
        teams_list = sorted(players_df['teamname'].dropna().unique().tolist())
        champs_list = sorted(players_df['champion'].dropna().unique().tolist())
        
        if not teams_list:
            st.warning("Немає даних по командах")
        else:
            # Створюємо 3 колонки: Команда 1, Команда 2 і Дашборд
            col1, col2, col3 = st.columns([1, 1, 1.5])
            
            # --- ДОПОМІЖНІ ФУНКЦІЇ ДЛЯ КАЛЬКУЛЯТОРА ---
            def get_roster(team_name):
                """Знаходить найчастішого гравця на кожній позиції для обраної команди"""
                roster = {}
                team_data = players_df[players_df['teamname'] == team_name]
                for role in ['top', 'jng', 'mid', 'bot', 'sup']:
                    r_data = team_data[team_data['position'] == role]
                    if not r_data.empty:
                        # Беремо гравця, який зіграв найбільше ігор на цій ролі
                        roster[role] = r_data['playername'].value_counts().index[0]
                    else:
                        roster[role] = "Невідомо"
                return roster

            def get_stats(player_name, champ_name):
                """Рахує середнє і медіану кілів, з фолбеком на лігу"""
                if not champ_name or champ_name == "None":
                    return 0, 0, ""
                
                # Шукаємо матчі конкретного гравця на конкретному герої
                p_data = players_df[(players_df['playername'] == player_name) & (players_df['champion'] == champ_name)]
                
                if not p_data.empty:
                    return p_data['kills'].mean(), p_data['kills'].median(), "Статистика гравця"
                
                # Якщо гравець не грав на герої — беремо стату по всіх гравцях на цьому герої
                c_data = players_df[players_df['champion'] == champ_name]
                if not c_data.empty:
                    return c_data['kills'].mean(), c_data['kills'].median(), "В середньому по лізі"
                
                return 0, 0, "Немає даних"

            roles_display = {'top': 'Top', 'jng': 'Jungle', 'mid': 'Mid', 'bot': 'ADC', 'sup': 'Support'}
            
            # Список для збору героїв, обраних на драфті (щоб малювати їх на графіку)
            selected_draft_champs = []

            # --- КОЛОНКА 1 (СИНЯ КОМАНДА) ---
            with col1:
                st.subheader("🔵 Синя команда")
                team1 = st.selectbox("Оберіть команду 1", options=teams_list, index=0, key="t1")
                roster1 = get_roster(team1)
                
                for role, role_name in roles_display.items():
                    st.markdown(f"**{role_name}** | {roster1[role]}")
                    champ = st.selectbox(f"Пік ({role_name})", ["None"] + champs_list, key=f"t1_champ_{role}")
                    
                    if champ != "None":
                        selected_draft_champs.append(champ)
                        mean_k, med_k, source = get_stats(roster1[role], champ)
                        # Виводимо результати
                        if source == "Статистика гравця":
                            st.success(f"Кіли: Середнє **{mean_k:.1f}** | Медіана **{med_k:.1f}**")
                        else:
                            st.warning(f"Кіли: Середнє **{mean_k:.1f}** | Медіана **{med_k:.1f}** ({source})")
                    st.write("---")

            # --- КОЛОНКА 2 (ЧЕРВОНА КОМАНДА) ---
            with col2:
                st.subheader("🔴 Червона команда")
                # Беремо іншу команду за замовчуванням, якщо команд достатньо
                t2_idx = 1 if len(teams_list) > 1 else 0
                team2 = st.selectbox("Оберіть команду 2", options=teams_list, index=t2_idx, key="t2")
                roster2 = get_roster(team2)
                
                for role, role_name in roles_display.items():
                    st.markdown(f"**{role_name}** | {roster2[role]}")
                    champ = st.selectbox(f"Пік ({role_name})", ["None"] + champs_list, key=f"t2_champ_{role}")
                    
                    if champ != "None":
                        selected_draft_champs.append(champ)
                        mean_k, med_k, source = get_stats(roster2[role], champ)
                        
                        if source == "Статистика гравця":
                            st.success(f"Кіли: Середнє **{mean_k:.1f}** | Медіана **{med_k:.1f}**")
                        else:
                            st.warning(f"Кіли: Середнє **{mean_k:.1f}** | Медіана **{med_k:.1f}** ({source})")
                    st.write("---")

            # --- КОЛОНКА 3 (ДАШБОРД ПАТЧІВ) ---
            with col3:
                st.subheader("📈 Тренд кілів по патчах")
                st.write("Оберіть героя на драфті зліва, щоб побачити графік.")
                
                # Фільтруємо унікальних героїв, яких щойно обрали на драфті
                unique_champs = list(set(selected_draft_champs))
                
                if unique_champs:
                    dash_champ = st.selectbox("Аналіз обраного героя:", unique_champs)
                    
                    # Готуємо дані для графіка (середні кіли героя по всіх іграх ліги)
                    champ_trend_data = players_df[players_df['champion'] == dash_champ]
                    
                    if not champ_trend_data.empty:
                        # Групуємо за патчем і рахуємо середнє
                        trend_grouped = champ_trend_data.groupby('patch')['kills'].mean().reset_index()
                        
                        # Сортуємо патчі як числа (наскільки це можливо)
                        # Якщо формат складний, можна просто покластись на алфавітне сортування
                        trend_grouped = trend_grouped.sort_values(by='patch')
                        trend_grouped.set_index('patch', inplace=True)
                        
                        st.line_chart(trend_grouped)
                        st.caption(f"Середня кількість кілів **{dash_champ}** (за всіма матчами в базі)")
                    else:
                        st.info("Недостатньо даних для малювання графіка.")
                else:
                    st.info("Поки що жодного героя не обрано.")