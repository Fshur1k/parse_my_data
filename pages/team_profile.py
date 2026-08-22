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
            import math
            
            # --- ФУНКЦІЇ МАТЕМАТИЧНОЇ МОДЕЛІ ---
            def get_tier(league):
                l = str(league).upper()
                if l in ['LCK', 'LPL', 'LEC', 'MSI', 'WCS']: return 'S'
                if l in ['LCS', 'CBLOL', 'PCS', 'VCS', 'LLA', 'LJL', 'EMEA MASTERS']: return 'A'
                return 'B' 
            
            def get_handicap(prob, tier):
                if prob < 0.5: prob = 1.0 - prob
                if prob <= 0: prob = 0.01 
                odds = 1.0 / prob
                
                lookup = {
                    'S': {1.1: 7.5, 1.15: 9.5, 1.2: 8.5, 1.25: 8.5, 1.3: 7.5, 1.35: 7.5, 1.4: 6.5, 1.45: 6.5, 1.5: 6.5, 1.55: 3.5, 1.6: 5.5, 1.65: 4.5, 1.7: 5.5, 1.75: 5.5, 1.8: 2.5, 1.85: 1.5},
                    'A': {1.1: 12.5, 1.15: 11.5, 1.2: 10.5, 1.25: 9.5, 1.3: 7.5, 1.35: 8.5, 1.4: 8.5, 1.45: 7.5, 1.5: 6.5, 1.55: 6.5, 1.6: 5.5, 1.65: 4.5, 1.7: 1.5, 1.75: 4.5, 1.8: 1.5, 1.85: 3.5},
                    'B': {1.1: 13.5, 1.15: 11.5, 1.2: 10.5, 1.25: 9.5, 1.3: 9.5, 1.35: 7.5, 1.4: 7.5, 1.45: 7.5, 1.5: 6.5, 1.55: 5.5, 1.6: 5.5, 1.65: 3.5, 1.7: 3.5, 1.75: 0.5, 1.8: 2.5, 1.85: 0.5}
                }
                closest_odds = min(lookup[tier].keys(), key=lambda k: abs(k - odds))
                return lookup[tier][closest_odds]

            def norm_cdf(x, mu, sigma):
                """Кумулятивна функція нормального розподілу"""
                return 0.5 * (1 + math.erf((x - mu) / (sigma * math.sqrt(2))))

            def get_markets(mo_val, margin=0.075):
                """Розраховує лінію та коефіцієнти з маржею 7.5% на основі сирого МО"""
                if mo_val <= 0: mo_val = 0.1
                
                # Округлюємо до найближчого формату .5
                line = round(mo_val * 2) / 2
                if line % 1 == 0:
                    line -= 0.5 
                    
                std_dev = math.sqrt(mo_val) # Відхилення (наближення до Пуассона)
                
                # Ймовірності
                p_under = norm_cdf(line, mu=mo_val, sigma=std_dev)
                p_over = 1.0 - p_under
                
                # Переведення в КФ із заданою маржею
                odds_over = round(1 / (p_over * (1 + margin)), 2)
                odds_under = round(1 / (p_under * (1 + margin)), 2)
                
                return line, odds_over, odds_under

            # --- ІНТЕРФЕЙС ТА ЛОГІКА ---
            current_league = f_df['league'].iloc[0]
            tourney_tier = get_tier(current_league)
            
            st.markdown("---")
            st.subheader("⚙️ Настройки мат. модели" if lang == "uk" else "⚙️ Math Model Settings")
            
            in_c1, in_c2, in_c3 = st.columns([1, 1, 2])
            with in_c1:
                t1_base = st.number_input(f"{team1} (%)", min_value=1.0, max_value=99.0, value=50.0, step=0.5)
            with in_c2:
                t2_base = 100.0 - t1_base
                st.number_input(f"{team2} (%)", value=t2_base, disabled=True)
            
            t1_prob = t1_base / 100.0
            t2_prob = t2_base / 100.0
            
            handicap = get_handicap(t1_prob, tourney_tier)
            
            # Сире МО для загального тоталу
            t1_median_total = (t1_data['kills'] + t1_data['deaths']).median()
            t2_median_total = (t2_data['kills'] + t2_data['deaths']).median()
            raw_total = (t1_median_total + t2_median_total) / 2
            
            # Розрахунок ринків (Генерує Лінію, КФ Більше, КФ Менше)
            t_line, t_o, t_u = get_markets(raw_total, margin=0.075)
            
            # Розподіл індивідуальних тоталів
            if t1_prob >= 0.5:
                h1, h2 = -handicap, handicap
                it1_raw = (raw_total + handicap) / 2
                it2_raw = (raw_total - handicap) / 2
            else:
                h1, h2 = handicap, -handicap
                it1_raw = (raw_total - handicap) / 2
                it2_raw = (raw_total + handicap) / 2

            it1_line, it1_o, it1_u = get_markets(it1_raw, margin=0.075)
            it2_line, it2_o, it2_u = get_markets(it2_raw, margin=0.075)

            # --- ГЕНЕРАЦІЯ БУКМЕКЕРСЬКОЇ ТАБЛИЦІ ---
            st.markdown("---")
            st.subheader("📊 Match markets" if lang == "uk" else "📊 Match Markets")
            st.caption(f"Турнір: {current_league} | Клас: {tourney_tier}-Tier | Розрахункова маржа: 7.5%")
            
            odds1 = round(1 / (t1_prob * (1 + 0.075)), 2) if t1_prob > 0 else 0
            odds2 = round(1 / (t2_prob * (1 + 0.075)), 2) if t2_prob > 0 else 0

            # Створюємо датафрейм у стилі букмекерської контори
            line_data = pd.DataFrame({
                "Команда" if lang == "uk" else "Team": [team1, team2],
                "Победитель" if lang == "uk" else "Win": [f"{odds1:.2f}", f"{odds2:.2f}"],
                "Фора" if lang == "uk" else "Handicap": [f"{h1:+.1f}", f"{h2:+.1f}"],
                "КФ Фора" if lang == "uk" else "HDP Odds": ["1.86", "1.86"], # Базовий коінфліп з маржею 7.5%
                "Тотал" if lang == "uk" else "Total": [f"{t_line}", ""],
                "ТБ" if lang == "uk" else "Over": [f"{t_o:.2f}", ""],
                "ТМ" if lang == "uk" else "Under": [f"{t_u:.2f}", ""],
                "Инд. Тотал" if lang == "uk" else "Ind. Total": [f"{it1_line}", f"{it2_line}"],
                "ІТБ" if lang == "uk" else "I.Over": [f"{it1_o:.2f}", f"{it2_o:.2f}"],
                "ІТМ" if lang == "uk" else "I.Under": [f"{it1_u:.2f}", f"{it2_u:.2f}"]
            })
            
            st.dataframe(line_data, hide_index=True, use_container_width=True)