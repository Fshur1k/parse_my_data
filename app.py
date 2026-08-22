import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re

st.set_page_config(page_title="LoL Esports Auto-Exporter", layout="wide")

# ==========================================
# ⚙️ ЛОКАЛІЗАЦІЯ (ПЕРЕКЛАДИ)
# ==========================================
TRANSLATIONS = {
    "uk": {
        "title": "🎮 LoL Esports Multi-Match Exporter",
        "lang_select": "🌍 Мова / Language",
        "reminder": "👋 Привіт! Завантажте сюди останній CSV-файл бази **Oracle's Elixir** для початку аналізу.",
        "sidebar_header": "📁 Джерело даних",
        "file_upload": "Завантажте локальний CSV-файл",
        "adv_url": "🔗 Додатково: Завантажити за посиланням",
        "url_input": "Пряме посилання (Google Drive / AWS):",
        "btn_load_url": "Завантажити",
        "loading": "Завантаження...",
        "success_load": "Дані успішно завантажено!",
        "err_load": "Помилка зчитування файлу:",
        "tab1": "📊 Експорт матчів",
        "tab2": "🧮 Калькулятор піків",
        "tournaments": "🏆 Оберіть турнір(и):",
        "dates": "📅 Діапазон дат:",
        "no_matches": "⚠️ За обраними фільтрами (турніри / дати) матчів не знайдено.",
        "match_sel": "⚔️ Вибір матчів",
        "choose_matches": "Оберіть один або декілька матчів:",
        "gen_table": "📊 Згенерована таблиця",
        "maps": "карт(и)",
        "export_btn": "🚀 Відправити в Google Sheets",
        "writing": "Записуємо...",
        "no_players": "Дані по гравцях відсутні.",
        "stat_period": "📅 Період статистики:",
        "patches": "🔢 Патчі для аналізу:",
        "team_1": "Команда 1",
        "team_2": "Команда 2",
        "pick": "Пік",
        "unknown": "Невідомо",
        "src_player": "Гравця",
        "src_league": "Ліги",
        "draft_analysis": "📊 Аналіз драфту",
        "theo_kills": "Теоретичні кіли",
        "trend_desc": "Тренд середніх кілів по патчах."
    },
    "en": {
        "title": "🎮 LoL Esports Multi-Match Exporter",
        "lang_select": "🌍 Language / Мова",
        "reminder": "👋 Hello! Please upload the latest CSV file from **Oracle's Elixir** here to begin analysis.",
        "sidebar_header": "📁 Data Source",
        "file_upload": "Upload local CSV file",
        "adv_url": "🔗 Advanced: Load via URL",
        "url_input": "Direct URL (Google Drive / AWS):",
        "btn_load_url": "Load Data",
        "loading": "Loading...",
        "success_load": "Data loaded successfully!",
        "err_load": "Error reading file:",
        "tab1": "📊 Match Exporter",
        "tab2": "🧮 Pick Calculator",
        "tournaments": "🏆 Select Tournament(s):",
        "dates": "📅 Date Range:",
        "no_matches": "⚠️ No matches found for the selected filters.",
        "match_sel": "⚔️ Match Selection",
        "choose_matches": "Select one or more matches:",
        "gen_table": "📊 Generated Table",
        "maps": "map(s)",
        "export_btn": "🚀 Send to Google Sheets",
        "writing": "Writing...",
        "no_players": "No player data available.",
        "stat_period": "📅 Stats Period:",
        "patches": "🔢 Patches for analysis:",
        "team_1": "Team 1",
        "team_2": "Team 2",
        "pick": "Pick",
        "unknown": "Unknown",
        "src_player": "Player",
        "src_league": "League",
        "draft_analysis": "📊 Draft Analysis",
        "theo_kills": "Theoretical kills",
        "trend_desc": "Average kills trend by patch."
    }
}

