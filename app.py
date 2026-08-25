import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

st.set_page_config(page_title="Експорт Матчів | LoL", layout="wide")

TRANSLATIONS = {
    "uk": {
        "title": "📊 Експорт Матчів у Google Sheets",
        "sidebar_header": "📁 Джерело даних",
        "last_update": "⏳ Останній матч у базі:",
        "export_btn": "🚀 Відправити в Google Sheets",
        "writing": "Записуємо..."
    },
    "en": {
        "title": "📊 Match Exporter for Google Sheets",
        "sidebar_header": "📁 Data Source",
        "last_update": "⏳ Last match in database:",
        "export_btn": "🚀 Send to Google Sheets",
        "writing": "Writing..."
    }
}

lang_choice = st.sidebar.radio("Language", ["Українська", "English"], label_visibility="collapsed")
lang = "uk" if lang_choice == "Українська" else "en"
t = TRANSLATIONS[lang]

# ==========================================
# ⚙️ НАЛАШТУВАННЯ ЗАВАНТАЖЕННЯ
# ==========================================
# Вказуємо назву файлу, який лежить поруч із app.py на GitHub
DEFAULT_FILE_PATH = "2026_LoL_esports_match_data_from_OraclesElixir.csv.zip"

if 'sheet_url' not in st.session_state: st.session_state['sheet_url'] = "https://docs.google.com/spreadsheets/d/1kjn9qTW1tgMNtqRwYCg0bQBWvjC9pJ6K-LZ6-G2o274/edit?gid=0#gid=0"
if 'sheet_name' not in st.session_state: st.session_state['sheet_name'] = "Sheets1"

@st.cache_data(ttl=3600)
def load_csv(source):
    # Визначаємо, чи передали нам рядок (шлях до файлу) чи об'єкт (UploadedFile)
    filename = source.name if hasattr(source, 'name') else str(source)
    
    # Якщо це zip архів, вказуємо компресію
    if filename.endswith('.zip'):
        d = pd.read_csv(source, low_memory=False, compression='zip').copy()
    else:
        d = pd.read_csv(source, low_memory=False).copy()
        
    d['parsed_datetime'] = pd.to_datetime(d['date'], errors='coerce')
    d['date_only'] = d['parsed_datetime'].dt.date
    return d

def get_time_ago(last_date):
    """Форматує час, що пройшов з дати останнього матчу"""
    now = datetime.now().date()
    delta = now - last_date
    days = delta.days
    
    if days <= 0:
        return "Сьогодні" if lang == "uk" else "Today"
    elif days == 1:
        return "1 день тому" if lang == "uk" else "1 day ago"
    elif days % 10 == 1 and days % 100 != 11:
        return f"{days} день тому" if lang == "uk" else f"{days} days ago"
    elif 2 <= days % 10 <= 4 and not (12 <= days % 100 <= 14):
        return f"{days} дні тому" if lang == "uk" else f"{days} days ago"
    else:
        return f"{days} днів тому" if lang == "uk" else f"{days} days ago"

# --- ПРЕДЗАВАНТАЖЕННЯ БАЗИ ---
if 'df' not in st.session_state or st.session_state['df'] is None:
    try:
        st.session_state['df'] = load_csv(DEFAULT_FILE_PATH)
    except Exception as e:
        st.session_state['df'] = None
        st.error(f"Помилка зчитування дефолтного файлу: {e}")

# Допоміжні функції (Google Sheets та Парсинг)
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


# ==========================================
# ОСНОВНИЙ ІНТЕРФЕЙС
# ==========================================
st.title(t["title"])

st.sidebar.header(t["sidebar_header"])

df = st.session_state['df']

# Виводимо інформацію про останній апдейт у боковому меню
if df is not None:
    last_match_date = df['date_only'].max()
    time_ago = get_time_ago(last_match_date)
    st.sidebar.info(f"**{t['last_update']}**\n\n🗓️ {last_match_date} ({time_ago})")

# Залишаємо можливість завантажити новий файл для оновлення
with st.sidebar.expander("📁 Завантажити новий файл" if lang == "uk" else "📁 Upload new file"):
    # ВИПРАВЛЕННЯ 1: Дозволяємо завантажувати і csv, і zip
    uploaded_file = st.file_uploader("CSV / ZIP", type=['csv', 'zip'], label_visibility="collapsed")
    
    # ВИПРАВЛЕННЯ 2: Запобіжник від нескінченного циклу
    # Перевіряємо, чи ми вже завантажували САМЕ ЦЕЙ файл
    if uploaded_file and st.session_state.get('uploaded_filename') != uploaded_file.name: 
        st.session_state['df'] = load_csv(uploaded_file)
        st.session_state['uploaded_filename'] = uploaded_file.name # Запам'ятовуємо ім'я
        st.rerun() # Оновлюємо сторінку лише ОДИН раз

if df is not None:
    t_df = df[df['position'] == 'team'].copy()
    
    # 1. СПОЧАТКУ запитуємо дати (щоб відфільтрувати турніри)
    md, mxd = t_df['date_only'].min(), t_df['date_only'].max()
    s_dates = st.date_input("📅 Дати / Dates:", value=(md, mxd), min_value=md, max_value=mxd)
    
    # Безпечне розпакування дат (якщо обрано лише 1 день або проміжок)
    if isinstance(s_dates, (list, tuple)):
        if len(s_dates) == 0: sd = ed = md
        elif len(s_dates) == 1: sd = ed = s_dates[0]
        else: sd, ed = s_dates[:2]
    else:
        sd = ed = s_dates
        
    # 2. Фільтруємо базу ТІЛЬКИ по датах, щоб отримати актуальні турніри в ці дні
    date_f_df = t_df[(t_df['date_only'] >= sd) & (t_df['date_only'] <= ed)]
    
    all_t = sorted(date_f_df['league'].dropna().unique().tolist())
    
    # Визначаємо дефолтні турніри безпечно
    default_t = [t for t in ['LEC', 'LCK', 'LPL'] if t in all_t]
    if not default_t: default_t = all_t[:3]
    
    # 3. Вибір турнірів (тепер список вже відфільтрований за обраними датами)
    sel_t = st.multiselect("🏆 Турніри / Tournaments:", options=all_t, default=default_t)
    
    # 4. Фінальна вибірка: і по датах, і по турнірах
    f_df = date_f_df[date_f_df['league'].isin(sel_t)]
    
    if not f_df.empty:
        s_info = {}
        for gid, g in f_df.groupby('gameid'):
            ts = sorted(g['teamname'].dropna().unique().tolist())
            d = g['date_only'].iloc[0]
            k = f"{d}_{g['league'].iloc[0]}_{' vs '.join(ts)}"
            if k not in s_info: s_info[k] = {'name': k, 'ids': []}
            s_info[k]['ids'].append(gid)
            
        opts = {k: f"{v['name']} ({len(v['ids'])} карт)" for k, v in s_info.items()}
        
        # 5. ДИНАМІЧНИЙ КЛЮЧ: якщо дати або турнір змінюються, ключ стає іншим. 
        # Це змушує Streamlit "забути" старі матчі і відмалювати список начисто.
        dynamic_key = f"matches_{sd}_{ed}_{'-'.join(sel_t)}"
        
        sel_s = st.multiselect(
            "⚔️ Матчі / Matches:", 
            options=list(opts.keys()), 
            format_func=lambda x: opts[x], 
            default=list(opts.keys())[:3],
            key=dynamic_key
        )
        
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
    else:
        st.warning("За обраними фільтрами не знайдено матчів." if lang == "uk" else "No matches found for the selected filters.")