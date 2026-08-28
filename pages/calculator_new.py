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

        # ------------------------------------------------------------------
        # Fearless Draft tracking
        # ------------------------------------------------------------------
        st.session_state.setdefault('fearless_mode', False)
        st.session_state.setdefault('fearless_map', 1)
        st.session_state.setdefault('fearless_used', [])  # ordered list, preserves per-map history
        st.session_state.setdefault('fearless_history', [])  # list of {map, champs}

        roles = {'top': 'Top', 'jng': 'Jungle', 'mid': 'Mid', 'bot': 'ADC', 'sup': 'Support'}
        role_keys = list(roles.keys())

        with st.expander("🚫 Fearless Draft" if lang == "en" else "🚫 Fearless Draft", expanded=st.session_state['fearless_mode']):
            st.session_state['fearless_mode'] = st.checkbox(
                "Увімкнути відстеження Fearless Draft (герої з попередніх карт недоступні)" if lang == "uk"
                else "Enable Fearless Draft tracking (heroes from previous maps become unavailable)",
                value=st.session_state['fearless_mode'],
            )

            if st.session_state['fearless_mode']:
                used_set = set(st.session_state['fearless_used'])
                st.markdown(
                    (f"**Карта {st.session_state['fearless_map']}** — заблоковано героїв: {len(used_set)}"
                     if lang == "uk" else
                     f"**Map {st.session_state['fearless_map']}** — heroes locked out: {len(used_set)}")
                )
                if used_set:
                    st.caption(", ".join(sorted(used_set)))
                else:
                    st.caption("Ще немає заблокованих героїв." if lang == "uk" else "No heroes locked out yet.")

                fc1, fc2 = st.columns([1, 3])
                with fc1:
                    advance_clicked = st.button(
                        "✅ Зафіксувати карту та перейти далі" if lang == "uk" else "✅ Lock map & advance",
                    )
                with fc2:
                    if st.button("♻️ Скинути серію" if lang == "uk" else "♻️ Reset series"):
                        st.session_state['fearless_used'] = []
                        st.session_state['fearless_map'] = 1
                        st.session_state['fearless_history'] = []
                        for r in role_keys:
                            for prefix in ("c1_", "c2_"):
                                st.session_state.pop(f"{prefix}{r}", None)
                        st.rerun()
            else:
                advance_clicked = False

        fearless_on = st.session_state['fearless_mode']
        used_champs = set(st.session_state['fearless_used']) if fearless_on else set()
        available_champs = [c for c in champs_list if c not in used_champs] if fearless_on else champs_list

        st.markdown("---")

        # ------------------------------------------------------------------
        # Kill total prediction input
        # ------------------------------------------------------------------
        pred_col1, pred_col2 = st.columns([1, 3])
        with pred_col1:
            initial_prediction = st.number_input(
                "🎯 Прогнозована лінія кілів" if lang == "uk" else "🎯 Predicted kill line",
                min_value=0.0, value=20.0, step=0.5,
            )

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

        t1_tot, t2_tot = 0.0, 0.0
        sel_champs = []
        # track selections per side/role for fearless lock-in and matchup lookup
        picks = {'1': {}, '2': {}}

        with col1:
            team1 = st.selectbox("Команда 1" if lang=="uk" else "Team 1", options=teams_list, index=0)
            st.markdown("---")
            for r, r_name in roles.items():
                p_list, p_idx = get_team_players(team1, r)
                c_p, c_c = st.columns(2)
                player = c_p.selectbox(r_name, options=p_list, index=p_idx, key=f"1_{r}")
                champ = c_c.selectbox("Пік" if lang=="uk" else "Pick", options=["None"] + available_champs, key=f"c1_{r}")
                if champ != "None":
                    sel_champs.append(champ)
                    picks['1'][r] = champ
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
                champ = c_c.selectbox("Пік" if lang=="uk" else "Pick", options=["None"] + available_champs, key=f"c2_{r}")
                if champ != "None":
                    sel_champs.append(champ)
                    picks['2'][r] = champ
                    mk, wr, src = get_stats(player, champ)
                    t2_tot += mk
                    st.caption(f"🎯 **{mk:.1f}** k. | WR: **{wr:.0f}%** ({src})")

        with col3:
            st.subheader("📊 Аналіз" if lang=="uk" else "📊 Analysis")
            st.metric(team1, f"{t1_tot:.1f} kills")
            st.metric(team2, f"{t2_tot:.1f} kills")

            predicted_total = t1_tot + t2_tot
            diff = predicted_total - initial_prediction
            if diff > 0:
                verdict = "БІЛЬШЕ ⬆️" if lang == "uk" else "OVER ⬆️"
            elif diff < 0:
                verdict = "МЕНШЕ ⬇️" if lang == "uk" else "UNDER ⬇️"
            else:
                verdict = "РІВНО" if lang == "uk" else "PUSH"
            st.metric(
                "Прогноз суми" if lang == "uk" else "Projected total",
                f"{predicted_total:.1f}",
                delta=f"{diff:+.1f} vs {initial_prediction:.1f}",
            )
            st.markdown(f"### {verdict}")

            u_champs = list(set([c for c in sel_champs if c != "None"]))
            if u_champs:
                trend_data = fp[fp['champion'].isin(u_champs)]
                if not trend_data.empty:
                    tg = trend_data.groupby(['patch', 'champion'])['kills'].mean().reset_index()
                    pt = tg.pivot(index='patch', columns='champion', values='kills').reset_index()
                    pt['s_val'] = pt['patch'].apply(patch_val)
                    pt = pt.sort_values('s_val').drop(columns=['s_val']).set_index('patch')
                    st.line_chart(pt)

        # ------------------------------------------------------------------
        # Fearless Draft: lock in this map's picks, advance to next map
        # ------------------------------------------------------------------
        if fearless_on and advance_clicked:
            newly_used = set(picks['1'].values()) | set(picks['2'].values())
            if newly_used:
                st.session_state['fearless_used'] = sorted(used_champs | newly_used)
                st.session_state['fearless_history'].append({
                    'map': st.session_state['fearless_map'],
                    'champs': sorted(newly_used),
                })
                st.session_state['fearless_map'] += 1
                for r in role_keys:
                    st.session_state.pop(f"c1_{r}", None)
                    st.session_state.pop(f"c2_{r}", None)
                st.rerun()
            else:
                st.warning(
                    "Оберіть хоча б одного героя перед фіксацією карти." if lang == "uk"
                    else "Pick at least one hero before locking in the map."
                )

        # ------------------------------------------------------------------
        # Role-based matchups & counterpicks
        # ------------------------------------------------------------------
        st.markdown("---")
        st.subheader("⚔️ Матчапи та контрпіки" if lang == "uk" else "⚔️ Matchups & Counterpicks")

        has_matchup_cols = {'gameid', 'side'}.issubset(fp.columns)

        if not has_matchup_cols:
            st.info(
                "Дані для аналізу матчапів (gameid/side) відсутні у завантаженій базі." if lang == "uk"
                else "Matchup data (gameid/side) isn't available in the loaded dataset."
            )
        else:
            @st.cache_data(show_spinner=False)
            def build_role_matchup_table(fp_role, role):
                """Self-join same game, opposite side, same role -> pair records with result."""
                left = fp_role[['gameid', 'side', 'champion', 'result']].rename(
                    columns={'side': 'side_a', 'champion': 'champion_a', 'result': 'result_a'}
                )
                right = fp_role[['gameid', 'side', 'champion']].rename(
                    columns={'side': 'side_b', 'champion': 'champion_b'}
                )
                merged = left.merge(right, on='gameid')
                merged = merged[merged['side_a'] != merged['side_b']]
                if merged.empty:
                    return merged
                agg = merged.groupby(['champion_a', 'champion_b']).agg(
                    win_rate=('result_a', 'mean'), games=('result_a', 'size')
                ).reset_index()
                return agg

            any_role_shown = False
            for r, r_name in roles.items():
                champ1 = picks['1'].get(r)
                champ2 = picks['2'].get(r)
                if not champ1 and not champ2:
                    continue

                fp_role = fp[fp['position'] == r]
                if fp_role.empty:
                    continue

                matchup_table = build_role_matchup_table(fp_role, r)
                any_role_shown = True

                with st.expander(f"{r_name}: {champ1 or '—'} vs {champ2 or '—'}", expanded=True):
                    if champ1 and champ2 and not matchup_table.empty:
                        head_to_head = matchup_table[
                            (matchup_table['champion_a'] == champ1) & (matchup_table['champion_b'] == champ2)
                        ]
                        if not head_to_head.empty:
                            wr = head_to_head.iloc[0]['win_rate'] * 100
                            games = int(head_to_head.iloc[0]['games'])
                            st.write(
                                (f"**{champ1}** проти **{champ2}**: WR {wr:.0f}% ({games} ігор)" if lang == "uk"
                                 else f"**{champ1}** vs **{champ2}**: {wr:.0f}% win rate ({games} games)")
                            )
                        else:
                            st.caption(
                                "Немає прямих зустрічей у виборці." if lang == "uk"
                                else "No direct meetings in the current sample."
                            )

                    MIN_GAMES = 3
                    mc1, mc2 = st.columns(2)
                    for champ, opp, container in ((champ2, champ1, mc1), (champ1, champ2, mc2)):
                        with container:
                            if not opp:
                                continue
                            st.markdown(
                                (f"Контрпіки проти **{opp}**" if lang == "uk" else f"Counterpicks vs **{opp}**")
                            )
                            counters = matchup_table[
                                (matchup_table['champion_b'] == opp) & (matchup_table['games'] >= MIN_GAMES)
                            ].sort_values('win_rate', ascending=False).head(3)
                            if counters.empty:
                                st.caption("Недостатньо даних." if lang == "uk" else "Not enough data.")
                            else:
                                for _, row in counters.iterrows():
                                    st.caption(f"• {row['champion_a']}: {row['win_rate']*100:.0f}% ({int(row['games'])} G)")

            if not any_role_shown:
                st.caption(
                    "Оберіть героїв в обох командах, щоб побачити матчапи." if lang == "uk"
                    else "Pick heroes for both teams to see matchups."
                )