# Вибір мови в сайдбарі
lang_choice = st.sidebar.radio("Language", ["Українська", "English"], label_visibility="collapsed")
lang = "uk" if lang_choice == "Українська" else "en"
t = TRANSLATIONS[lang]

# ==========================================
# ⚙️ НАЛАШТУВАННЯ ЗА ЗАМОВЧУВАННЯМ
# ==========================================
DEFAULT_GDRIVE_LINK = "https://oracleselixir-downloadable-match-data.s3-us-west-2.amazonaws.com/2026_LoL_esports_match_data_from_OraclesElixir.csv"
DEFAULT_SHEET_URL = "https://docs.google.com/spreadsheets/d/1kjn9qTW1tgMNtqRwYCg0bQBWvjC9pJ6K-LZ6-G2o274/edit?gid=0#gid=0"
DEFAULT_SHEET_NAME = "Sheets1"

if 'sheet_url' not in st.session_state: st.session_state['sheet_url'] = DEFAULT_SHEET_URL
if 'sheet_name' not in st.session_state: st.session_state['sheet_name'] = DEFAULT_SHEET_NAME
if 'df' not in st.session_state: st.session_state['df'] = None

# ==========================================
# 1. ДОПОМІЖНІ ФУНКЦІЇ ТА СЕРВІСИ
# ==========================================
def convert_gdrive_url(url: str) -> str:
    match = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
    if match: return f'https://drive.google.com/uc?export=download&id={match.group(1)}'
    return url

def get_gspread_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

def append_to_sheet(spreadsheet_url, sheet_name, data_rows):
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
            
        if len(sheet.get_all_values()) == initial_count + len(data_rows):
            return True, f"Успішно додано {len(data_rows)} {t['maps']} у Google Sheets!"
        else: return False, "Помилка запису: кількість рядків у таблиці не збігається."
    except Exception as e:
        return False, f"Помилка доступу до Google Sheets: {str(e)}"

def parse_selected_games(df_games):
    parsed_rows = []
    for game_id, match_data in df_games.groupby('gameid'):
        for map_num, map_data in match_data.groupby('game'):
            blue = map_data[map_data['side'] == 'Blue'].iloc[0]
            red = map_data[map_data['side'] == 'Red'].iloc[0]
            
            t1, t2 = blue['teamname'], red['teamname']
            t1_kills, t2_kills = int(blue['kills']), int(red['kills'])
            
            if t1_kills >= 10 and t2_kills < 10: f10 = t1
            elif t2_kills >= 10 and t1_kills < 10: f10 = t2
            elif t1_kills < 10 and t2_kills < 10: f10 = 'None'
            else: f10 = 'N/A'
                
            fb = t1 if blue['firstblood'] == 1 else (t2 if red['firstblood'] == 1 else 'None')
            f_tower = t1 if blue['firsttower'] == 1 else (t2 if red['firsttower'] == 1 else 'None')
            f_dragon = t1 if blue['firstdragon'] == 1 else (t2 if red['firstdragon'] == 1 else 'None')
            f_nashor = t1 if blue['firstbaron'] == 1 else (t2 if red['firstbaron'] == 1 else 'None')
            
            b_inhib, r_inhib = int(blue.get('inhibitors', 0)), int(red.get('inhibitors', 0))
            if blue.get('firstinhibitor', 0) == 1: f_inhib = t1
            elif red.get('firstinhibitor', 0) == 1: f_inhib = t2
            elif b_inhib > 0 and r_inhib == 0: f_inhib = t1
            elif r_inhib > 0 and b_inhib == 0: f_inhib = t2
            else: f_inhib = 'None'
            
            date_str = str(blue['date'])
            date_part = date_str.split(' ')[0] if ' ' in date_str else date_str
            time_part = date_str.split(' ')[1] if ' ' in date_str else '12:00:00'
            
            total_sec = int(blue.get('gamelength', 0))
            
            parsed_rows.append({
                'Patch': str(blue.get('patch', '')).replace(',', '.'),
                'Date': date_part,
                'Match start time': time_part,
                'Tournament': blue['league'],
                'Map number': int(map_num),
                'Team 1': t1,
                'Team 2': t2,
                'Team 1 baseline (%)': '50%',
                'Map winner': t1 if blue['result'] == 1 else t2,
                'Team 1 kills': t1_kills,
                'Team 2 kills': t2_kills,
                'Total kills': t1_kills + t2_kills,
                'Total minutes': f"{total_sec//60:02d}:{total_sec%60:02d}",
                'FB': fb,
                'F10': f10,
                '1st tower': f_tower,
                'Total towers': int(blue['towers'] + red['towers']),
                '1st dragon': f_dragon,
                'Total dragons': int(blue['dragons'] + red['dragons']),
                '1st nashor': f_nashor,
                'Total nashors': int(blue['barons'] + red['barons']),
                '1st inhibitor': f_inhib,
                'Total inhibitors': b_inhib + r_inhib,
                'Last pick map winner': "YES" if red['result'] == 1 else "NO",
                'Red side map winner': "YES" if red['result'] == 1 else "NO"
            })
    return parsed_rows

