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

@st.cache_data(ttl=3600)
def load_and_process_csv(source_input):
    data = pd.read_csv(source_input, low_memory=False)
        
    if 'position' not in data.columns:
        raise KeyError("Колонку 'position' не знайдено. Перевір формат отриманого файлу.")
        
    # БІЛЬШЕ НЕ ВИДАЛЯЄМО ГРАВЦІВ ТУТ! Парсимо дати для всього файлу
    data['parsed_datetime'] = pd.to_datetime(data['date'], errors='coerce')
    data['date_only'] = data['parsed_datetime'].dt.date
    
    return data

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
    tab1, tab2 = st.tabs(["📊 Експорт матчів", "🧮 Калькулятор піків"])
    
    # ==========================================
    # Вкладка 1: Експортер (Командна статистика)
    # ==========================================
    with tab1:
        teams_df = df[df['position'] == 'team'].copy()
        all_tournaments = sorted(teams_df['league'].dropna().unique().tolist())
        selected_tournaments = st.multiselect(
            "🏆 Оберіть турнір(и):", 
            options=all_tournaments, 
            default=['LEC', 'LCK', 'LPL'] if all(x in all_tournaments for x in ['LEC', 'LCK', 'LPL']) else all_tournaments[:3],
            key="tab1_tournaments"
        )
        
        min_date = teams_df['date_only'].min()
        max_date = teams_df['date_only'].max()
        selected_date_range = st.sidebar.date_input(
            "📅 Діапазон дат:", value=(min_date, max_date), min_value=min_date, max_value=max_date
        )
        
        if isinstance(selected_date_range, tuple) and len(selected_date_range) == 2:
            start_date, end_date = selected_date_range
        else:
            start_date = end_date = selected_date_range[0] if isinstance(selected_date_range, (list, tuple)) else selected_date_range
            
        filtered_df = teams_df[
            (teams_df['league'].isin(selected_tournaments)) &
            (teams_df['date_only'] >= start_date) &
            (teams_df['date_only'] <= end_date)
        ]
        
        if filtered_df.empty:
            st.warning("⚠️ За обраними фільтрами (турніри / дати) матчів не знайдено.")
        else:
            series_info = {}
            for game_id, g in filtered_df.groupby('gameid'):
                teams = sorted(g['teamname'].dropna().unique().tolist())
                team_display = f"{teams[0]} vs {teams[1]}" if len(teams) == 2 else " vs ".join(teams)
                league_name = g['league'].iloc[0]
                game_date = g['date_only'].iloc[0]
                series_key = f"{game_date}_{league_name}_{team_display}"
                
                if series_key not in series_info:
                    series_info[series_key] = {'display_name': f"{game_date} | [{league_name}] {team_display}", 'game_ids': []}
                series_info[series_key]['game_ids'].append(game_id)
                
            display_options = {s_key: f"{info['display_name']} ({len(info['game_ids'])} карт)" for s_key, info in series_info.items()}
    
            st.subheader("⚔️ Вибір матчів")
            selected_series_keys = st.multiselect(
                "Оберіть один або декілька матчів:",
                options=list(display_options.keys()),
                format_func=lambda x: display_options[x],
                default=list(display_options.keys())[:3] if len(display_options) >= 3 else list(display_options.keys())
            )
            
            if selected_series_keys:
                selected_match_ids = []
                for s_key in selected_series_keys:
                    selected_match_ids.extend(series_info[s_key]['game_ids'])
                    
                selected_games_df = filtered_df[filtered_df['gameid'].isin(selected_match_ids)]
                parsed_maps_rows = parse_selected_games(selected_games_df)
                parsed_df = pd.DataFrame(parsed_maps_rows)
                
                st.subheader(f"📊 Згенерована таблиця ({len(parsed_df)} карт(и))")
                st.dataframe(parsed_df)
                
                st.markdown("---")
                st.subheader("📤 Експорт у Google Sheets")
                col1, col2 = st.columns(2)
                with col1:
                    st.session_state['sheet_url'] = st.text_input("URL Google Таблиці:", value=st.session_state['sheet_url'])
                with col2:
                    st.session_state['sheet_name'] = st.text_input("Назва аркуша:", value=st.session_state['sheet_name'])
                    
                if st.button("🚀 Відправити в Google Sheets"):
                    with st.spinner("Записуємо..."):
                        success, message = append_to_sheet(st.session_state['sheet_url'], st.session_state['sheet_name'], parsed_maps_rows)
                        if success: st.success(message)
                        else: st.error(message)

    # ==========================================
    # Вкладка 2: Компактний Калькулятор Піків
    # ==========================================
    with tab2:
        players_df = df[df['position'] != 'team'].copy()
        players_df['patch'] = players_df['patch'].astype(str).str.replace(',', '.')
        
        teams_list = sorted(players_df['teamname'].dropna().unique().tolist())
        champs_list = sorted(players_df['champion'].dropna().unique().tolist())
        
        if not teams_list:
            st.warning("Дані по гравцях відсутні.")
        else:
            # Фільтри для статистики калькулятора
            f_col1, f_col2 = st.columns(2)
            with f_col1:
                min_dp = players_df['date_only'].min()
                max_dp = players_df['date_only'].max()
                sel_dates = st.date_input("📅 Період статистики:", value=(min_dp, max_dp), key="t2_dates")
            with f_col2:
                all_patches = sorted(players_df['patch'].unique().tolist())
                sel_patches = st.multiselect("🔢 Патчі для аналізу:", options=all_patches, default=all_patches, key="t2_patches")
            
            if isinstance(sel_dates, tuple) and len(sel_dates) == 2:
                s_date, e_date = sel_dates
            else:
                s_date = e_date = sel_dates[0] if isinstance(sel_dates, (list, tuple)) else sel_dates
                
            filtered_players = players_df[
                (players_df['date_only'] >= s_date) &
                (players_df['date_only'] <= e_date) &
                (players_df['patch'].isin(sel_patches))
            ]
            
            st.markdown("---")
            col1, col2, col3 = st.columns([1.5, 1.5, 1.2])
            
            # --- Логіка знаходження найновіших 2 патчів для складу за замовчуванням ---
            def patch_val(p):
                parts = p.split('.')
                try: return float(f"{parts[0]}.{int(parts[1]):03d}")
                except: return 0
                
            last_2_patches = sorted(all_patches, key=patch_val, reverse=True)[:2]

            def get_team_players(team_name, role):
                team_role_df = players_df[(players_df['teamname'] == team_name) & (players_df['position'] == role)]
                if team_role_df.empty: return ["Невідомо"], 0
                
                all_p = team_role_df['playername'].unique().tolist()
                recent_df = team_role_df[team_role_df['patch'].isin(last_2_patches)]
                
                default_p = recent_df['playername'].value_counts().index[0] if not recent_df.empty else team_role_df['playername'].value_counts().index[0]
                return all_p, (all_p.index(default_p) if default_p in all_p else 0)

            def get_stats(player_name, champ_name):
                if not champ_name or champ_name == "None": return 0, 0, 0, ""
                p_data = filtered_players[(filtered_players['playername'] == player_name) & (filtered_players['champion'] == champ_name)]
                
                if not p_data.empty:
                    return p_data['kills'].mean(), p_data['kills'].median(), p_data['result'].mean()*100, "Гравця"
                
                c_data = filtered_players[filtered_players['champion'] == champ_name]
                if not c_data.empty:
                    return c_data['kills'].mean(), c_data['kills'].median(), c_data['result'].mean()*100, "Ліги"
                
                return 0, 0, 0, "-"

            roles_display = {'top': 'Top', 'jng': 'Jungle', 'mid': 'Mid', 'bot': 'ADC', 'sup': 'Support'}
            t1_total_kills, t2_total_kills = 0.0, 0.0
            selected_draft_champs = []

            # --- КОМАНДА 1 ---
            with col1:
                team1 = st.selectbox("Команда 1", options=teams_list, index=0, key="t1")
                st.markdown("---")
                for role, role_name in roles_display.items():
                    p_list, p_idx = get_team_players(team1, role)
                    c_p, c_c = st.columns(2)
                    player = c_p.selectbox(f"{role_name}", options=p_list, index=p_idx, key=f"t1_p_{role}")
                    champ = c_c.selectbox(f"Пік", options=["None"] + champs_list, key=f"t1_c_{role}")
                    
                    if champ != "None":
                        selected_draft_champs.append(champ)
                        mean_k, med_k, wr, source = get_stats(player, champ)
                        t1_total_kills += mean_k
                        st.caption(f"🎯 **{mean_k:.1f}** кілів | WR: **{wr:.0f}%** ({source})")

            # --- КОМАНДА 2 ---
            with col2:
                team2 = st.selectbox("Команда 2", options=teams_list, index=1 if len(teams_list)>1 else 0, key="t2")
                st.markdown("---")
                for role, role_name in roles_display.items():
                    p_list, p_idx = get_team_players(team2, role)
                    c_p, c_c = st.columns(2)
                    player = c_p.selectbox(f"{role_name}", options=p_list, index=p_idx, key=f"t2_p_{role}")
                    champ = c_c.selectbox(f"Пік", options=["None"] + champs_list, key=f"t2_c_{role}")
                    
                    if champ != "None":
                        selected_draft_champs.append(champ)
                        mean_k, med_k, wr, source = get_stats(player, champ)
                        t2_total_kills += mean_k
                        st.caption(f"🎯 **{mean_k:.1f}** кілів | WR: **{wr:.0f}%** ({source})")

            # --- ДАШБОРД (Колонка 3) ---
            with col3:
                st.subheader("📊 Аналіз драфту")
                st.metric(f"Теоретичні кіли: {team1}", f"{t1_total_kills:.1f}")
                st.metric(f"Теоретичні кіли: {team2}", f"{t2_total_kills:.1f}")
                
                unique_champs = list(set([c for c in selected_draft_champs if c != "None"]))
                if unique_champs:
                    champ_trend_data = filtered_players[filtered_players['champion'].isin(unique_champs)]
                    if not champ_trend_data.empty:
                        trend_grouped = champ_trend_data.groupby(['patch', 'champion'])['kills'].mean().reset_index()
                        pivot_trend = trend_grouped.pivot(index='patch', columns='champion', values='kills')
                        pivot_trend.index = sorted(pivot_trend.index, key=patch_val)
                        
                        st.line_chart(pivot_trend)
                        st.caption("Тренд середніх кілів по патчах.")