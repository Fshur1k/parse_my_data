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
    
    # Фільтри для вибірки даних
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ Налаштування вибірки" if lang == "uk" else "⚙️ Sample Settings")
    
    # 1. Турніри
    all_tournaments = sorted(teams_df['league'].dropna().unique().tolist())
    sel_tournaments = st.sidebar.multiselect(
        "Турніри:" if lang == "uk" else "Tournaments:", 
        options=all_tournaments, 
        default=all_tournaments
    )
    
    # 2. Патчі (замість дат)
    def patch_val(p):
        parts = str(p).split('.')
        try: return float(f"{parts[0]}.{int(parts[1]):03d}")
        except: return 0
        
    all_patches = sorted(teams_df['patch'].dropna().unique().tolist(), key=patch_val, reverse=True)
    # За замовчуванням беремо 3 останні патчі
    sel_patches = st.sidebar.multiselect(
        "Патчі:" if lang == "uk" else "Patches:", 
        options=all_patches, 
        default=all_patches[:3] if len(all_patches) >= 3 else all_patches
    )
    
    # 3. Ліміт останніх ігор
    game_counts = [10, 15, 20, 25, 30, 35, 40, 45, 50, "Всі" if lang == "uk" else "All"]
    sel_count = st.sidebar.selectbox(
        "Аналізувати останні ігри:" if lang == "uk" else "Analyze last games:", 
        options=game_counts, 
        index=0 # За замовчуванням стоїть 10 ігор
    )
    
    # Фільтруємо базу за турнірами та патчами
    f_df = teams_df[(teams_df['league'].isin(sel_tournaments)) & (teams_df['patch'].isin(sel_patches))]
    
    teams_list = sorted(f_df['teamname'].dropna().unique().tolist())
    
    if len(teams_list) < 2:
        st.warning("За обраними фільтрами недостатньо команд." if lang == "uk" else "Not enough teams based on selected filters.")
    else:
        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1: team1 = st.selectbox("🔵 Команда 1" if lang == "uk" else "🔵 Team 1", options=teams_list, index=0)
        with c2: team2 = st.selectbox("🔴 Команда 2" if lang == "uk" else "🔴 Team 2", options=teams_list, index=1)
        
        # Витягуємо статистику обох команд і СОРТУЄМО від найсвіжіших ігор до найстаріших
        t1_data = f_df[f_df['teamname'] == team1].sort_values(by='parsed_datetime', ascending=False)
        t2_data = f_df[f_df['teamname'] == team2].sort_values(by='parsed_datetime', ascending=False)
        
        # Застосовуємо ліміт (залишаємо тільки N найсвіжіших ігор для кожної команди)
        if sel_count not in ["Всі", "All"]:
            t1_data = t1_data.head(sel_count)
            t2_data = t2_data.head(sel_count)
        
        if not t1_data.empty and not t2_data.empty:
            
            # === 1. ВБУДОВАНА ТАБЛИЦЯ ФОР ТА КАТЕГОРІЙ ===
            def get_tier(league):
                l = str(league).upper()
                # Розподіл ліг за рівнем макро-гри
                if l in ['LCK', 'LPL', 'LEC', 'MSI', 'WCS']: return 'S'
                if l in ['LCS', 'CBLOL', 'PCS', 'VCS', 'LLA', 'LJL', 'EMEA MASTERS']: return 'A'
                return 'B' # Регіоналки, академії, тір-3
            
            def get_handicap(prob, tier):
                # Конвертуємо ймовірність фаворита у коефіцієнт
                if prob < 0.5: prob = 1.0 - prob
                if prob <= 0: prob = 0.01 
                odds = 1.0 / prob
                
                # Емпірична матриця фор на основі розподілу Скеллама (з історичної бази)
                lookup = {
                    'S': {1.1: 7.5, 1.15: 9.5, 1.2: 8.5, 1.25: 8.5, 1.3: 7.5, 1.35: 7.5, 1.4: 6.5, 1.45: 6.5, 1.5: 6.5, 1.55: 3.5, 1.6: 5.5, 1.65: 4.5, 1.7: 5.5, 1.75: 5.5, 1.8: 2.5, 1.85: 1.5},
                    'A': {1.1: 12.5, 1.15: 11.5, 1.2: 10.5, 1.25: 9.5, 1.3: 7.5, 1.35: 8.5, 1.4: 8.5, 1.45: 7.5, 1.5: 6.5, 1.55: 6.5, 1.6: 5.5, 1.65: 4.5, 1.7: 1.5, 1.75: 4.5, 1.8: 1.5, 1.85: 3.5},
                    'B': {1.1: 13.5, 1.15: 11.5, 1.2: 10.5, 1.25: 9.5, 1.3: 9.5, 1.35: 7.5, 1.4: 7.5, 1.45: 7.5, 1.5: 6.5, 1.55: 5.5, 1.6: 5.5, 1.65: 3.5, 1.7: 3.5, 1.75: 0.5, 1.8: 2.5, 1.85: 0.5}
                }
                # Знаходимо найближчий кеф у таблиці
                closest_odds = min(lookup[tier].keys(), key=lambda k: abs(k - odds))
                return lookup[tier][closest_odds]

            # === 2. ІНТЕРФЕЙС BASELINE ===
            current_league = f_df['league'].iloc[0]
            tourney_tier = get_tier(current_league)
            
            st.markdown("---")
            st.subheader("⚖️ Лінія матчу (Baseline %)" if lang == "uk" else "⚖️ Match Line (Baseline %)")
            
            # Повзунок для виставлення шансів (як на букмекерській карті)
            t1_baseline = st.slider(
                f"Шанс на перемогу {team1} (%)", 
                min_value=1, max_value=99, value=50, step=1,
                help="Встановіть ймовірність перемоги першої команди."
            ) / 100.0
            
            t2_baseline = 1.0 - t1_baseline
            
            # Отримуємо точну фору для цього рівня турніру
            handicap = get_handicap(t1_baseline, tourney_tier)
            
            # === 3. РОЗРАХУНОК ТОТАЛІВ ===
            # Знаходимо чистий загальний тотал гри (Медіана загальних тоталів двох команд)
            t1_median_total = (t1_data['kills'] + t1_data['deaths']).median()
            t2_median_total = (t2_data['kills'] + t2_data['deaths']).median()
            total_expected = (t1_median_total + t2_median_total) / 2
            
            # Розподіляємо кіли за формулою: (Тотал ± Фора) / 2
            if t1_baseline >= 0.5:
                # Команда 1 - фаворит
                t1_expected_kills = (total_expected + handicap) / 2
                t2_expected_kills = (total_expected - handicap) / 2
                fav_name, fav_h = team1, -handicap
            else:
                # Команда 2 - фаворит
                t1_expected_kills = (total_expected - handicap) / 2
                t2_expected_kills = (total_expected + handicap) / 2
                fav_name, fav_h = team2, -handicap
                
            # === 4. ВИВІД ДАНИХ ===
            st.header("🎯 Предикт матчу" if lang == "uk" else "🎯 Match Prediction")
            st.caption(f"🏆 Турнір: {current_league} (Клас: {tourney_tier}-Tier) | Очікувана фора: {fav_name} {fav_h}")
            
            p_col1, p_col2, p_col3 = st.columns(3)
            p_col1.metric(f"Очікувані кіли {team1}", f"{t1_expected_kills:.1f}")
            p_col2.metric(f"Загальний Тотал (O/U)", f"{total_expected:.1f}")
            p_col3.metric(f"Очікувані кіли {team2}", f"{t2_expected_kills:.1f}")