@st.cache_data(ttl=3600)
def load_and_process_csv(source_input):
    data = pd.read_csv(source_input, low_memory=False)
    if 'position' not in data.columns:
        raise KeyError("Колонку 'position' не знайдено.")
    data = data.copy() # Дефрагментація пам'яті
    data['parsed_datetime'] = pd.to_datetime(data['date'], errors='coerce')
    data['date_only'] = data['parsed_datetime'].dt.date
    return data

# ==========================================
# 2. ОСНОВНИЙ ІНТЕРФЕЙС STREAMLIT
# ==========================================
st.title(t["title"])

st.sidebar.header(t["sidebar_header"])
uploaded_file = st.sidebar.file_uploader(t["file_upload"], type=['csv'])

with st.sidebar.expander(t["adv_url"]):
    gdrive_url = st.text_input(t["url_input"], value=DEFAULT_GDRIVE_LINK)
    load_url_btn = st.button(t["btn_load_url"])

try:
    if uploaded_file is not None:
        st.session_state['df'] = load_and_process_csv(uploaded_file)
    elif load_url_btn and gdrive_url:
        with st.spinner(t["loading"]):
            st.session_state['df'] = load_and_process_csv(gdrive_url)
            st.sidebar.success(t["success_load"])
except Exception as e:
    st.error(f"{t['err_load']} {e}")

df = st.session_state['df']

if df is None:
    st.info(t["reminder"])
