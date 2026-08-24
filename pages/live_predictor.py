import streamlit as st
import pandas as pd
import numpy as np
import time

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

    t1_time = safe_median(t1_data['gamelength']) / 60
    t2_time = safe_median(t2_data['gamelength']) / 60
    expected_length = (t1_time + t2_time) / 2
    
    t1_k10_tot = safe_median(t1_data['killsat10']) + safe_median(t1_data['opp_killsat10']) if 'opp_killsat10' in t1_data.columns else safe_median(t1_data['killsat10']) * 2
    t2_k10_tot = safe_median(t2_data['killsat10']) + safe_median(t2_data['opp_killsat10']) if 'opp_killsat10' in t2_data.columns else safe_median(t2_data['killsat10']) * 2
    exp_k10 = (t1_k10_tot + t2_k10_tot) / 2

    t1_k15_tot = safe_median(t1_data['killsat15']) + safe_median(t1_data['opp_killsat15']) if 'opp_killsat15' in t1_data.columns else safe_median(t1_data['killsat15']) * 2
    t2_k15_tot = safe_median(t2_data['killsat15']) + safe_median(t2_data['opp_killsat15']) if 'opp_killsat15' in t2_data.columns else safe_median(t2_data['killsat15']) * 2
    exp_k15 = (t1_k15_tot + t2_k15_tot) / 2
    
    t1_total_med = safe_median(t1_data['kills'] + t1_data['deaths'])
    t2_total_med = safe_median(t2_data['kills'] + t2_data['deaths'])
    expected_total = (t1_total_med + t2_total_med) / 2

    # --- СТАН ТАЙМЕРА ---
    if 'timer_running' not in st.session_state: 
        st.session_state.timer_running = False
    if 'timer_seconds' not in st.session_state: 
        st.session_state.timer_seconds = 15.0 * 60.0 # За замовчуванням 15:00
    if 'last_tick' not in st.session_state: 
        st.session_state.last_tick = time.time()

    # Оновлення фонового часу
    now = time.time()
    if st.session_state.timer_running:
        st.session_state.timer_seconds += (now - st.session_state.last_tick)
    st.session_state.last_tick = now

    # --- 2. ВВІД LIVE-ДАНИХ (ТАЙМЕР ТА КІЛИ) ---
    st.markdown("---")
    st.subheader("⏱️ Live Таймер та Рахунок" if lang == "uk" else "⏱️ Live Timer & Score")
    
    # Кнопки управління таймером
    tc1, tc2, tc3, tc4, tc5 = st.columns([1, 1, 1, 1, 1])
    with tc1:
        if st.button("⏸ Пауза" if st.session_state.timer_running else "▶️ Старт", use_container_width=True):
            st.session_state.timer_running = not st.session_state.timer_running
            st.rerun()
    with tc2:
        if st.button("-10 сек", use_container_width=True):
            st.session_state.timer_seconds = max(0.0, st.session_state.timer_seconds - 10)
            st.rerun()
    with tc3:
        if st.button("+10 сек", use_container_width=True):
            st.session_state.timer_seconds += 10
            st.rerun()
            
    # Ручне введення часу
    current_m = int(st.session_state.timer_seconds // 60)
    current_s = int(st.session_state.timer_seconds % 60)
    
    with tc4:
        man_m = st.number_input("Хвилини" if lang == "uk" else "Minutes", min_value=0, max_value=120, value=current_m, step=1)
    with tc5:
        man_s = st.number_input("Секунди" if lang == "uk" else "Seconds", min_value=0, max_value=59, value=current_s, step=1)

    # Синхронізація ручного введення з внутрішнім станом
    if man_m != current_m or man_s != current_s:
        st.session_state.timer_seconds = man_m * 60 + man_s
        st.rerun()

    # Точний дробовий час для математичної моделі
    curr_min_exact = st.session_state.timer_seconds / 60.0

    st.caption("💡 *Коли таймер запущено, він працює у фоні. Інтерфейс оновлюється щоразу, коли ви змінюєте кіли або натискаєте будь-яку кнопку.*" if lang == "uk" else "💡 *Timer runs in background. UI updates whenever you change kills or click a button.*")

    # --- 3. ОЦІНКА СИЛИ ТА РАХУНОК ---
    c_k1, c_k2, c_str = st.columns([1, 1, 2])
    with c_k1:
        curr_k1 = st.number_input(f"⚔️ Кіли {team1}:", min_value=0, max_value=100, value=5, step=1)
    with c_k2:
        curr_k2 = st.number_input(f"⚔️ Кіли {team2}:", min_value=0, max_value=100, value=5, step=1)
    with c_str:
        # Компактне виставлення сили через number_input
        live_prob = st.number_input(
            f"⚖️ Шанс на перемогу {team1} (%)" if lang == "uk" else f"⚖️ Win Prob {team1} (%)",
            min_value=1, max_value=99, value=50, step=1,
            help="Використовуйте кнопки +/- для точного налаштування. 50% = Рівна гра." if lang == "uk" else "Use +/- for precise tuning. 50% = Even game."
        )
    
    current_total = curr_k1 + curr_k2
    
    # --- 4. МАТЕМАТИЧНА МОДЕЛЬ ТЕМПУ ---
    exp_len_safe = max(20.0, expected_length)
    x_points = [0, 10, 15, exp_len_safe]
    y_points = [0, exp_k10, exp_k15, expected_total]
    
    if curr_min_exact > exp_len_safe:
        x_points.append(curr_min_exact)
        y_points.append(expected_total + (curr_min_exact - exp_len_safe) * 1.2)
        
    # Використовуємо точний час (з секундами) для максимально плавного предикту
    expected_at_curr_min = np.interp(curr_min_exact, x_points, y_points)
    expected_remaining_base = max(0, expected_total - expected_at_curr_min)
    
    # --- 5. МАНУАЛЬНА СНОУБОЛ КОРЕКЦІЯ ---
    live_lead_intensity = abs((live_prob / 100.0) - 0.5) * 2.0
    max_penalty = 0.55
    snowball_mult = 1.0 - (live_lead_intensity * max_penalty)
    adjusted_remaining = expected_remaining_base * snowball_mult
    
    live_prediction = current_total + adjusted_remaining

    # --- 6. ВІЗУАЛІЗАЦІЯ ---
    st.markdown("---")
    st.subheader("📊 Live Предикт" if lang == "uk" else "📊 Live Prediction")
    
    res_c1, res_c2, res_c3 = st.columns(3)
    res_c1.metric(
        "Залишок кілів (До корекції)" if lang == "uk" else "Remaining Kills (Base)", 
        f"{expected_remaining_base:.1f}"
    )
    
    snowball_diff = adjusted_remaining - expected_remaining_base
    penalty_text = "Рівна гра" if live_lead_intensity < 0.1 else "Відрив по золоту/об'єктах"
    if lang == "en": penalty_text = "Even game" if live_lead_intensity < 0.1 else "Gold/Objective Lead Penalty"
    
    res_c2.metric(
        "Скор. Залишок (Корекція сили)" if lang == "uk" else "Adj. Remaining (Pace Correction)", 
        f"{adjusted_remaining:.1f}", 
        delta=f"{snowball_diff:.1f} ({penalty_text})", 
        delta_color="inverse" if snowball_diff < 0 else "normal"
    )
    
    res_c3.metric(
        "🔥 ПРОГНОЗ (LIVE ТОТАЛ)" if lang == "uk" else "🔥 LIVE PREDICTION", 
        f"{live_prediction:.1f}"
    )