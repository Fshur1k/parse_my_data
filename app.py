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
    # 1. Список усіх турнірів із CSV
    all_tournaments = sorted(df['league'].dropna().unique().tolist())
    selected_tournaments = st.sidebar.multiselect(
        "🏆 Оберіть турнір(и):", 
        options=all_tournaments, 
        default=['LEC', 'LCK', 'LPL'] if all(x in all_tournaments for x in ['LEC', 'LCK', 'LPL']) else all_tournaments[:3]
    )
    
    # 2. Календар за датами
    min_date = df['date_only'].min()
    max_date = df['date_only'].max()
    selected_date_range = st.sidebar.date_input(
        "📅 Діапазон дат:",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )
    
    if isinstance(selected_date_range, tuple) and len(selected_date_range) == 2:
        start_date, end_date = selected_date_range
    else:
        start_date = end_date = selected_date_range[0] if isinstance(selected_date_range, (list, tuple)) else selected_date_range
        
    # Фільтрація
    filtered_df = df[
        (df['league'].isin(selected_tournaments)) &
        (df['date_only'] >= start_date) &
        (df['date_only'] <= end_date)
    ]
    
    if filtered_df.empty:
            st.warning("⚠️ За обраними фільтрами (турніри / дати) матчів не знайдено.")
    else:
        # === БЛОК ГРУПУВАННЯ МАТЧІВ (СЕРІЙ) ===
        series_info = {}
        
        for game_id, g in filtered_df.groupby('gameid'):
            # Беремо назви обох команд і сортуємо їх за алфавітом
            teams = sorted(g['teamname'].dropna().unique().tolist())
            team_display = f"{teams[0]} vs {teams[1]}" if len(teams) == 2 else " vs ".join(teams)
            
            league_name = g['league'].iloc[0]
            game_date = g['date_only'].iloc[0]
            
            # Створюємо унікальний ключ для серії (матчу)
            series_key = f"{game_date}_{league_name}_{team_display}"
            
            if series_key not in series_info:
                series_info[series_key] = {
                    'display_name': f"{game_date} | [{league_name}] {team_display}",
                    'game_ids': []
                }
                
            # Додаємо ID карти до загального списку карт цієї серії
            series_info[series_key]['game_ids'].append(game_id)
            
        # Додаємо кількість зіграних карт до назви в меню
        display_options = {}
        for s_key, info in series_info.items():
            map_count = len(info['game_ids'])
            display_options[s_key] = f"{info['display_name']} ({map_count} карт)"

        # 3. Множинний вибір матчів
        st.subheader("⚔️ Вибір матчів")
        selected_series_keys = st.multiselect(
            "Оберіть один або декілька матчів (усі карти підтягнуться автоматично):",
            options=list(display_options.keys()),
            format_func=lambda x: display_options[x],
            default=list(display_options.keys())[:3] if len(display_options) >= 3 else list(display_options.keys())
        )
        
        if selected_series_keys:
            # Збираємо всі gameid (карти), що входять у вибрані матчі
            selected_match_ids = []
            for s_key in selected_series_keys:
                selected_match_ids.extend(series_info[s_key]['game_ids'])
                
            # Фільтруємо датафрейм за всіма знайденими картами
            selected_games_df = filtered_df[filtered_df['gameid'].isin(selected_match_ids)]
            
            # Парсимо дані
            parsed_maps_rows = parse_selected_games(selected_games_df)
            parsed_df = pd.DataFrame(parsed_maps_rows)
            
            st.subheader(f"📊 Згенерована таблиця карт ({len(parsed_df)} карт(и))")
            st.dataframe(parsed_df)
            
            st.markdown("---")
            st.subheader("📤 Експорт у Google Sheets")
            
            col1, col2 = st.columns(2)
            with col1:
                st.session_state['sheet_url'] = st.text_input("URL Google Таблиці:", value=st.session_state['sheet_url'])
            with col2:
                st.session_state['sheet_name'] = st.text_input("Назва аркуша:", value=st.session_state['sheet_name'])
                
            if st.button("🚀 Відправити в Google Sheets"):
                with st.spinner("Запис даних у Google Таблицю..."):
                    success, message = append_to_sheet(
                        st.session_state['sheet_url'], 
                        st.session_state['sheet_name'], 
                        parsed_maps_rows
                    )
                    if success:
                        st.success(message)
                    else:
                        st.error(message)