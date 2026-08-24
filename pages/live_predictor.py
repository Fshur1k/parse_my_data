import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="Live Предикт | LoL", layout="wide")

lang_choice = st.sidebar.radio("Language", ["Українська", "English"], label_visibility="collapsed")
lang = "uk" if lang_choice == "Українська" else "en"

st.title("🔴 Live Предикт Тоталів (In-Play)" if lang == "uk" else "🔴 Live Totals Predictor (In-Play)")

df = st.session_state.get('df', None)

if df is None:
    st.info("👋 Завантажте файл бази на головній сторінці." if lang == "uk" else "👋 Load the database file on the main page.")
    st.stop()

teams_df = df[df['position'] == 'team'].copy()

# --- ФІЛЬТРИ ---
st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ Налаштування" if lang == "uk" else "⚙️ Settings")
all_tournaments = sorted(teams_df['league'].dropna().unique().tolist())
sel_tournaments = st.sidebar.multiselect("Турніри:" if lang == "uk" else "Tournaments:", options=all_tournaments, default=all_tournaments)

f_df = teams_df[teams_df['league'].isin(sel_tournaments)]
teams_list = sorted(f_df['teamname'].dropna().unique().tolist())

if len(teams_list) < 2:
    st.warning("Недостатньо команд." if lang == "uk" else "Not enough teams.")
    st.stop()

c1, c2 = st.columns(2)
with c1: team1 = st.selectbox("🔵 Команда 1" if lang == "uk" else "🔵 Team 1", options=teams_list, index=0)
with c2: team2 = st.selectbox("🔴 Команда 2" if lang == "uk" else "🔴 Team 2", options=teams_list, index=1)

t1_data = f_df[f_df['teamname'] == team1]
t2_data = f_df[f_df['teamname'] == team2]

if not t1_data.empty and not t2_data.empty:
    
    # --- 1. PRE-MATCH СТАТИСТИКА (МЕДІАНИ) ---
    def safe_median(series):
        s = pd.to_numeric(series, errors='coerce').dropna()
        return s.median() if not s.empty else 0

    # Очікувані кіли та смерті
    t1_kills, t1_deaths = safe_median(t1_data['kills']), safe_median(t1_data['deaths'])
    t2_kills, t2_deaths = safe_median(t2_data['kills']), safe_median(t2_data['deaths'])
    
    # Очікувана тривалість гри (у хвилинах)
    t1_time = safe_median(t1_data['gamelength']) / 60
    t2_time = safe_median(t2_data['gamelength']) / 60
    expected_length = (t1_time + t2_time) / 2
    
    # Кіли на 10 та 15 хвилинах (Команда + Суперник = Тотал матчу на цій хвилині)
    t1_k10_tot = safe_median(t1_data['killsat10']) + safe_median(t1_data['opp_killsat10']) if 'opp_killsat10' in t1_data.columns else safe_median(t1_data['killsat10']) * 2
    t2_k10_tot = safe_median(t2_data['killsat10']) + safe_median(t2_data['opp_killsat10']) if 'opp_killsat10' in t2_data.columns else safe_median(t2_data['killsat10']) * 2
    exp_k10 = (t1_k10_tot + t2_k10_tot) / 2

    t1_k15_tot = safe_median(t1_data['killsat15']) + safe_median(t1_data['opp_killsat15']) if 'opp_killsat15' in t1_data.columns else safe_median(t1_data['killsat15']) * 2
    t2_k15_tot = safe_median(t2_data['killsat15']) + safe_median(t2_data['opp_killsat15']) if 'opp_killsat15' in t2_data.columns else safe_median(t2_data['killsat15']) * 2
    exp_k15 = (t1_k15_tot + t2_k15_tot) / 2
    
    # Загальний очікуваний тотал (як ми рахували раніше)
    t1_total_med = safe_median(t1_data['kills'] + t1_data['deaths'])
    t2_total_med = safe_median(t2_data['kills'] + t2_data['deaths'])
    expected_total = (t1_total_med + t2_total_med) / 2

    # --- ВВІД LIVE-ДАНИХ ---
    st.markdown("---")
    st.subheader("⏱️ Live Ситуація (Введіть поточні дані)" if lang == "uk" else "⏱️ Live Situation (Enter current data)")
    
    col_t, col_k1, col_k2 = st.columns(3)
    curr_min = col_t.number_input("Поточна хвилина (Min):" if lang == "uk" else "Current Minute:", min_value=1, max_value=60, value=15, step=1)
    curr_k1 = col_k1.number_input(f"Кіли {team1}:", min_value=0, max_value=50, value=5, step=1)
    curr_k2 = col_k2.number_input(f"Кіли {team2}:", min_value=0, max_value=50, value=5, step=1)
    
    current_total = curr_k1 + curr_k2
    
    # --- 2. МАТЕМАТИЧНА МОДЕЛЬ ТЕМПУ (INTERPOLATION) ---
    # Точки для графіка: [Хвилина], [Очікувані Кіли]
    # Запобіжник: якщо очікуваний час менше 15, ставимо хоча б 20
    exp_len_safe = max(20.0, expected_length)
    
    x_points = [0, 10, 15, exp_len_safe]
    y_points = [0, exp_k10, exp_k15, expected_total]
    
    # Якщо поточна хвилина більша за очікуваний кінець, екстраполюємо лінійно
    if curr_min > exp_len_safe:
        x_points.append(curr_min)
        # Додаємо трохи кілів за "лейт-гейм фієсту" (наприклад, 1 кіл на хвилину)
        y_points.append(expected_total + (curr_min - exp_len_safe) * 1.2)
        
    # Розраховуємо очікувану кількість кілів саме на поточну хвилину
    expected_at_curr_min = np.interp(curr_min, x_points, y_points)
    
    # Залишок кілів = Загальний Тотал - Очікувані кіли на даний момент
    # (Не може бути від'ємним)
    expected_remaining_base = max(0, expected_total - expected_at_curr_min)
    
    # Корекція темпу (Pace Adjustment)
    # Якщо команди роблять кіли швидше, ніж очікувалося, гра може закінчитися швидше (снігова куля),
    # АБО вона перетвориться на фієсту. Зазвичай букмекери беруть чистий залишок + поточні кіли.
    pace_diff = current_total - expected_at_curr_min
    
    live_prediction = current_total + expected_remaining_base

    # --- 3. ВІЗУАЛІЗАЦІЯ ---
    st.markdown("---")
    st.subheader("📊 Live Предикт" if lang == "uk" else "📊 Live Prediction")
    
    res_c1, res_c2, res_c3 = st.columns(3)
    res_c1.metric(
        "Очікуваний час гри" if lang == "uk" else "Expected Game Length", 
        f"{expected_length:.1f} хв"
    )
    res_c2.metric(
        "Очікувано кілів на цю хвилину" if lang == "uk" else "Expected Kills at this min", 
        f"{expected_at_curr_min:.1f}", 
        delta=f"{pace_diff:+.1f} (Темп)", delta_color="inverse"
    )
    res_c3.metric(
        "🔥 ПРОГНОЗ (LIVE ТОТАЛ)" if lang == "uk" else "🔥 LIVE PREDICTION", 
        f"{live_prediction:.1f}"
    )
    
    st.caption("Формула: Поточні Кіли + Історично очікуваний залишок кілів для цих команд з поточної хвилини." if lang == "uk" else "Formula: Current Kills + Historically expected remaining kills from this minute.")