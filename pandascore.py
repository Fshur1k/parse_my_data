if df is not None:
    # --- Створюємо дві вкладки ---
    tab1, tab2 = st.tabs(["📊 Експорт матчів", "🧮 Калькулятор піків"])
    
    # ==========================================
    # Вкладка 1: Твій старий експортер
    # ==========================================
    with tab1:
        # 1. Список усіх турнірів із CSV
        all_tournaments = sorted(df['league'].dropna().unique().tolist())
        selected_tournaments = st.selectbox(
            "🏆 Оберіть турнір(и):", 
            options=all_tournaments, 
            key="tab1_tournaments"
        )
        
        # ... ТУТ МАЄ БУТИ ВВЕСЬ ТВІЙ СТАРИЙ КОД ФІЛЬТРАЦІЇ ...
        # (від вибору дат до кнопки "Відправити в Google Sheets")
        # Просто переконайся, що він має відступ всередині блоку `with tab1:`
        # 2. Календар за датами
        min_date = df['date_only'].min()
        max_date = df['date_only'].max()
        selected_date_range = st.sidebar.date_input(
            "📅 Діапазон дат:",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date
        )
        
        if isinstance(selected_date_range, tuple) and len(selected_date_range) == 2:
            start_date, end_date = selected_date_range
        else:
            start_date = end_date = selected_date_range[0] if isinstance(selected_date_range, (list, tuple)) else selected_date_range
            
        # Фільтрація
        filtered_df = df[
            (df['league'].isin(selected_tournaments)) &
            (df['date_only'] >= start_date) &
            (df['date_only'] <= end_date)
        ]
        
        if filtered_df.empty:
                st.warning("⚠️ За обраними фільтрами (турніри / дати) матчів не знайдено.")
        else:
            # === БЛОК ГРУПУВАННЯ МАТЧІВ (СЕРІЙ) ===
            series_info = {}
            
            for game_id, g in filtered_df.groupby('gameid'):
                # Беремо назви обох команд і сортуємо їх за алфавітом
                teams = sorted(g['teamname'].dropna().unique().tolist())
                team_display = f"{teams[0]} vs {teams[1]}" if len(teams) == 2 else " vs ".join(teams)
                
                league_name = g['league'].iloc[0]
                game_date = g['date_only'].iloc[0]
                
                # Створюємо унікальний ключ для серії (матчу)
                series_key = f"{game_date}_{league_name}_{team_display}"
                
                if series_key not in series_info:
                    series_info[series_key] = {
                        'display_name': f"{game_date} | [{league_name}] {team_display}",
                        'game_ids': []
                    }
                    
                # Додаємо ID карти до загального списку карт цієї серії
                series_info[series_key]['game_ids'].append(game_id)
                
            # Додаємо кількість зіграних карт до назви в меню
            display_options = {}
            for s_key, info in series_info.items():
                map_count = len(info['game_ids'])
                display_options[s_key] = f"{info['display_name']} ({map_count} карт)"
    
            # 3. Множинний вибір матчів
            st.subheader("⚔️ Вибір матчів")
            selected_series_keys = st.multiselect(
                "Оберіть один або декілька матчів (усі карти підтягнуться автоматично):",
                options=list(display_options.keys()),
                format_func=lambda x: display_options[x],
                default=list(display_options.keys())[:3] if len(display_options) >= 3 else list(display_options.keys())
            )
            
            if selected_series_keys:
                # Збираємо всі gameid (карти), що входять у вибрані матчі
                selected_match_ids = []
                for s_key in selected_series_keys:
                    selected_match_ids.extend(series_info[s_key]['game_ids'])
                    
                # Фільтруємо датафрейм за всіма знайденими картами
                selected_games_df = filtered_df[filtered_df['gameid'].isin(selected_match_ids)]
                
                # Парсимо дані
                parsed_maps_rows = parse_selected_games(selected_games_df)
                parsed_df = pd.DataFrame(parsed_maps_rows)
                
                st.subheader(f"📊 Згенерована таблиця карт ({len(parsed_df)} карт(и))")
                st.dataframe(parsed_df)
                
                st.markdown("---")
                st.subheader("📤 Експорт у Google Sheets")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.session_state['sheet_url'] = st.text_input("URL Google Таблиці:", value=st.session_state['sheet_url'])
                with col2:
                    st.session_state['sheet_name'] = st.text_input("Назва аркуша:", value=st.session_state['sheet_name'])
                    
                if st.button("🚀 Відправити в Google Sheets"):
                    with st.spinner("Запис даних у Google Таблицю..."):
                        success, message = append_to_sheet(
                            st.session_state['sheet_url'], 
                            st.session_state['sheet_name'], 
                            parsed_maps_rows
                        )
                        if success:
                            st.success(message)
                        else:
                            st.error(message)


    # ==========================================
    # Вкладка 2: Новий Калькулятор Піків
    # ==========================================
    with tab2:
        st.header("🧮 Аналіз піків та гравців")
        
        # Витягуємо дані лише по гравцях (виключаємо командну статистику)
        players_df = df[df['position'] != 'team'].copy()
        
        # Форматуємо патчі, щоб графік малювався коректно (замінюємо коми на крапки)
        players_df['patch'] = players_df['patch'].astype(str).str.replace(',', '.')
        
        teams_list = sorted(players_df['teamname'].dropna().unique().tolist())
        champs_list = sorted(players_df['champion'].dropna().unique().tolist())
        
        if not teams_list:
            st.warning("Немає даних по командах")
        else:
            # Створюємо 3 колонки: Команда 1, Команда 2 і Дашборд
            col1, col2, col3 = st.columns([1, 1, 1.5])
            
            # --- ДОПОМІЖНІ ФУНКЦІЇ ДЛЯ КАЛЬКУЛЯТОРА ---
            def get_roster(team_name):
                """Знаходить найчастішого гравця на кожній позиції для обраної команди"""
                roster = {}
                team_data = players_df[players_df['teamname'] == team_name]
                for role in ['top', 'jng', 'mid', 'bot', 'sup']:
                    r_data = team_data[team_data['position'] == role]
                    if not r_data.empty:
                        # Беремо гравця, який зіграв найбільше ігор на цій ролі
                        roster[role] = r_data['playername'].value_counts().index[0]
                    else:
                        roster[role] = "Невідомо"
                return roster

            def get_stats(player_name, champ_name):
                """Рахує середнє і медіану кілів, з фолбеком на лігу"""
                if not champ_name or champ_name == "None":
                    return 0, 0, ""
                
                # Шукаємо матчі конкретного гравця на конкретному герої
                p_data = players_df[(players_df['playername'] == player_name) & (players_df['champion'] == champ_name)]
                
                if not p_data.empty:
                    return p_data['kills'].mean(), p_data['kills'].median(), "Статистика гравця"
                
                # Якщо гравець не грав на герої — беремо стату по всіх гравцях на цьому герої
                c_data = players_df[players_df['champion'] == champ_name]
                if not c_data.empty:
                    return c_data['kills'].mean(), c_data['kills'].median(), "В середньому по лізі"
                
                return 0, 0, "Немає даних"

            roles_display = {'top': 'Top', 'jng': 'Jungle', 'mid': 'Mid', 'bot': 'ADC', 'sup': 'Support'}
            
            # Список для збору героїв, обраних на драфті (щоб малювати їх на графіку)
            selected_draft_champs = []

            # --- КОЛОНКА 1 (СИНЯ КОМАНДА) ---
            with col1:
                st.subheader("🔵 Синя команда")
                team1 = st.selectbox("Оберіть команду 1", options=teams_list, index=0, key="t1")
                roster1 = get_roster(team1)
                
                for role, role_name in roles_display.items():
                    st.markdown(f"**{role_name}** | {roster1[role]}")
                    champ = st.selectbox(f"Пік ({role_name})", ["None"] + champs_list, key=f"t1_champ_{role}")
                    
                    if champ != "None":
                        selected_draft_champs.append(champ)
                        mean_k, med_k, source = get_stats(roster1[role], champ)
                        # Виводимо результати
                        if source == "Статистика гравця":
                            st.success(f"Кіли: Середнє **{mean_k:.1f}** | Медіана **{med_k:.1f}**")
                        else:
                            st.warning(f"Кіли: Середнє **{mean_k:.1f}** | Медіана **{med_k:.1f}** ({source})")
                    st.write("---")

            # --- КОЛОНКА 2 (ЧЕРВОНА КОМАНДА) ---
            with col2:
                st.subheader("🔴 Червона команда")
                # Беремо іншу команду за замовчуванням, якщо команд достатньо
                t2_idx = 1 if len(teams_list) > 1 else 0
                team2 = st.selectbox("Оберіть команду 2", options=teams_list, index=t2_idx, key="t2")
                roster2 = get_roster(team2)
                
                for role, role_name in roles_display.items():
                    st.markdown(f"**{role_name}** | {roster2[role]}")
                    champ = st.selectbox(f"Пік ({role_name})", ["None"] + champs_list, key=f"t2_champ_{role}")
                    
                    if champ != "None":
                        selected_draft_champs.append(champ)
                        mean_k, med_k, source = get_stats(roster2[role], champ)
                        
                        if source == "Статистика гравця":
                            st.success(f"Кіли: Середнє **{mean_k:.1f}** | Медіана **{med_k:.1f}**")
                        else:
                            st.warning(f"Кіли: Середнє **{mean_k:.1f}** | Медіана **{med_k:.1f}** ({source})")
                    st.write("---")

            # --- КОЛОНКА 3 (ДАШБОРД ПАТЧІВ) ---
            with col3:
                st.subheader("📈 Тренд кілів по патчах")
                st.write("Оберіть героя на драфті зліва, щоб побачити графік.")
                
                # Фільтруємо унікальних героїв, яких щойно обрали на драфті
                unique_champs = list(set(selected_draft_champs))
                
                if unique_champs:
                    dash_champ = st.selectbox("Аналіз обраного героя:", unique_champs)
                    
                    # Готуємо дані для графіка (середні кіли героя по всіх іграх ліги)
                    champ_trend_data = players_df[players_df['champion'] == dash_champ]
                    
                    if not champ_trend_data.empty:
                        # Групуємо за патчем і рахуємо середнє
                        trend_grouped = champ_trend_data.groupby('patch')['kills'].mean().reset_index()
                        
                        # Сортуємо патчі як числа (наскільки це можливо)
                        # Якщо формат складний, можна просто покластись на алфавітне сортування
                        trend_grouped = trend_grouped.sort_values(by='patch')
                        trend_grouped.set_index('patch', inplace=True)
                        
                        st.line_chart(trend_grouped)
                        st.caption(f"Середня кількість кілів **{dash_champ}** (за всіма матчами в базі)")
                    else:
                        st.info("Недостатньо даних для малювання графіка.")
                else:
                    st.info("Поки що жодного героя не обрано.")