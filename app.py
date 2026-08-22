import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re

st.set_page_config(page_title="Експорт Матчів | LoL", layout="wide")

TRANSLATIONS = {
    "uk": {
        "title": "📊 Експорт Матчів у Google Sheets",
        "reminder": "👋 Привіт! Завантажте файл бази Oracle's Elixir у боковій панелі.",
        "success_load": "Дані успішно завантажено!",
        "err_load": "Помилка зчитування файлу:",
        "export_btn": "🚀 Відправити в Google Sheets",
        "writing": "Записуємо..."
    },
    "en": {
        "title": "📊 Match Exporter for Google Sheets",
        "reminder": "👋 Hello! Upload the Oracle's Elixir file in the sidebar.",
        "success_load": "Data loaded successfully!",
        "err_load": "Error reading file:",
        "export_btn": "🚀 Send to Google Sheets",
        "writing": "Writing..."
    }
}

lang_choice = st.sidebar.radio("Language", ["Українська", "English"], label_visibility="collapsed")
lang = "uk" if lang_choice == "Українська" else "en"
t = TRANSLATIONS[lang]

# Замість URL просто вказуємо назву файлу, який лежить поруч із app.py
DEFAULT_GDRIVE_LINK = "2026_LoL_esports_match_data_from_OraclesElixir.csv"
if 'sheet_url' not in st.session_state: st.session_state['sheet_url'] = "https://docs.google.com/spreadsheets/d/1kjn9qTW1tgMNtqRwYCg0bQBWvjC9pJ6K-LZ6-G2o274/edit?gid=0#gid=0"
if 'sheet_name' not in st.session_state: st.session_state['sheet_name'] = "Sheets1"
if 'df' not in st.session_state: st.session_state['df'] = None

# Допоміжні функції
def get_gspread_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
    return gspread.authorize(creds)

def append_to_sheet(url, sheet, rows):
    try:
        client = get_gspread_client()
        ws = client.open_by_url(url).worksheet(sheet)
        if not ws.get_all_values():
            ws.append_row(['Patch', 'Date', 'Match start time', 'Tournament', 'Map number', 'Team 1', 'Team 2', 'Team 1 baseline (%)', 'Map winner', 'Team 1 kills', 'Team 2 kills', 'Total kills', 'Total minutes', 'FB', 'F10', '1st tower', 'Total towers', '1st dragon', 'Total dragons', '1st nashor', 'Total nashors', '1st inhibitor', 'Total inhibitors', 'Last pick map winner', 'Red side map winner'])
        init_count = len(ws.get_all_values())
        ws.append_rows([list(r.values()) for r in rows])
        if len(ws.get_all_values()) == init_count + len(rows): return True, "Успішно додано!"
        return False, "Помилка запису."
    except Exception as e: return False, str(e)

def parse_games(df_games):
    parsed = []
    for g_id, m_data in df_games.groupby('gameid'):
        for m_num, m_map in m_data.groupby('game'):
            b, r = m_map[m_map['side'] == 'Blue'].iloc[0], m_map[m_map['side'] == 'Red'].iloc[0]
            t1_k, t2_k = int(b['kills']), int(r['kills'])
            
            f10 = b['teamname'] if t1_k >= 10 and t2_k < 10 else (r['teamname'] if t2_k >= 10 and t1_k < 10 else ('None' if t1_k < 10 and t2_k < 10 else 'N/A'))
            
            b_inh, r_inh = int(b.get('inhibitors', 0)), int(r.get('inhibitors', 0))
            f_inh = b['teamname'] if b.get('firstinhibitor') == 1 or (b_inh > 0 and r_inh == 0) else (r['teamname'] if r.get('firstinhibitor') == 1 or (r_inh > 0 and b_inh == 0) else 'None')
            
            d_str = str(b['date'])
            ts = int(b.get('gamelength', 0))
            
            parsed.append({
                'Patch': str(b.get('patch', '')).replace(',', '.'), 'Date': d_str.split(' ')[0] if ' ' in d_str else d_str,
                'Match start time': d_str.split(' ')[1] if ' ' in d_str else '12:00:00', 'Tournament': b['league'],
                'Map number': int(m_num), 'Team 1': b['teamname'], 'Team 2': r['teamname'], 'Team 1 baseline (%)': '50%',
                'Map winner': b['teamname'] if b['result'] == 1 else r['teamname'], 'Team 1 kills': t1_k, 'Team 2 kills': t2_k,
                'Total kills': t1_k + t2_k, 'Total minutes': f"{ts//60:02d}:{ts%60:02d}",
                'FB': b['teamname'] if b['firstblood'] == 1 else (r['teamname'] if r['firstblood'] == 1 else 'None'), 'F10': f10,
                '1st tower': b['teamname'] if b['firsttower'] == 1 else (r['teamname'] if r['firsttower'] == 1 else 'None'), 'Total towers': int(b['towers'] + r['towers']),
                '1st dragon': b['teamname'] if b['firstdragon'] == 1 else (r['teamname'] if r['firstdragon'] == 1 else 'None'), 'Total dragons': int(b['dragons'] + r['dragons']),
                '1st nashor': b['teamname'] if b['firstbaron'] == 1 else (r['teamname'] if r['firstbaron'] == 1 else 'None'), 'Total nashors': int(b['barons'] + r['barons']),
                '1st inhibitor': f_inh, 'Total inhibitors': b_inh + r_inh,
                'Last pick map winner': "YES" if r['result'] == 1 else "NO", 'Red side map winner': "YES" if r['result'] == 1 else "NO"
            })
    return parsed

