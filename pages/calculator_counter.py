import itertools
import streamlit as st
import pandas as pd

from data_loader import DEFAULT_FILE_PATH, get_active_dataframe

st.set_page_config(page_title="Калькулятор Піків | LoL", layout="wide")

lang_choice = st.sidebar.radio("Language", ["Українська", "English"], label_visibility="collapsed")
lang = "uk" if lang_choice == "Українська" else "en"

st.title("🧮 Калькулятор Піків" if lang == "uk" else "🧮 Pick Calculator")

# ==========================================================================
# Hero icons (Data Dragon)
# [Assuming outbound internet access to ddragon.leagueoflegends.com is available
#  in the deployment environment. A Data Dragon version is pinned rather than
#  looked up live, since the dataset doesn't track per-patch asset versions and
#  DDragon retains historical assets under any recent version string. Native
#  Streamlit selectboxes can't render icons inside the dropdown itself, so the
#  icon is shown as visual confirmation right below each pick once selected.]
# ==========================================================================
DDRAGON_VERSION = "14.24.1"
CHAMPION_ID_OVERRIDES = {
    "Wukong": "MonkeyKing", "Renata Glasc": "Renata", "Nunu & Willump": "Nunu",
    "Bel'Veth": "Belveth", "Cho'Gath": "Chogath", "Kai'Sa": "Kaisa",
    "Kha'Zix": "Khazix", "Vel'Koz": "Velkoz", "K'Sante": "KSante",
    "LeBlanc": "Leblanc", "Dr. Mundo": "DrMundo", "Jarvan IV": "JarvanIV",
    "Master Yi": "MasterYi", "Miss Fortune": "MissFortune", "Tahm Kench": "TahmKench",
    "Twisted Fate": "TwistedFate", "Xin Zhao": "XinZhao", "Aurelion Sol": "AurelionSol",
    "Rek'Sai": "RekSai", "Fiddlesticks": "Fiddlesticks",
}

def champion_icon_url(champion_name):
    if not champion_name or champion_name == "None":
        return None
    cid = CHAMPION_ID_OVERRIDES.get(champion_name) or "".join(ch for ch in champion_name if ch.isalnum())
    return f"https://ddragon.leagueoflegends.com/cdn/{DDRAGON_VERSION}/img/champion/{cid}.png"

def icon_html(champion_name, size=20):
    url = champion_icon_url(champion_name)
    if not url:
        return ""
    return f'<img src="{url}" width="{size}" style="vertical-align:middle;border-radius:3px;margin-right:4px;">'

# Беремо спільний датасет (єдина копія на весь застосунок, а не на кожну сесію)
df = get_active_dataframe(DEFAULT_FILE_PATH)

if df is None:
    st.info("👋 Завантажте файл бази на головній сторінці, щоб використовувати калькулятор." if lang == "uk" else "👋 Load the database file on the main page to use the calculator.")
