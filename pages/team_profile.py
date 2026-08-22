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
            
            # === ЛОГІКА ПРЕДИКТУ ===
            
            # 1. Рахуємо медіани кілів та смертей для кожної команди (їхній типовий виступ)
            t1_avg_kills = t1_data['kills'].median()
            t1_avg_deaths = t1_data['deaths'].median()
            t2_avg_kills = t2_data['kills'].median()
            t2_avg_deaths = t2_data['deaths'].median()
            
            # 2. Індивідуальний предикт: шукаємо баланс між "Вмінням вбивати" Т1 та "Вмінням не вмирати" Т2
            t1_expected_kills = (t1_avg_kills + t2_avg_deaths) / 2
            t2_expected_kills = (t2_avg_kills + t1_avg_deaths) / 2
            
            # 3. Загальний тотал - це просто сума очікуваних індивідуальних кілів обох команд
            total_expected = t1_expected_kills + t2_expected_kills
            
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