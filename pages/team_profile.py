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
            
            # --- ОНОВЛЕНА МАТЕМАТИЧНА МОДЕЛЬ (BOOKMAKER MODEL) ---
            def get_tier_multiplier(league):
                l = str(league).upper()
                if l in ['LCK', 'LPL', 'LEC', 'MSI', 'WCS']: return 15.0 
                if l in ['LCS', 'CBLOL', 'PCS', 'VCS', 'LLA', 'LJL', 'EMEA MASTERS']: return 17.5
                return 19.0 
                
            def norm_cdf(x, mu, sigma):
                return 0.5 * (1 + math.erf((x - mu) / (sigma * math.sqrt(2))))

            def get_markets(line, mu, sigma, margin=0.075):
                """Розрахунок коефіцієнтів для тоталів з фіксованою дисперсією"""
                p_u = norm_cdf(line, mu=mu, sigma=sigma)
                p_o = 1.0 - p_u
                oo = round(1 / (p_o * (1 + margin)), 2) if p_o > 0 else 0
                ou = round(1 / (p_u * (1 + margin)), 2) if p_u > 0 else 0
                return oo, ou

            def get_hdp_odds(h1, mu_diff, t1_win_prob, t2_win_prob, sigma_hdp=37.0, margin=0.075):
                """Розрахунок коефіцієнтів для фор із запобіжником на чисту перемогу"""
                p_t1 = 1.0 - norm_cdf(-h1, mu=mu_diff, sigma=sigma_hdp)
                p_t2 = 1.0 - p_t1
                
                if h1 < 0: p_t1 = min(p_t1, t1_win_prob)
                elif h1 > 0: p_t1 = max(p_t1, t1_win_prob) 
                
                h2 = -h1
                if h2 < 0: p_t2 = min(p_t2, t2_win_prob)
                elif h2 > 0: p_t2 = max(p_t2, t2_win_prob)

                o1 = round(1 / (p_t1 * (1 + margin)), 2) if p_t1 > 0 else 0
                o2 = round(1 / (p_t2 * (1 + margin)), 2) if p_t2 > 0 else 0
                return o1, o2

            def get_obj_mo(df1, df2, col, opp_col):
                """Обчислює очікуваний загальний тотал макро-об'єктів для матчу"""
                if opp_col in df1.columns:
                    t1_tot = (pd.to_numeric(df1[col], errors='coerce') + pd.to_numeric(df1[opp_col], errors='coerce')).median()
                    t2_tot = (pd.to_numeric(df2[col], errors='coerce') + pd.to_numeric(df2[opp_col], errors='coerce')).median()
                    res = (t1_tot + t2_tot) / 2
                else:
                    # Якщо немає даних про суперника, просто сумуємо середні показники обох команд
                    res = pd.to_numeric(df1[col], errors='coerce').median() + pd.to_numeric(df2[col], errors='coerce').median()
                return res if not pd.isna(res) else 0

            def calc_line(mo):
                """Знаходить лінію (.5), яка є найближчою до МО (найближче до 50% ймовірності)"""
                if mo >= 0:
                    l = math.floor(mo) + 0.5
                else:
                    l = math.ceil(mo) - 0.5
                # Тотал не може бути від'ємним або нульовим
                return max(0.5, l) if mo >= 0 else l

            # Константи розкиду ліній
            SIGMA_HDP = 37.0
            SIGMA_TOT = 9.0
            SIGMA_IT = 6.0
            SIGMA_TOWERS = 2.5
            SIGMA_DRAGONS = 1.2
            SIGMA_BARONS = 0.8
            SIGMA_INHIBS = 1.0

            # --- ІНТЕРФЕЙС ТА ЛОГІКА ---
            current_league = f_df['league'].iloc[0]
            tier_multiplier = get_tier_multiplier(current_league)
            
            st.markdown("---")
            st.subheader("⚙️ Налаштування мат. моделі" if lang == "uk" else "⚙️ Math Model Settings")
            
            in_c1, in_c2, in_c3 = st.columns([1, 1, 2])
            with in_c1:
                t1_base = st.number_input(f"{team1} (%)", min_value=1.0, max_value=99.0, value=50.0, step=0.5)
            with in_c2:
                t2_base = 100.0 - t1_base
                st.number_input(f"{team2} (%)", value=t2_base, disabled=True)
            
            t1_prob = t1_base / 100.0
            t2_prob = t2_base / 100.0
            
            # --- 1. РОЗРАХУНОК ОЧІКУВАНЬ КІЛІВ (МО) ---
            t1_median_total = (t1_data['kills'] + t1_data['deaths']).median()
            t2_median_total = (t2_data['kills'] + t2_data['deaths']).median()
            raw_total = (t1_median_total + t2_median_total) / 2
            
            p_fav = t1_prob if t1_prob >= 0.5 else t2_prob
            diff_magnitude = tier_multiplier * math.sqrt(p_fav - 0.5)
            mu_diff = diff_magnitude if t1_prob >= 0.5 else -diff_magnitude
            
            it1_raw = (raw_total + mu_diff) / 2
            it2_raw = (raw_total - mu_diff) / 2

            # --- 2. РОЗРАХУНОК ОЧІКУВАНЬ ОБ'ЄКТІВ (МАКРО) ---
            mo_tow = get_obj_mo(t1_data, t2_data, 'towers', 'opp_towers')
            if mo_tow == 0: mo_tow = 12.5 # Fallback
            mo_drag = get_obj_mo(t1_data, t2_data, 'dragons', 'opp_dragons')
            if mo_drag == 0: mo_drag = 4.5
            mo_bar = get_obj_mo(t1_data, t2_data, 'barons', 'opp_barons')
            if mo_bar == 0: mo_bar = 1.5
            mo_inh = get_obj_mo(t1_data, t2_data, 'inhibitors', 'opp_inhibitors')
            if mo_inh == 0: mo_inh = 1.5

            # --- 3. ВИЗНАЧЕННЯ НОМІНАЛЬНИХ ЛІНІЙ (НАЙБЛИЖЧИХ ДО 50%) ---
            raw_h1 = -mu_diff 
            base_h1 = calc_line(raw_h1)
            # Якщо матч ідеально рівний (0), даємо номінальну фору -0.5 для першої команди
            if raw_h1 == 0: base_h1 = -0.5 
            base_h2 = -base_h1
            
            base_t = calc_line(raw_total)
            base_it1 = calc_line(it1_raw)
            base_it2 = calc_line(it2_raw)
            
            l_tow = calc_line(mo_tow)
            l_drag = calc_line(mo_drag)
            l_bar = calc_line(mo_bar)
            l_inh = calc_line(mo_inh)

            # --- 4. ГЕНЕРАЦІЯ БУКМЕКЕРСЬКОЇ ТАБЛИЦІ (MAIN MARKET) ---
            st.markdown("---")
            st.subheader("📊 Main markets (Кіли)" if lang == "uk" else "📊 Main Markets (Kills)")
            st.caption(f"Турнір: {current_league} | Очікувана різниця: {mu_diff:+.2f} кілів | Маржа: 7.5%")
            
            odds1 = round(1 / (t1_prob * (1 + 0.075)), 2) if t1_prob > 0 else 0
            odds2 = round(1 / (t2_prob * (1 + 0.075)), 2) if t2_prob > 0 else 0

            m_ho1, m_ho2 = get_hdp_odds(base_h1, mu_diff, t1_prob, t2_prob, SIGMA_HDP)
            m_to, m_tu = get_markets(base_t, raw_total, SIGMA_TOT)
            m_it1_o, m_it1_u = get_markets(base_it1, it1_raw, SIGMA_IT)
            m_it2_o, m_it2_u = get_markets(base_it2, it2_raw, SIGMA_IT)

            line_data = pd.DataFrame({
                "Команда" if lang == "uk" else "Team": [team1, team2],
                "Победитель" if lang == "uk" else "Win": [f"{odds1:.2f}", f"{odds2:.2f}"],
                "Фора" if lang == "uk" else "Handicap": [f"{base_h1:+.1f}", f"{base_h2:+.1f}"],
                "КФ Фора" if lang == "uk" else "HDP Odds": [f"{m_ho1:.2f}", f"{m_ho2:.2f}"], 
                "Тотал" if lang == "uk" else "Total": [f"{base_t}", ""],
                "ТБ" if lang == "uk" else "Over": [f"{m_to:.2f}", ""],
                "ТМ" if lang == "uk" else "Under": [f"{m_tu:.2f}", ""],
                "Инд. Тотал" if lang == "uk" else "Ind. Total": [f"{base_it1}", f"{base_it2}"],
                "ІТБ" if lang == "uk" else "I.Over": [f"{m_it1_o:.2f}", f"{m_it2_o:.2f}"],
                "ІТМ" if lang == "uk" else "I.Under": [f"{m_it1_u:.2f}", f"{m_it2_u:.2f}"]
            })
            
            st.dataframe(line_data, hide_index=True, use_container_width=True)

            # --- 5. МАКРО-ОБ'ЄКТИ (НОВА ТАБЛИЦЯ) ---
            st.markdown("---")
            st.subheader("🏰 Макро-об'єкти (Тотали)" if lang == "uk" else "🏰 Macro Objectives (Totals)")
            st.caption("Аналіз очікуваної кількості зруйнованих/вбитих об'єктів за матч" if lang == "uk" else "Analysis of expected destroyed/killed objectives per match")
            
            o_tow, u_tow = get_markets(l_tow, mo_tow, SIGMA_TOWERS)
            o_drag, u_drag = get_markets(l_drag, mo_drag, SIGMA_DRAGONS)
            o_bar, u_bar = get_markets(l_bar, mo_bar, SIGMA_BARONS)
            o_inh, u_inh = get_markets(l_inh, mo_inh, SIGMA_INHIBS)

            obj_data = pd.DataFrame({
                "Об'єкт" if lang == "uk" else "Objective": ["🗼 Вежі (Towers)", "🐉 Дракони (Dragons)", "👾 Нашори (Barons)", "🛑 Інгібітори (Inhibs)"],
                "МО (Очікування)" if lang == "uk" else "Expected (MO)": [f"{mo_tow:.2f}", f"{mo_drag:.2f}", f"{mo_bar:.2f}", f"{mo_inh:.2f}"],
                "Лінія" if lang == "uk" else "Line": [f"{l_tow}", f"{l_drag}", f"{l_bar}", f"{l_inh}"],
                "Більше" if lang == "uk" else "Over": [f"{o_tow:.2f}", f"{o_drag:.2f}", f"{o_bar:.2f}", f"{o_inh:.2f}"],
                "Менше" if lang == "uk" else "Under": [f"{u_tow:.2f}", f"{u_drag:.2f}", f"{u_bar:.2f}", f"{u_inh:.2f}"]
            })
            
            st.dataframe(obj_data, hide_index=True, use_container_width=True)

            # --- 6. РОЗШИРЕНИЙ РОЗПИС (АЛЬТЕРНАТИВНІ ЛІНІЇ КІЛІВ) ---
            st.markdown("---")
            st.subheader("📈 Розширений розпис (Альтернативні лінії)" if lang == "uk" else "📈 Alternative Markets")
            
            alt_c1, alt_c2, alt_c3 = st.columns(3)
            
            hdp_list = []
            offsets = [-2.0, -1.0, 0.0, 1.0, 2.0]
            for offset in offsets:
                curr_h1 = base_h1 + offset
                curr_h2 = -curr_h1
                co1, co2 = get_hdp_odds(curr_h1, mu_diff, t1_prob, t2_prob, SIGMA_HDP)
                
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

            tot_list = []
            for offset in [2.0, 1.0, 0.0, -1.0, -2.0]:
                curr_t = base_t + offset
                co, cu = get_markets(curr_t, raw_total, SIGMA_TOT)
                
                prefix = "🔥 " if offset == 0 else ""
                tot_list.append({
                    "Тотал" if lang == "uk" else "Total": f"{prefix}{curr_t}",
                    "Більше" if lang == "uk" else "Over": f"{co:.2f}",
                    "Менше" if lang == "uk" else "Under": f"{cu:.2f}"
                })
                
            with alt_c2:
                st.caption("**Загальний Тотал (Матч)**" if lang == "uk" else "**Total Kills (Match)**")
                st.dataframe(pd.DataFrame(tot_list), hide_index=True, use_container_width=True)
                
            it_list = []
            for offset in [2.0, 1.0, 0.0, -1.0, -2.0]:
                curr_it1 = base_it1 + offset
                curr_it2 = base_it2 + offset
                
                co1, cu1 = get_markets(curr_it1, it1_raw, SIGMA_IT)
                co2, cu2 = get_markets(curr_it2, it2_raw, SIGMA_IT)
                
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