@st.cache_data(ttl=3600)
def load_csv(source):
    d = pd.read_csv(source, low_memory=False).copy()
    d['parsed_datetime'] = pd.to_datetime(d['date'], errors='coerce')
    d['date_only'] = d['parsed_datetime'].dt.date
    return d

st.title(t["title"])
st.sidebar.header("📁 Джерело даних" if lang == "uk" else "📁 Data Source")
uploaded_file = st.sidebar.file_uploader("CSV", type=['csv'], label_visibility="collapsed")
with st.sidebar.expander("🔗 Додатково: Завантажити за посиланням" if lang == "uk" else "🔗 Advanced: URL Load"):
    url_input = st.text_input("URL:", value=DEFAULT_GDRIVE_LINK)
    if st.button("Завантажити" if lang == "uk" else "Load"):
        with st.spinner("Завантаження..."): st.session_state['df'] = load_csv(url_input)

if uploaded_file: st.session_state['df'] = load_csv(uploaded_file)
df = st.session_state['df']

if df is None: st.info(t["reminder"])
else:
    t_df = df[df['position'] == 'team'].copy()
    all_t = sorted(t_df['league'].dropna().unique().tolist())
    sel_t = st.multiselect("🏆 Турніри / Tournaments:", options=all_t, default=['LEC', 'LCK', 'LPL'] if all(x in all_t for x in ['LEC', 'LCK', 'LPL']) else all_t[:3])
    
    md, mxd = t_df['date_only'].min(), t_df['date_only'].max()
    s_dates = st.date_input("📅 Дати / Dates:", value=(md, mxd), min_value=md, max_value=mxd)
    sd = ed = s_dates[0] if isinstance(s_dates, (list, tuple)) else s_dates
    if isinstance(s_dates, tuple) and len(s_dates) == 2: sd, ed = s_dates
        
    f_df = t_df[(t_df['league'].isin(sel_t)) & (t_df['date_only'] >= sd) & (t_df['date_only'] <= ed)]
    
    if not f_df.empty:
        s_info = {}
        for gid, g in f_df.groupby('gameid'):
            ts = sorted(g['teamname'].dropna().unique().tolist())
            d = g['date_only'].iloc[0]
            k = f"{d}_{g['league'].iloc[0]}_{' vs '.join(ts)}"
            if k not in s_info: s_info[k] = {'name': k, 'ids': []}
            s_info[k]['ids'].append(gid)
            
        opts = {k: f"{v['name']} ({len(v['ids'])} карт)" for k, v in s_info.items()}
        sel_s = st.multiselect("⚔️ Матчі / Matches:", options=list(opts.keys()), format_func=lambda x: opts[x], default=list(opts.keys())[:3])
        
        if sel_s:
            ids = [gid for k in sel_s for gid in s_info[k]['ids']]
            p_df = pd.DataFrame(parse_games(f_df[f_df['gameid'].isin(ids)]))
            st.dataframe(p_df)
            
            st.markdown("---")
            c1, c2 = st.columns(2)
            st.session_state['sheet_url'] = c1.text_input("URL Google Sheets:", value=st.session_state['sheet_url'])
            st.session_state['sheet_name'] = c2.text_input("Sheet Name:", value=st.session_state['sheet_name'])
            
            if st.button(t["export_btn"]):
                with st.spinner(t["writing"]):
                    succ, msg = append_to_sheet(st.session_state['sheet_url'], st.session_state['sheet_name'], p_df.to_dict('records'))
                    if succ: st.success(msg)
                    else: st.error(msg)