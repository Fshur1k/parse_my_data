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
            
            # --- МАТЕМАТИЧНА МОДЕЛЬ ---
            def get_tier_multiplier(league):
                l = str(league).upper()
                if l in ['LCK', 'LPL', 'LEC', 'MSI', 'WCS']: return 15.0 # S-Tier
                if l in ['LCS', 'CBLOL', 'PCS', 'VCS', 'LLA', 'LJL', 'EMEA MASTERS']: return 17.5 # A-Tier
                return 19.0 # B-Tier
                
            def norm_cdf(x, mu, sigma):
                """Кумулятивна функція нормального розподілу"""
                return 0.5 * (1 + math.erf((x - mu) / (sigma * math.sqrt(2))))

            def get_markets(mo_val, margin=0.075):
                """Розрахунок ринків тоталу з маржею 7.5%"""
                if mo_val <= 0: mo_val = 0.1
                line = round(mo_val * 2) / 2
                if line % 1 == 0: line -= 0.5 
                std_dev = math.sqrt(mo_val)
                p_under = norm_cdf(line, mu=mo_val, sigma=std_dev)
                p_over = 1.0 - p_under
                return line, round(1 / (p_over * (1 + margin)), 2), round(1 / (p_under * (1 + margin)), 2)

            def get_hdp_markets(mu_diff, raw_total, margin=0.075):
                """Розрахунок точних коефіцієнтів на фору"""
                # Знаходимо найближчу лінію фори (.5)
                if mu_diff >= 0: base_line = math.floor(mu_diff) + 0.5
                else: base_line = math.ceil(mu_diff) - 0.5
                
                h1 = -base_line
                h2 = base_line
                std_dev = math.sqrt(raw_total)
                
                # Ймовірність того, що Команда 1 покриє фору (D > -h1)
                p_t1 = 1 - norm_cdf(-h1, mu=mu_diff, sigma=std_dev)
                p_t2 = 1 - p_t1
                return h1, h2, round(1 / (p_t1 * (1 + margin)), 2), round(1 / (p_t2 * (1 + margin)), 2)

            # --- ІНТЕРФЕЙС ТА ЛОГІКА ---
            current_league = f_df['league'].iloc[0]
            tier_multiplier = get_tier_multiplier(current_league)
            
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
            
            # --- 1. РОЗРАХУНОК ОЧІКУВАНЬ (СИРІ ДАНІ) ---
            # 1.1 Тотал
            t1_median_total = (t1_data['kills'] + t1_data['deaths']).median()
            t2_median_total = (t2_data['kills'] + t2_data['deaths']).median()
            raw_total = (t1_median_total + t2_median_total) / 2
            
            # 1.2 Очікувана різниця в кілах (Математичне сподівання)
            p_fav = t1_prob if t1_prob >= 0.5 else t2_prob
            diff_magnitude = tier_multiplier * math.sqrt(p_fav - 0.5)
            mu_diff = diff_magnitude if t1_prob >= 0.5 else -diff_magnitude
            
            # 1.3 Індивідуальні тотали (Сирі)
            it1_raw = (raw_total + mu_diff) / 2
            it2_raw = (raw_total - mu_diff) / 2

            # --- 2. РОЗРАХУНОК РИНКІВ (КФ З МАРЖЕЮ) ---
            t_line, t_o, t_u = get_markets(raw_total)
            it1_line, it1_o, it1_u = get_markets(it1_raw)
            it2_line, it2_o, it2_u = get_markets(it2_raw)
            h1, h2, ho1, ho2 = get_hdp_markets(mu_diff, raw_total)
            
            # --- 3. ГЕНЕРАЦІЯ БУКМЕКЕРСЬКОЇ ТАБЛИЦІ (MAIN MARKET) ---
            st.markdown("---")
            st.subheader("📊 Main markets (Основна лінія)" if lang == "uk" else "📊 Main Markets")
            st.caption(f"Турнір: {current_league} | Очікувана різниця: {mu_diff:+.2f} кілів | Розрахункова маржа: 7.5%")
            
            odds1 = round(1 / (t1_prob * (1 + 0.075)), 2) if t1_prob > 0 else 0
            odds2 = round(1 / (t2_prob * (1 + 0.075)), 2) if t2_prob > 0 else 0

            line_data = pd.DataFrame({
                "Команда" if lang == "uk" else "Team": [team1, team2],
                "Победитель" if lang == "uk" else "Win": [f"{odds1:.2f}", f"{odds2:.2f}"],
                "Фора" if lang == "uk" else "Handicap": [f"{h1:+.1f}", f"{h2:+.1f}"],
                "КФ Фора" if lang == "uk" else "HDP Odds": [f"{ho1:.2f}", f"{ho2:.2f}"], 
                "Тотал" if lang == "uk" else "Total": [f"{t_line}", ""],
                "ТБ" if lang == "uk" else "Over": [f"{t_o:.2f}", ""],
                "ТМ" if lang == "uk" else "Under": [f"{t_u:.2f}", ""],
                "Инд. Тотал" if lang == "uk" else "Ind. Total": [f"{it1_line}", f"{it2_line}"],
                "ІТБ" if lang == "uk" else "I.Over": [f"{it1_o:.2f}", f"{it2_o:.2f}"],
                "ІТМ" if lang == "uk" else "I.Under": [f"{it1_u:.2f}", f"{it2_u:.2f}"]
            })
            
            st.dataframe(line_data, hide_index=True, use_container_width=True)

            # --- 4. РОЗШИРЕНИЙ РОЗПИС (АЛЬТЕРНАТИВНІ ЛІНІЇ) ---
            st.markdown("---")
            st.subheader("📈 Розширений розпис (Альтернативні лінії)" if lang == "uk" else "📈 Alternative Markets")
            
            alt_c1, alt_c2, alt_c3 = st.columns(3)
            
            # 4.1 Альтернативні Фори
            hdp_list = []
            for offset in [2.0, 1.0, 0.0, -1.0, -2.0]:
                curr_h1 = h1 + offset
                curr_h2 = -curr_h1
                # Розрахунок точних КФ для зсунутої фори
                _, _, c_ho1, c_ho2 = get_hdp_markets(mu_diff, raw_total) # dummy call just to get func logic
                # Реальна логіка ймовірностей:
                std_d = math.sqrt(raw_total)
                p1 = 1 - norm_cdf(-curr_h1, mu=mu_diff, sigma=std_d)
                p2 = 1 - p1
                co1 = round(1 / (p1 * (1 + 0.075)), 2) if p1 > 0 else 0
                co2 = round(1 / (p2 * (1 + 0.075)), 2) if p2 > 0 else 0
                
                prefix = "🔥 " if offset == 0 else ""
                hdp_list.append({
                    "Фора 1" if lang == "uk" else "HDP 1": f"{prefix}{curr_h1:+.1f}",
                    "КФ 1" if lang == "uk" else "Odds 1": f"{co1:.2f}",
                    "Фора 2" if lang == "uk" else "HDP 2": f"{curr_h2:+.1f}",
                    "КФ 2" if lang == "uk" else "Odds 2": f"{co2:.2f}"
                })
                
            with alt_c1:
                st.caption(f"**Фора ({team1} / {team2})**")
                st.dataframe(pd.DataFrame(hdp_list), hide_index=True, use_container_width=True)

            # 4.2 Альтернативний Загальний Тотал
            tot_list = []
            for offset in [2.0, 1.0, 0.0, -1.0, -2.0]:
                curr_t = t_line + offset
                std_t = math.sqrt(raw_total)
                p_u = norm_cdf(curr_t, mu=raw_total, sigma=std_t)
                p_o = 1.0 - p_u
                co = round(1 / (p_o * (1 + 0.075)), 2) if p_o > 0 else 0
                cu = round(1 / (p_u * (1 + 0.075)), 2) if p_u > 0 else 0
                
                prefix = "🔥 " if offset == 0 else ""
                tot_list.append({
                    "Тотал" if lang == "uk" else "Total": f"{prefix}{curr_t}",
                    "Більше" if lang == "uk" else "Over": f"{co:.2f}",
                    "Менше" if lang == "uk" else "Under": f"{cu:.2f}"
                })
                
            with alt_c2:
                st.caption("**Загальний Тотал (Матч)**" if lang == "uk" else "**Total Kills (Match)**")
                st.dataframe(pd.DataFrame(tot_list), hide_index=True, use_container_width=True)
                
            # 4.3 Альтернативні Індивідуальні Тотали
            it_list = []
            for offset in [2.0, 1.0, 0.0, -1.0, -2.0]:
                curr_it1 = it1_line + offset
                curr_it2 = it2_line + offset
                
                s1 = math.sqrt(it1_raw)
                p_u1 = norm_cdf(curr_it1, mu=it1_raw, sigma=s1)
                co1 = round(1 / ((1-p_u1) * (1 + 0.075)), 2)
                cu1 = round(1 / (p_u1 * (1 + 0.075)), 2)
                
                s2 = math.sqrt(it2_raw)
                p_u2 = norm_cdf(curr_it2, mu=it2_raw, sigma=s2)
                co2 = round(1 / ((1-p_u2) * (1 + 0.075)), 2)
                cu2 = round(1 / (p_u2 * (1 + 0.075)), 2)
                
                prefix = "🔥 " if offset == 0 else ""
                it_list.append({
                    "ІТ 1" if lang == "uk" else "IT 1": f"{prefix}{curr_it1}",
                    "Б (1)": f"{co1:.2f}",
                    "М (1)": f"{cu1:.2f}",
                    "ІТ 2" if lang == "uk" else "IT 2": f"{prefix}{curr_it2}",
                    "Б (2)": f"{co2:.2f}",
                    "М (2)": f"{cu2:.2f}"
                })
                
            with alt_c3:
                st.caption(f"**Інд. Тотали ({team1[:3]}. / {team2[:3]}.)**" if lang == "uk" else "**Ind. Totals**")
                st.dataframe(pd.DataFrame(it_list), hide_index=True, use_container_width=True)