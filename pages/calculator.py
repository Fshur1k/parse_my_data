import streamlit as st
import pandas as pd

st.set_page_config(page_title="Калькулятор Піків | LoL", layout="wide")

lang_choice = st.sidebar.radio("Language", ["Українська", "English"], label_visibility="collapsed")
lang = "uk" if lang_choice == "Українська" else "en"

st.title("🧮 Калькулятор Піків" if lang == "uk" else "🧮 Pick Calculator")

# Беремо дані з кешу сесії (якщо завантажено на першій сторінці)
df = st.session_state.get('df', None)

if df is None:
    st.info("👋 Завантажте файл бази на головній сторінці, щоб використовувати калькулятор." if lang == "uk" else "👋 Load the database file on the main page to use the calculator.")
else:
    players_df = df[df['position'] != 'team'].copy()
    players_df['patch'] = players_df['patch'].astype(str).str.replace(',', '.')
    
    teams_list = sorted(players_df['teamname'].dropna().unique().tolist())
    champs_list = sorted(players_df['champion'].dropna().unique().tolist())
    
    if not teams_list:
        st.warning("Дані по гравцях відсутні." if lang == "uk" else "No player data available.")
    else:
        def patch_val(p):
            try: return float(f"{p.split('.')[0]}.{int(p.split('.')[1]):03d}")
            except: return 0
            
        all_patches = sorted(players_df['patch'].unique().tolist())
        last_2_patches = sorted(all_patches, key=patch_val, reverse=True)[:2]

        f_col1, f_col2 = st.columns(2)
        with f_col1:
            sel_dates = st.date_input("📅 Період / Period:", value=(players_df['date_only'].min(), players_df['date_only'].max()))
        with f_col2:
            sel_patches = st.multiselect("🔢 Патчі / Patches:", options=all_patches, default=last_2_patches)
        
        s_date = e_date = sel_dates[0] if isinstance(sel_dates, (list, tuple)) else sel_dates
        if isinstance(sel_dates, tuple) and len(sel_dates) == 2: s_date, e_date = sel_dates
            
        fp = players_df[(players_df['date_only'] >= s_date) & (players_df['date_only'] <= e_date) & (players_df['patch'].isin(sel_patches))]
        
        st.markdown("---")
        col1, col2, col3 = st.columns([1.5, 1.5, 1.2])

        def get_team_players(t_name, role):
            t_df = players_df[(players_df['teamname'] == t_name) & (players_df['position'] == role)]
            if t_df.empty: return ["Невідомо"], 0
            all_p = t_df['playername'].unique().tolist()
            r_df = t_df[t_df['patch'].isin(last_2_patches)]
            def_p = r_df['playername'].value_counts().index[0] if not r_df.empty else t_df['playername'].value_counts().index[0]
            return all_p, (all_p.index(def_p) if def_p in all_p else 0)

        def get_stats(p_name, c_name):
            if not c_name or c_name == "None": return 0, 0, "-"
            p_data = fp[(fp['playername'] == p_name) & (fp['champion'] == c_name)]
            if not p_data.empty: return p_data['kills'].mean(), p_data['result'].mean()*100, "Гравця" if lang=="uk" else "Player"
            c_data = fp[fp['champion'] == c_name]
            if not c_data.empty: return c_data['kills'].mean(), c_data['result'].mean()*100, "Ліги" if lang=="uk" else "League"
            return 0, 0, "-"

        roles = {'top': 'Top', 'jng': 'Jungle', 'mid': 'Mid', 'bot': 'ADC', 'sup': 'Support'}
        t1_tot, t2_tot = 0.0, 0.0
        sel_champs = []

        with col1:
            team1 = st.selectbox("Команда 1" if lang=="uk" else "Team 1", options=teams_list, index=0)
            st.markdown("---")
            for r, r_name in roles.items():
                p_list, p_idx = get_team_players(team1, r)
                c_p, c_c = st.columns(2)
                player = c_p.selectbox(r_name, options=p_list, index=p_idx, key=f"1_{r}")
                champ = c_c.selectbox("Пік" if lang=="uk" else "Pick", options=["None"] + champs_list, key=f"c1_{r}")
                if champ != "None":
                    sel_champs.append(champ)
                    mk, wr, src = get_stats(player, champ)
                    t1_tot += mk
                    st.caption(f"🎯 **{mk:.1f}** k. | WR: **{wr:.0f}%** ({src})")

        with col2:
            team2 = st.selectbox("Команда 2" if lang=="uk" else "Team 2", options=teams_list, index=1 if len(teams_list)>1 else 0)
            st.markdown("---")
            for r, r_name in roles.items():
                p_list, p_idx = get_team_players(team2, r)
                c_p, c_c = st.columns(2)
                player = c_p.selectbox(r_name, options=p_list, index=p_idx, key=f"2_{r}")
                champ = c_c.selectbox("Пік" if lang=="uk" else "Pick", options=["None"] + champs_list, key=f"c2_{r}")
                if champ != "None":
                    sel_champs.append(champ)
                    mk, wr, src = get_stats(player, champ)
                    t2_tot += mk
                    st.caption(f"🎯 **{mk:.1f}** k. | WR: **{wr:.0f}%** ({src})")

        with col3:
            st.subheader("📊 Аналіз" if lang=="uk" else "📊 Analysis")
            st.metric(team1, f"{t1_tot:.1f} kills")
            st.metric(team2, f"{t2_tot:.1f} kills")
            
            u_champs = list(set([c for c in sel_champs if c != "None"]))
            if u_champs:
                trend_data = fp[fp['champion'].isin(u_champs)]
                if not trend_data.empty:
                    tg = trend_data.groupby(['patch', 'champion'])['kills'].mean().reset_index()
                    pt = tg.pivot(index='patch', columns='champion', values='kills').reset_index()
                    pt['s_val'] = pt['patch'].apply(patch_val)
                    pt = pt.sort_values('s_val').drop(columns=['s_val']).set_index('patch')
                    st.line_chart(pt)