else:
    players_df = df[df['position'] != 'team'].copy()
    players_df['patch'] = players_df['patch'].astype(str).str.replace(',', '.')

    # [Assuming 'playoffs' (0/1) exists on player-level rows too, mirroring app.py's
    #  parse_games() usage of the same column on team-level rows — used to derive Stage.]
    has_stage_col = 'playoffs' in players_df.columns
    if has_stage_col:
        players_df['stage'] = players_df['playoffs'].apply(
            lambda x: 'Playoffs' if pd.notna(x) and x == 1 else 'Group Stage'
        )

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

        if has_stage_col:
            f_col1, f_col2, f_col3 = st.columns(3)
        else:
            f_col1, f_col2 = st.columns(2)
            f_col3 = None

        with f_col1:
            sel_dates = st.date_input("📅 Період / Period:", value=(players_df['date_only'].min(), players_df['date_only'].max()))
        with f_col2:
            sel_patches = st.multiselect("🔢 Патчі / Patches:", options=all_patches, default=last_2_patches)

        STAGE_ALL = "Всі" if lang == "uk" else "All"
        sel_stage = STAGE_ALL
        if has_stage_col:
            with f_col3:
                sel_stage = st.selectbox("🏟️ Стадія / Stage:", options=[STAGE_ALL, "Group Stage", "Playoffs"])

        s_date = e_date = sel_dates[0] if isinstance(sel_dates, (list, tuple)) else sel_dates
        if isinstance(sel_dates, tuple) and len(sel_dates) == 2: s_date, e_date = sel_dates

        fp = players_df[(players_df['date_only'] >= s_date) & (players_df['date_only'] <= e_date) & (players_df['patch'].isin(sel_patches))]
        if has_stage_col and sel_stage != STAGE_ALL:
            fp = fp[fp['stage'] == sel_stage]

        # ------------------------------------------------------------------
        # Fearless Draft tracking
        # ------------------------------------------------------------------
        st.session_state.setdefault('fearless_mode', False)
        st.session_state.setdefault('fearless_map', 1)
        st.session_state.setdefault('fearless_used', [])  # ordered list, preserves per-map history
        st.session_state.setdefault('fearless_history', [])  # list of {map, champs}

        roles = {'top': 'Top', 'jng': 'Jungle', 'mid': 'Mid', 'bot': 'ADC', 'sup': 'Support'}
        role_keys = list(roles.keys())

        with st.expander("🚫 Fearless Draft", expanded=st.session_state['fearless_mode']):
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
                    st.markdown(f"{icon_html(champ)}🎯 **{mk:.1f}** k. | WR: **{wr:.0f}%** ({src})", unsafe_allow_html=True)

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
                    st.markdown(f"{icon_html(champ)}🎯 **{mk:.1f}** k. | WR: **{wr:.0f}%** ({src})", unsafe_allow_html=True)

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
        # Charts: (1) team rating trend, (2) expected kill distribution
        # ------------------------------------------------------------------
        st.markdown("---")
        st.subheader("📈 Тренд рейтингу та розподіл кілів" if lang == "uk" else "📈 Rating Trend & Kill Distribution")

        team1_champs = list(picks['1'].values())
        team2_champs = list(picks['2'].values())

        # --- Chart 1: team rating trend across selected patches ---
        st.markdown("**" + ("Тренд рейтингу команд (WR% обраних героїв по патчах)" if lang == "uk"
                             else "Team rating trend (selected-hero WR% by patch)") + "**")

        def team_rating_by_patch(champ_list):
            if not champ_list:
                return None
            sub = fp[fp['champion'].isin(champ_list)]
            if sub.empty:
                return None
            return sub.groupby('patch', observed=True)['result'].mean() * 100

        t1_trend = team_rating_by_patch(team1_champs)
        t2_trend = team_rating_by_patch(team2_champs)

        rating_series = {}
        if t1_trend is not None: rating_series[team1] = t1_trend
        if t2_trend is not None: rating_series[team2] = t2_trend

        if rating_series:
            rating_df = pd.DataFrame(rating_series)
            rating_df = rating_df.reindex(sorted(rating_df.index.tolist(), key=patch_val))
            st.line_chart(rating_df)

            # Aggregate readout: the line chart alone doesn't label its endpoints,
            # so surface the average WR and the direction of travel explicitly.
            agg_cols = st.columns(len(rating_series))
            for agg_col, (name, _series) in zip(agg_cols, rating_series.items()):
                ordered = rating_df[name].dropna()
                avg_val = ordered.mean() if not ordered.empty else None
                trend_delta = ordered.iloc[-1] - ordered.iloc[0] if len(ordered) >= 2 else None
                with agg_col:
                    st.metric(
                        f"{name}: {'середній WR' if lang == 'uk' else 'avg WR'}",
                        f"{avg_val:.0f}%" if avg_val is not None else "—",
                        delta=f"{trend_delta:+.0f}pp" if trend_delta is not None else None,
                    )
        else:
            st.caption(
                "Оберіть героїв хоча б для однієї команди, щоб побачити тренд рейтингу." if lang == "uk"
                else "Pick heroes for at least one team to see the rating trend."
            )

        # --- Chart 2: expected kill distribution across the map ---
        st.markdown("**" + ("Прогнозований розподіл кілів по карті" if lang == "uk"
                             else "Expected kill distribution across the map") + "**")

        cols_lower = {c.lower(): c for c in fp.columns}
        timeline_keys = ['killsat10', 'killsat15', 'killsat20', 'killsat25']
        has_timeline_cols = all(k in cols_lower for k in timeline_keys)

        if has_timeline_cols:
            c10, c15, c20, c25 = (cols_lower[k] for k in timeline_keys)

            def team_kill_distribution_timeline(champ_list):
                totals = {"0-10": 0.0, "10-15": 0.0, "15-20": 0.0, "20-25": 0.0, "25+": 0.0}
                found_any = False
                for c in champ_list:
                    sub = fp[fp['champion'] == c]
                    if sub.empty:
                        continue
                    found_any = True
                    a10, a15, a20, a25, afin = (
                        sub[c10].mean(), sub[c15].mean(), sub[c20].mean(), sub[c25].mean(), sub['kills'].mean()
                    )
                    totals["0-10"] += a10
                    totals["10-15"] += max(a15 - a10, 0)
                    totals["15-20"] += max(a20 - a15, 0)
                    totals["20-25"] += max(a25 - a20, 0)
                    totals["25+"] += max(afin - a25, 0)
                return pd.Series(totals) if found_any else None

            t1_dist = team_kill_distribution_timeline(team1_champs)
            t2_dist = team_kill_distribution_timeline(team2_champs)
        else:
            def team_kill_distribution_by_role(picks_for_team):
                result = {}
                found_any = False
                for r, r_name in roles.items():
                    c = picks_for_team.get(r)
                    if not c:
                        result[r_name] = 0.0
                        continue
                    sub = fp[fp['champion'] == c]
                    result[r_name] = sub['kills'].mean() if not sub.empty else 0.0
                    if not sub.empty:
                        found_any = True
                return pd.Series(result) if found_any else None

            t1_dist = team_kill_distribution_by_role(picks['1'])
            t2_dist = team_kill_distribution_by_role(picks['2'])

            st.caption(
                ("Деталізація по хвилинах (killsAt10/15/20/25) не знайдена у базі — показано розподіл за роллю."
                 if lang == "uk" else
                 "Minute-level columns (killsAt10/15/20/25) weren't found in the dataset — showing distribution by role instead.")
            )

        dist_series = {}
        if t1_dist is not None: dist_series[team1] = t1_dist
        if t2_dist is not None: dist_series[team2] = t2_dist

        if dist_series:
            dist_df = pd.DataFrame(dist_series)
            st.bar_chart(dist_df)

            # Aggregate readout: the bar chart shows shape, not the summed total
            # or which phase carries the most weight — spell both out.
            agg_cols = st.columns(len(dist_series))
            for agg_col, (name, series) in zip(agg_cols, dist_series.items()):
                total = series.sum()
                peak_phase = series.idxmax() if not series.empty and series.sum() > 0 else None
                with agg_col:
                    st.metric(
                        f"{name}: {'прогноз тоталу' if lang == 'uk' else 'projected total'}",
                        f"{total:.1f}",
                    )
                    if peak_phase is not None:
                        st.caption(f"{'Пік' if lang == 'uk' else 'Peak'}: {peak_phase}")
        else:
            st.caption(
                "Оберіть героїв хоча б для однієї команди, щоб побачити розподіл кілів." if lang == "uk"
                else "Pick heroes for at least one team to see the kill distribution."
            )

        # ------------------------------------------------------------------
        # Role-based matchups & counterpicks, with dangerous-pick highlighting
        # ------------------------------------------------------------------
        st.markdown("---")
        st.subheader("⚔️ Матчапи та контрпіки" if lang == "uk" else "⚔️ Matchups & Counterpicks")
        st.caption(
            (f"На основі ліги за патчами: {', '.join(sel_patches) if sel_patches else '—'}" if lang == "uk"
             else f"Based on league data for patches: {', '.join(sel_patches) if sel_patches else '—'}")
        )

        has_matchup_cols = {'gameid', 'side'}.issubset(fp.columns)

        # Thresholds for labeling a counterpick as "dangerous" vs "equal"
        STRONG_MARGIN = 15   # percentage points away from 50% => significantly stronger pick
        EQUAL_MARGIN = 5     # percentage points around 50% => roughly equal matchup
        MIN_H2H_GAMES = 3
        MIN_COUNTER_GAMES = 3

        role_edge_summary = []  # (role, label, favor_team1 [1/-1/0], weight)

        if not has_matchup_cols:
            st.info(
                "Дані для аналізу матчапів (gameid/side) відсутні у завантаженій базі." if lang == "uk"
                else "Matchup data (gameid/side) isn't available in the loaded dataset."
            )
        else:
            @st.cache_data(show_spinner=False, ttl=1800, max_entries=20)
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
                agg = merged.groupby(['champion_a', 'champion_b'], observed=True).agg(
                    win_rate=('result_a', 'mean'), games=('result_a', 'size')
                ).reset_index()
                return agg

            def classify_pick_strength(wr_a_pct, games):
                """Returns a label code for champion_a's win rate vs champion_b."""
                if games < MIN_H2H_GAMES:
                    return 'insufficient'
                diff = wr_a_pct - 50
                if abs(diff) <= EQUAL_MARGIN:
                    return 'equal'
                if diff >= STRONG_MARGIN:
                    return 'a_dangerous'
                if diff <= -STRONG_MARGIN:
                    return 'b_dangerous'
                return 'edge'

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

                header_icons = f"{icon_html(champ1, 18)}{champ1 or '—'} vs {icon_html(champ2, 18)}{champ2 or '—'}"
                with st.expander(f"{r_name}", expanded=True):
                    st.markdown(header_icons, unsafe_allow_html=True)
                    if champ1 and champ2 and not matchup_table.empty:
                        head_to_head = matchup_table[
                            (matchup_table['champion_a'] == champ1) & (matchup_table['champion_b'] == champ2)
                        ]
                        if not head_to_head.empty:
                            wr = head_to_head.iloc[0]['win_rate'] * 100
                            games = int(head_to_head.iloc[0]['games'])
                            label = classify_pick_strength(wr, games)
                            diff = wr - 50
                            favor = 1 if diff > 0 else (-1 if diff < 0 else 0)
                            weight = 2 if label in ('a_dangerous', 'b_dangerous') else (1 if label == 'edge' else 0)
                            if label in ('insufficient', 'equal'):
                                favor = 0
                            role_edge_summary.append((r, label, favor, weight))

                            if label == 'insufficient':
                                st.caption(
                                    f"Недостатньо очних зустрічей ({games})." if lang == "uk"
                                    else f"Not enough direct meetings ({games})."
                                )
                            elif label == 'equal':
                                st.info(
                                    (f"⚖️ **Рівний матчап**: {champ1} {wr:.0f}% — {champ2} {100-wr:.0f}% ({games} ігор)"
                                     if lang == "uk" else
                                     f"⚖️ **Equal matchup**: {champ1} {wr:.0f}% — {champ2} {100-wr:.0f}% ({games} games)")
                                )
                            elif label == 'a_dangerous':
                                st.error(
                                    (f"⚠️ **НЕБЕЗПЕЧНИЙ ПІК**: **{champ1}** домінує над **{champ2}** — {wr:.0f}% WR ({games} ігор)"
                                     if lang == "uk" else
                                     f"⚠️ **DANGEROUS PICK**: **{champ1}** dominates **{champ2}** — {wr:.0f}% WR ({games} games)")
                                )
                            elif label == 'b_dangerous':
                                st.error(
                                    (f"⚠️ **НЕБЕЗПЕЧНИЙ ПІК**: **{champ2}** домінує над **{champ1}** — {100-wr:.0f}% WR ({games} ігор)"
                                     if lang == "uk" else
                                     f"⚠️ **DANGEROUS PICK**: **{champ2}** dominates **{champ1}** — {100-wr:.0f}% WR ({games} games)")
                                )
                            else:  # 'edge' — some advantage, but not dangerous
                                st.write(
                                    (f"**{champ1}** проти **{champ2}**: WR {wr:.0f}% ({games} ігор)" if lang == "uk"
                                     else f"**{champ1}** vs **{champ2}**: {wr:.0f}% win rate ({games} games)")
                                )
                        else:
                            st.caption(
                                "Немає прямих зустрічей у виборці." if lang == "uk"
                                else "No direct meetings in the current sample."
                            )
                    elif champ1 and champ2:
                        st.caption(
                            "Немає прямих зустрічей у виборці." if lang == "uk"
                            else "No direct meetings in the current sample."
                        )

                    mc1, mc2 = st.columns(2)
                    for champ, opp, container in ((champ2, champ1, mc1), (champ1, champ2, mc2)):
                        with container:
                            if not opp:
                                continue
                            st.markdown(
                                (f"Контрпіки проти **{opp}**" if lang == "uk" else f"Counterpicks vs **{opp}**")
                            )
                            counters = matchup_table[
                                (matchup_table['champion_b'] == opp) & (matchup_table['games'] >= MIN_COUNTER_GAMES)
                            ].sort_values('win_rate', ascending=False).head(3) if not matchup_table.empty else matchup_table
                            if counters.empty:
                                st.caption("Недостатньо даних." if lang == "uk" else "Not enough data.")
                            else:
                                for _, row in counters.iterrows():
                                    counter_wr = row['win_rate'] * 100
                                    is_dangerous = counter_wr - 50 >= STRONG_MARGIN
                                    prefix = "⚠️ " if is_dangerous else "• "
                                    st.markdown(
                                        f"{prefix}{icon_html(row['champion_a'], 16)}{row['champion_a']}: {counter_wr:.0f}% ({int(row['games'])} G)",
                                        unsafe_allow_html=True,
                                    )

            if not any_role_shown:
                st.caption(
                    "Оберіть героїв в обох командах, щоб побачити матчапи." if lang == "uk"
                    else "Pick heroes for both teams to see matchups."
                )

        # ------------------------------------------------------------------
        # Residual-based hero synergy for upcoming maps + total prediction
        # ------------------------------------------------------------------
        st.markdown("---")
        st.subheader(
            "🧬 Синергії на наступні карти" if lang == "uk" else "🧬 Synergies for Upcoming Maps"
        )

        pair_stats_fp = pd.DataFrame()  # populated below when matchup cols exist; reused by pick-quality summary

        if not has_matchup_cols:
            st.info(
                "Дані для аналізу синергій (gameid/side) відсутні у завантаженій базі." if lang == "uk"
                else "Synergy data (gameid/side) isn't available in the loaded dataset."
            )
        else:
            MIN_SYN_GAMES = 3
            SYN_TOP_N = 5

            # "Matchup-aware": prefer history of this exact team1-vs-team2 pairing (within the
            # already stage/date/patch-filtered fp); fall back to the broader pool if too thin.
            # [Assuming "matchup" = the specific team1-vs-team2 pairing selected above, since
            #  the dataset has no other explicit head-to-head/series identifier.]
            @st.cache_data(show_spinner=False, ttl=1800, max_entries=20)
            def scope_to_matchup(fp_all, t1, t2):
                pair_games = fp_all[fp_all['teamname'].isin([t1, t2])].groupby('gameid')['teamname'].nunique()
                gids = pair_games[pair_games == 2].index
                return fp_all[fp_all['gameid'].isin(gids)]

            matchup_fp = scope_to_matchup(fp, team1, team2)
            matchup_gids = matchup_fp['gameid'].nunique() if not matchup_fp.empty else 0

            if matchup_gids >= MIN_SYN_GAMES:
                syn_source = matchup_fp
                syn_src_label = "Матчапу" if lang == "uk" else "Matchup"
            else:
                syn_source = fp
                syn_src_label = "Ліги" if lang == "uk" else "League"

            @st.cache_data(show_spinner=False, ttl=1800, max_entries=20)
            def build_teammate_synergy(fp_scope):
                """Residual synergy: observed teammate win rate minus each champ's solo baseline."""
                base = fp_scope[['gameid', 'side', 'champion', 'result']].dropna(subset=['champion'])
                if base.empty:
                    return pd.DataFrame(), pd.Series(dtype=float)
                champ_wr = base.groupby('champion', observed=True)['result'].mean()

                left = base.rename(columns={'champion': 'champion_x', 'result': 'result_x'})
                right = base[['gameid', 'side', 'champion']].rename(columns={'champion': 'champion_y'})
                merged = left.merge(right, on=['gameid', 'side'])
                # 'champion' is a categorical (unordered) column for memory efficiency, and
                # unordered categoricals can't be compared with < directly — compare as plain
                # strings instead to dedupe unordered pairs and drop self-pairs.
                merged = merged[merged['champion_x'].astype(str) < merged['champion_y'].astype(str)]
                if merged.empty:
                    return pd.DataFrame(), champ_wr

                pair_stats = merged.groupby(['champion_x', 'champion_y'], observed=True).agg(
                    win_rate=('result_x', 'mean'), games=('result_x', 'size')
                ).reset_index()
                pair_stats = pair_stats[pair_stats['games'] >= MIN_SYN_GAMES]
                if pair_stats.empty:
                    return pair_stats, champ_wr

                pair_stats['expected'] = pair_stats.apply(
                    lambda row: (champ_wr.get(row['champion_x'], 0.5) + champ_wr.get(row['champion_y'], 0.5)) / 2,
                    axis=1,
                )
                pair_stats['residual'] = pair_stats['win_rate'] - pair_stats['expected']
                return pair_stats.sort_values('residual', ascending=False), champ_wr

            pair_stats, champ_wr = build_teammate_synergy(syn_source)

            # Also build an fp-scoped (pure "historical league data for selected patches")
            # version for the pick-quality summary below, independent of the matchup fallback.
            pair_stats_fp, _ = build_teammate_synergy(fp)

            if pair_stats.empty:
                st.caption(
                    "Недостатньо даних для аналізу синергій у поточній вибірці." if lang == "uk"
                    else "Not enough data to analyze synergies in the current sample."
                )
            else:
                # Restrict suggestions to heroes still pickable (post-Fearless-ban pool)
                pickable = pair_stats[
                    pair_stats['champion_x'].isin(available_champs) & pair_stats['champion_y'].isin(available_champs)
                ].head(SYN_TOP_N)

                if pickable.empty:
                    st.caption(
                        "Немає доступних синергійних пар у межах пулу героїв, що залишився." if lang == "uk"
                        else "No synergy pairs available within the remaining hero pool."
                    )
                else:
                    st.caption(
                        (f"На основі: {syn_src_label} | поріг {MIN_SYN_GAMES}+ ігор" if lang == "uk"
                         else f"Based on: {syn_src_label} | {MIN_SYN_GAMES}+ game threshold")
                    )

                    total_kills_by_game = syn_source.groupby('gameid')['kills'].sum()
                    # need gameid/side back on the pair to look up which games featured that pair
                    base = syn_source[['gameid', 'side', 'champion']].dropna(subset=['champion'])

                    for _, row in pickable.iterrows():
                        cx, cy = row['champion_x'], row['champion_y']
                        wr_pct = row['win_rate'] * 100
                        residual_pts = row['residual'] * 100
                        games = int(row['games'])

                        tag = "🔥" if residual_pts >= 10 else "🧬"
                        st.markdown(
                            (f"{tag} {icon_html(cx, 18)}{icon_html(cy, 18)}**{cx} + {cy}** — WR {wr_pct:.0f}% (residual **{residual_pts:+.1f}pp**, {games} ігор)"
                             if lang == "uk" else
                             f"{tag} {icon_html(cx, 18)}{icon_html(cy, 18)}**{cx} + {cy}** — {wr_pct:.0f}% WR (residual **{residual_pts:+.1f}pp**, {games} games)"),
                            unsafe_allow_html=True,
                        )

                        pair_keys = base[(base['champion'] == cx)][['gameid', 'side']].merge(
                            base[base['champion'] == cy][['gameid', 'side']], on=['gameid', 'side']
                        )
                        pair_gids = pair_keys['gameid'].unique()
                        pair_totals = total_kills_by_game[total_kills_by_game.index.isin(pair_gids)]
                        if not pair_totals.empty:
                            st.caption(
                                (f"　↳ Прогноз тоталу на карті з цією синергією: **{pair_totals.mean():.1f}** кілів ({len(pair_totals)} ігор)"
                                 if lang == "uk" else
                                 f"　↳ Projected map total with this synergy: **{pair_totals.mean():.1f}** kills ({len(pair_totals)} games)")
                            )

        # ------------------------------------------------------------------
        # Pick-quality summary: which draft is stronger, if the data supports it
        # ------------------------------------------------------------------
        st.markdown("---")
        st.subheader("🏆 Оцінка якості драфту" if lang == "uk" else "🏆 Pick Quality Summary")

        team1_champs_named = [c for c in picks['1'].values()]
        team2_champs_named = [c for c in picks['2'].values()]

        if not team1_champs_named and not team2_champs_named:
            st.caption(
                "Оберіть героїв, щоб отримати оцінку драфту." if lang == "uk"
                else "Pick heroes to get a draft quality summary."
            )
        else:
            MIN_HERO_WR_GAMES = 3
            NEGLIGIBLE_PP = 2  # percentage-point threshold below which a signal counts as a tie

            champ_league_stats = fp.groupby('champion', observed=True).agg(wr=('result', 'mean'), games=('result', 'size'))

            def hero_wr_avg(champ_list):
                vals, excluded = [], []
                for c in champ_list:
                    if c in champ_league_stats.index and champ_league_stats.loc[c, 'games'] >= MIN_HERO_WR_GAMES:
                        vals.append(champ_league_stats.loc[c, 'wr'] * 100)
                    else:
                        excluded.append(c)
                avg = sum(vals) / len(vals) if vals else None
                return avg, len(vals), excluded

            t1_avg_wr, t1_n, t1_excl = hero_wr_avg(team1_champs_named)
            t2_avg_wr, t2_n, t2_excl = hero_wr_avg(team2_champs_named)

            def team_synergy_avg(champ_list, pair_table):
                if pair_table is None or pair_table.empty:
                    return None, 0, []
                pairs = list(itertools.combinations(sorted(set(c for c in champ_list if c)), 2))
                found, missing = [], []
                for a, b in pairs:
                    row = pair_table[(pair_table['champion_x'] == a) & (pair_table['champion_y'] == b)]
                    if not row.empty:
                        found.append(row.iloc[0]['residual'] * 100)
                    else:
                        missing.append((a, b))
                avg = sum(found) / len(found) if found else None
                return avg, len(found), missing

            t1_syn_avg, t1_syn_n, t1_syn_missing = team_synergy_avg(team1_champs_named, pair_stats_fp)
            t2_syn_avg, t2_syn_n, t2_syn_missing = team_synergy_avg(team2_champs_named, pair_stats_fp)

            roles_favor_t1 = sum(1 for _, _, favor, _ in role_edge_summary if favor == 1)
            roles_favor_t2 = sum(1 for _, _, favor, _ in role_edge_summary if favor == -1)
            roles_neutral = sum(1 for _, _, favor, _ in role_edge_summary if favor == 0)
            role_score = sum(favor * weight for _, _, favor, weight in role_edge_summary)

            # --- Data-backed facts ---
            st.markdown("**" + ("Дані" if lang == "uk" else "Data") + "**")

            if t1_avg_wr is not None or t2_avg_wr is not None:
                line = (f"- {'WR героїв' if lang=='uk' else 'Hero WR'}: **{team1}** "
                        f"{f'{t1_avg_wr:.0f}%' if t1_avg_wr is not None else '—'} ({t1_n} {'героїв' if lang=='uk' else 'heroes'}) "
                        f"vs **{team2}** {f'{t2_avg_wr:.0f}%' if t2_avg_wr is not None else '—'} ({t2_n} {'героїв' if lang=='uk' else 'heroes'})")
                st.markdown(line)
                if t1_excl or t2_excl:
                    st.caption(
                        (f"Виключено через малу вибірку (< {MIN_HERO_WR_GAMES} ігор): "
                         f"{team1}: {', '.join(t1_excl) or '—'}; {team2}: {', '.join(t2_excl) or '—'}" if lang == "uk"
                         else f"Excluded for small sample (< {MIN_HERO_WR_GAMES} games): "
                              f"{team1}: {', '.join(t1_excl) or '—'}; {team2}: {', '.join(t2_excl) or '—'}")
                    )
            else:
                st.caption(
                    "Недостатньо даних про WR героїв для порівняння." if lang == "uk"
                    else "Not enough hero WR data to compare."
                )

            if has_matchup_cols and role_edge_summary:
                st.markdown(
                    (f"- Матчапи по ролях: **{team1}** сильніший у {roles_favor_t1}, **{team2}** — у {roles_favor_t2}, "
                     f"нейтрально/недостатньо даних — {roles_neutral}" if lang == "uk" else
                     f"- Role matchups: **{team1}** favored in {roles_favor_t1}, **{team2}** favored in {roles_favor_t2}, "
                     f"neutral/insufficient — {roles_neutral}")
                )
            elif has_matchup_cols:
                st.caption(
                    "Немає спільних ролей з піками в обох командах для порівняння матчапів." if lang == "uk"
                    else "No shared roles with picks on both teams to compare matchups."
                )
            else:
                st.caption(
                    "Дані для аналізу матчапів по ролях відсутні." if lang == "uk"
                    else "Role matchup data isn't available."
                )

            if has_matchup_cols and (t1_syn_avg is not None or t2_syn_avg is not None):
                st.markdown(
                    (f"- Синергія пар: **{team1}** {f'{t1_syn_avg:+.1f}pp' if t1_syn_avg is not None else '—'} "
                     f"({t1_syn_n} пар) vs **{team2}** {f'{t2_syn_avg:+.1f}pp' if t2_syn_avg is not None else '—'} ({t2_syn_n} пар)"
                     if lang == "uk" else
                     f"- Pair synergy: **{team1}** {f'{t1_syn_avg:+.1f}pp' if t1_syn_avg is not None else '—'} "
                     f"({t1_syn_n} pairs) vs **{team2}** {f'{t2_syn_avg:+.1f}pp' if t2_syn_avg is not None else '—'} ({t2_syn_n} pairs)")
                )
            elif has_matchup_cols:
                st.caption(
                    "Недостатньо даних для порівняння синергії пар." if lang == "uk"
                    else "Not enough data to compare pair synergy."
                )

            # --- Interpretation ---
            st.markdown("**" + ("Інтерпретація" if lang == "uk" else "Interpretation") + "**")

            signals = []  # list of (name, +1/-1/0 favor_team1)
            if t1_avg_wr is not None and t2_avg_wr is not None:
                d = t1_avg_wr - t2_avg_wr
                signals.append(("hero_wr", 1 if d > NEGLIGIBLE_PP else (-1 if d < -NEGLIGIBLE_PP else 0)))
            if has_matchup_cols and role_edge_summary and role_score != 0:
                signals.append(("role_matchups", 1 if role_score > 0 else -1))
            if has_matchup_cols and t1_syn_avg is not None and t2_syn_avg is not None:
                d = t1_syn_avg - t2_syn_avg
                signals.append(("synergy", 1 if d > NEGLIGIBLE_PP else (-1 if d < -NEGLIGIBLE_PP else 0)))

            usable_signals = [(n, v) for n, v in signals if v != 0]

            if not usable_signals:
                st.caption(
                    "Наявних даних недостатньо, щоб визначити, чий драфт сильніший — не робимо припущень." if lang == "uk"
                    else "The available data isn't sufficient to determine which draft is stronger — not speculating further."
                )
            else:
                directions = set(v for _, v in usable_signals)
                if len(directions) == 1:
                    winner = team1 if usable_signals[0][1] == 1 else team2
                    names = ", ".join(n for n, _ in usable_signals)
                    st.success(
                        (f"На основі наявних сигналів ({names}) **{winner}** мав(ла) сильніший драфт." if lang == "uk"
                         else f"Based on the available signals ({names}), **{winner}** had the stronger draft.")
                    )
                else:
                    for_t1 = [n for n, v in usable_signals if v == 1]
                    for_t2 = [n for n, v in usable_signals if v == -1]
                    st.warning(
                        (f"Сигнали суперечать одне одному: {', '.join(for_t1) or '—'} на користь **{team1}**, "
                         f"{', '.join(for_t2) or '—'} на користь **{team2}**. Однозначного висновку про сильніший драфт зробити не можна."
                         if lang == "uk" else
                         f"Signals conflict: {', '.join(for_t1) or '—'} favor **{team1}**, "
                         f"{', '.join(for_t2) or '—'} favor **{team2}**. No clear conclusion about the stronger draft can be drawn.")
                    )