import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="Профіль команд | LoL", layout="wide")

lang_choice = st.sidebar.radio("Language", ["Українська", "English"], label_visibility="collapsed")
lang = "uk" if lang_choice == "Українська" else "en"

st.title("🛡️ Профіль команд та Предикт матчу" if lang == "uk" else "🛡️ Team Profile & Match Predictor")

# Отримуємо базу з кешу
df = st.session_state.get('df', None)

if df is None:
    st.info("👋 Завантажте файл бази на головній сторінці, щоб використовувати цей інструмент." if lang == "uk" else "👋 Load the database file on the main page to use this tool.")
else:
    # Залишаємо тільки командну статистику
    teams_df = df[df['position'] == 'team'].copy()
    
    # Фільтри для вибірки даних (щоб аналізувати свіжі дані)
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ Налаштування вибірки" if lang == "uk" else "⚙️ Sample Settings")
    all_tournaments = sorted(teams_df['league'].dropna().unique().tolist())
    sel_tournaments = st.sidebar.multiselect(
        "Турніри:" if lang == "uk" else "Tournaments:", 
        options=all_tournaments, 
        default=all_tournaments
    )
    
    min_d, max_d = teams_df['date_only'].min(), teams_df['date_only'].max()
    sel_dates = st.sidebar.date_input("Період:" if lang == "uk" else "Period:", value=(min_d, max_d))
    s_date = e_date = sel_dates[0] if isinstance(sel_dates, (list, tuple)) else sel_dates
    if isinstance(sel_dates, tuple) and len(sel_dates) == 2: s_date, e_date = sel_dates
        
    f_df = teams_df[(teams_df['league'].isin(sel_tournaments)) & (teams_df['date_only'] >= s_date) & (teams_df['date_only'] <= e_date)]
    
    teams_list = sorted(f_df['teamname'].dropna().unique().tolist())
    
    if len(teams_list) < 2:
        st.warning("За обраними фільтрами недостатньо команд." if lang == "uk" else "Not enough teams based on selected filters.")
    else:
        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1: team1 = st.selectbox("🔵 Команда 1" if lang == "uk" else "🔵 Team 1", options=teams_list, index=0)
        with c2: team2 = st.selectbox("🔴 Команда 2" if lang == "uk" else "🔴 Team 2", options=teams_list, index=1)
        
        # Витягуємо статистику обох команд
        t1_data = f_df[f_df['teamname'] == team1]
        t2_data = f_df[f_df['teamname'] == team2]
        
        if not t1_data.empty and not t2_data.empty:
            
            # === ЛОГІКА ПРЕДИКТУ ===
            
            # 1. Предикт для кожної команди окремо (залишаємо як було, бо це їхня індивідуальна сила)
            t1_avg_kills = t1_data['kills'].median()
            t1_avg_deaths = t1_data['deaths'].median()
            t2_avg_kills = t2_data['kills'].median()
            t2_avg_deaths = t2_data['deaths'].median()
            
            t1_expected_kills = (t1_avg_kills + t2_avg_deaths) / 2
            t2_expected_kills = (t2_avg_kills + t1_avg_deaths) / 2
            
            # 2. НОВИЙ ТОТАЛ МАТЧУ (за твоєю логікою)
            # Рахуємо медіану ЗАГАЛЬНИХ кілів у матчах першої команди (її кіли + смерті)
            t1_median_total = (t1_data['kills'] + t1_data['deaths']).median()
            # Рахуємо медіану ЗАГАЛЬНИХ кілів у матчах другої команди
            t2_median_total = (t2_data['kills'] + t2_data['deaths']).median()
            
            # Беремо середнє арифметичне від двох медіан тоталів
            total_expected = (t1_median_total + t2_median_total) / 2
            
            st.header("🎯 Предикт матчу" if lang == "uk" else "🎯 Match Prediction")
            
            p_col1, p_col2, p_col3 = st.columns(3)
            p_col1.metric(f"Очікувані кіли {team1}", f"{t1_expected_kills:.1f}")
            p_col2.metric(f"Загальний Тотал (O/U)", f"{total_expected:.1f}")
            p_col3.metric(f"Очікувані кіли {team2}", f"{t2_expected_kills:.1f}")
            
            # === РОЗПОДІЛ КІЛІВ У ЧАСІ (ТИМЛАЙН) ===
            st.subheader("📈 Темп гри (Вбивства по хвилинах)" if lang == "uk" else "📈 Game Pace (Kills by minutes)")
            st.write("Скільки в середньому вбивств робить команда на певній стадії гри." if lang == "uk" else "Average kills a team secures at different stages of the game.")
            
            # Збираємо середні значення для графіку (10 хв, 15 хв, Кінець гри)
            # Використовуємо pd.to_numeric для безпеки, бо дані можуть мати пропуски (LPL часто не має стат на 10/15 хв)
            # Використовуємо медіану для тимлайну
            t1_k10 = pd.to_numeric(t1_data['killsat10'], errors='coerce').median()
            t1_k15 = pd.to_numeric(t1_data['killsat15'], errors='coerce').median()
            
            t2_k10 = pd.to_numeric(t2_data['killsat10'], errors='coerce').median()
            t2_k15 = pd.to_numeric(t2_data['killsat15'], errors='coerce').median()
            
            timeline_data = {
                "Етап гри" if lang == "uk" else "Game Stage": ["10 хв (Early)", "15 хв (Mid)", "Кінець гри (End)"],
                team1: [t1_k10, t1_k15, t1_avg_kills],
                team2: [t2_k10, t2_k15, t2_avg_kills]
            }
            
            df_timeline = pd.DataFrame(timeline_data).set_index("Етап гри" if lang == "uk" else "Game Stage")
            st.line_chart(df_timeline)
            
            # === ЕКОНОМІКА (ЗОЛОТО НА 15 ХВИЛИНІ) ===
            st.markdown("---")
            st.subheader("💰 Економіка (Різниця золота на 15 хв)" if lang == "uk" else "💰 Economy (Gold Diff at 15)")
            
            e_col1, e_col2 = st.columns(2)
            
            # Рахуємо Gold Diff за медіаною
            t1_gd15 = pd.to_numeric(t1_data['golddiffat15'], errors='coerce').median()
            t2_gd15 = pd.to_numeric(t2_data['golddiffat15'], errors='coerce').median()
            
            # Стрілочки і кольори
            t1_color = "normal" if t1_gd15 > 0 else "inverse"
            t2_color = "normal" if t2_gd15 > 0 else "inverse"
            
            e_col1.metric(f"Середня перевага {team1}", f"{t1_gd15:.0f} Gold", delta=f"{t1_gd15:.0f}", delta_color=t1_color)
            e_col2.metric(f"Середня перевага {team2}", f"{t2_gd15:.0f} Gold", delta=f"{t2_gd15:.0f}", delta_color=t2_color)
            
            st.caption("Позитивне значення означає, що команда зазвичай перемагає на лініях. Негативне - команда частіше програє старт гри." if lang == "uk" else "Positive means the team usually wins lanes. Negative means they lose the early game.")