else:
    tab1, tab2 = st.tabs([t["tab1"], t["tab2"]])
    
    # ==========================================
    # Вкладка 1: Експортер матчів
    # ==========================================
    with tab1:
        teams_df = df[df['position'] == 'team'].copy()
        all_tournaments = sorted(teams_df['league'].dropna().unique().tolist())
        selected_tournaments = st.multiselect(
            t["tournaments"], 
            options=all_tournaments, 
            default=['LEC', 'LCK', 'LPL'] if all(x in all_tournaments for x in ['LEC', 'LCK', 'LPL']) else all_tournaments[:3],
            key="tab1_tournaments"
        )
        
        min_date, max_date = teams_df['date_only'].min(), teams_df['date_only'].max()
        sel_dates = st.date_input(t["dates"], value=(min_date, max_date), min_value=min_date, max_value=max_date)
        
        s_date = e_date = sel_dates[0] if isinstance(sel_dates, (list, tuple)) else sel_dates
        if isinstance(sel_dates, tuple) and len(sel_dates) == 2:
            s_date, e_date = sel_dates
            
        filtered_df = teams_df[
            (teams_df['league'].isin(selected_tournaments)) &
            (teams_df['date_only'] >= s_date) & (teams_df['date_only'] <= e_date)
        ]
        
        if filtered_df.empty:
            st.warning(t["no_matches"])
        else:
            series_info = {}
            for game_id, g in filtered_df.groupby('gameid'):
                teams = sorted(g['teamname'].dropna().unique().tolist())
                team_display = f"{teams[0]} vs {teams[1]}" if len(teams) == 2 else " vs ".join(teams)
                l_name, g_date = g['league'].iloc[0], g['date_only'].iloc[0]
                series_key = f"{g_date}_{l_name}_{team_display}"
                
                if series_key not in series_info:
                    series_info[series_key] = {'display_name': f"{g_date} | [{l_name}] {team_display}", 'game_ids': []}
                series_info[series_key]['game_ids'].append(game_id)
                
            display_options = {s_key: f"{info['display_name']} ({len(info['game_ids'])} {t['maps']})" for s_key, info in series_info.items()}
    
            st.subheader(t["match_sel"])
            selected_series = st.multiselect(
                t["choose_matches"],
                options=list(display_options.keys()),
                format_func=lambda x: display_options[x],
                default=list(display_options.keys())[:3] if len(display_options) >= 3 else list(display_options.keys())
            )
            
            if selected_series:
                match_ids = [gid for s_key in selected_series for gid in series_info[s_key]['game_ids']]
                selected_games_df = filtered_df[filtered_df['gameid'].isin(match_ids)]
                
                parsed_df = pd.DataFrame(parse_selected_games(selected_games_df))
                st.subheader(f"{t['gen_table']} ({len(parsed_df)} {t['maps']})")
                st.dataframe(parsed_df)
                
                st.markdown("---")
                st.subheader(t["export_btn"])
                c1, c2 = st.columns(2)
                st.session_state['sheet_url'] = c1.text_input("URL Google Sheets:", value=st.session_state['sheet_url'])
                st.session_state['sheet_name'] = c2.text_input("Sheet Name:", value=st.session_state['sheet_name'])
                
                if st.button(t["export_btn"]):
                    with st.spinner(t["writing"]):
                        success, message = append_to_sheet(st.session_state['sheet_url'], st.session_state['sheet_name'], parsed_df.to_dict('records'))
                        if success: st.success(message)
                        else: st.error(message)

    # ==========================================
    # Вкладка 2: Калькулятор Піків
    # ==========================================
    with tab2:
        players_df = df[df['position'] != 'team'].copy()
        players_df['patch'] = players_df['patch'].astype(str).str.replace(',', '.')
        teams_list = sorted(players_df['teamname'].dropna().unique().tolist())
        champs_list = sorted(players_df['champion'].dropna().unique().tolist())
        
        if not teams_list:
            st.warning(t["no_players"])
        else:
            # Визначаємо сортування патчів вище, щоб використати їх для default значень
            def patch_val(p):
                parts = p.split('.')
                try: return float(f"{parts[0]}.{int(parts[1]):03d}")
                except: return 0
                
            all_patches = sorted(players_df['patch'].unique().tolist())
            last_2_patches = sorted(all_patches, key=patch_val, reverse=True)[:2]

            f_col1, f_col2 = st.columns(2)
            with f_col1:
                sel_dates = st.date_input(t["stat_period"], value=(players_df['date_only'].min(), players_df['date_only'].max()), key="t2_dates")
            with f_col2:
                # Встановлюємо default=last_2_patches
                sel_patches = st.multiselect(t["patches"], options=all_patches, default=last_2_patches, key="t2_patches")
            
            s_date = e_date = sel_dates[0] if isinstance(sel_dates, (list, tuple)) else sel_dates
            if isinstance(sel_dates, tuple) and len(sel_dates) == 2:
                s_date, e_date = sel_dates
                
            filtered_p = players_df[(players_df['date_only'] >= s_date) & (players_df['date_only'] <= e_date) & (players_df['patch'].isin(sel_patches))]
            
            st.markdown("---")
            col1, col2, col3 = st.columns([1.5, 1.5, 1.2])
            
            def patch_val(p):
                parts = p.split('.')
                try: return float(f"{parts[0]}.{int(parts[1]):03d}")
                except: return 0
                
            last_2_patches = sorted(all_patches, key=patch_val, reverse=True)[:2]

            def get_team_players(t_name, role):
                t_df = players_df[(players_df['teamname'] == t_name) & (players_df['position'] == role)]
                if t_df.empty: return [t["unknown"]], 0
                all_p = t_df['playername'].unique().tolist()
                r_df = t_df[t_df['patch'].isin(last_2_patches)]
                def_p = r_df['playername'].value_counts().index[0] if not r_df.empty else t_df['playername'].value_counts().index[0]
                return all_p, (all_p.index(def_p) if def_p in all_p else 0)

            def get_stats(p_name, c_name):
                if not c_name or c_name == "None": return 0, 0, "-"
                p_data = filtered_p[(filtered_p['playername'] == p_name) & (filtered_p['champion'] == c_name)]
                if not p_data.empty: return p_data['kills'].mean(), p_data['result'].mean()*100, t["src_player"]
                c_data = filtered_p[filtered_p['champion'] == c_name]
                if not c_data.empty: return c_data['kills'].mean(), c_data['result'].mean()*100, t["src_league"]
                return 0, 0, "-"

            roles = {'top': 'Top', 'jng': 'Jungle', 'mid': 'Mid', 'bot': 'ADC', 'sup': 'Support'}
            t1_total, t2_total = 0.0, 0.0
            sel_champs = []

            with col1:
                team1 = st.selectbox(t["team_1"], options=teams_list, index=0, key="t1")
                st.markdown("---")
                for r, r_name in roles.items():
                    p_list, p_idx = get_team_players(team1, r)
                    c_p, c_c = st.columns(2)
                    player = c_p.selectbox(r_name, options=p_list, index=p_idx, key=f"t1_p_{r}")
                    champ = c_c.selectbox(t["pick"], options=["None"] + champs_list, key=f"t1_c_{r}")
                    if champ != "None":
                        sel_champs.append(champ)
                        mk, wr, src = get_stats(player, champ)
                        t1_total += mk
                        st.caption(f"🎯 **{mk:.1f}** k. | WR: **{wr:.0f}%** ({src})")

            with col2:
                team2 = st.selectbox(t["team_2"], options=teams_list, index=1 if len(teams_list)>1 else 0, key="t2")
                st.markdown("---")
                for r, r_name in roles.items():
                    p_list, p_idx = get_team_players(team2, r)
                    c_p, c_c = st.columns(2)
                    player = c_p.selectbox(r_name, options=p_list, index=p_idx, key=f"t2_p_{r}")
                    champ = c_c.selectbox(t["pick"], options=["None"] + champs_list, key=f"t2_c_{r}")
                    if champ != "None":
                        sel_champs.append(champ)
                        mk, wr, src = get_stats(player, champ)
                        t2_total += mk
                        st.caption(f"🎯 **{mk:.1f}** k. | WR: **{wr:.0f}%** ({src})")

            with col3:
                st.subheader(t["draft_analysis"])
                st.metric(f"{t['theo_kills']}: {team1}", f"{t1_total:.1f}")
                st.metric(f"{t['theo_kills']}: {team2}", f"{t2_total:.1f}")
                
                u_champs = list(set([c for c in sel_champs if c != "None"]))
                if u_champs:
                    trend_data = filtered_p[filtered_p['champion'].isin(u_champs)]
                    if not trend_data.empty:
                        tg = trend_data.groupby(['patch', 'champion'])['kills'].mean().reset_index()
                        pt = tg.pivot(index='patch', columns='champion', values='kills').reset_index()
                        pt['s_val'] = pt['patch'].apply(patch_val)
                        pt = pt.sort_values('s_val').drop(columns=['s_val']).set_index('patch')
                        st.line_chart(pt)
                        st.caption(t["trend_desc"])