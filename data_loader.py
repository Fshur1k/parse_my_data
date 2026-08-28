import streamlit as st
import pandas as pd

# ==========================================================================
# Shared data loader for app.py, calculator_counter.py, and team_profile.py.
# [Assuming this file lives alongside app.py at the repo root, so `import
#  data_loader` resolves the same way from a pages/ subfolder — Streamlit adds
#  the main script's directory to sys.path for the whole multipage app.]
#
# Why this exists: previously every page read the parsed dataframe out of
# st.session_state, which held the return value of an st.cache_data-wrapped
# loader. st.cache_data returns a *copy* of the cached object on every call,
# so every browser session that opened the app ended up with its own full
# copy of the (large, wide) Oracle's Elixir export sitting in memory for the
# life of that session. On Streamlit Community Cloud, where every session
# shares one process, that duplication is very likely what pushed the app
# over its memory limit. st.cache_resource instead hands every caller the
# *same* object, so the whole app shares one copy no matter how many people
# are using it at once.
# ==========================================================================

DEFAULT_FILE_PATH = "2026_LoL_esports_match_data_from_OraclesElixir.csv.zip"

# Only the columns actually referenced anywhere in app.py / calculator_counter.py /
# team_profile.py. Oracle's Elixir exports 100+ columns; loading only what's used
# is the single biggest memory saving available at load time. If a needed column
# is missing from a given export, downstream pages already guard for that
# (has_stage_col / has_matchup_cols / has_timeline_cols checks) and degrade
# gracefully instead of crashing.
NEEDED_COLUMNS = [
    'date', 'gameid', 'game', 'position', 'side', 'teamname', 'playername',
    'champion', 'league', 'patch', 'playoffs', 'result', 'kills', 'deaths',
    'gamelength', 'towers', 'opp_towers', 'dragons', 'opp_dragons',
    'barons', 'opp_barons', 'inhibitors', 'opp_inhibitors',
    'firstblood', 'firsttower', 'firstdragon', 'firstbaron', 'firstinhibitor',
    'killsat10', 'opp_killsat10', 'killsat15', 'opp_killsat15', 'killsat20', 'killsat25',
]

# Repeated, low-cardinality string columns — 'category' dtype is usually the
# single largest dtype saving available on a match-log CSV like this one.
CATEGORY_COLUMNS = ['position', 'side', 'teamname', 'playername', 'champion', 'league', 'patch']


def _downcast(d: pd.DataFrame) -> pd.DataFrame:
    for col in CATEGORY_COLUMNS:
        if col in d.columns:
            d[col] = d[col].astype('category')
    for col in d.select_dtypes(include='integer').columns:
        d[col] = pd.to_numeric(d[col], downcast='integer')
    # [Downcasting float64 -> float32 trades a small amount of precision for
    #  roughly half the memory on numeric columns; fine for aggregated stats
    #  like this app computes (means, sums, win rates), not exact science.]
    for col in d.select_dtypes(include='float').columns:
        d[col] = pd.to_numeric(d[col], downcast='float')
    return d


def _probe_header_columns(source):
    try:
        cols = pd.read_csv(source, nrows=0).columns.tolist()
        if hasattr(source, 'seek'):
            source.seek(0)
        return cols
    except Exception:
        return None


def _read_any(source, usecols=None) -> pd.DataFrame:
    filename = source.name if hasattr(source, 'name') else str(source)
    kwargs = {'low_memory': False}
    if usecols is not None:
        kwargs['usecols'] = usecols
    if filename.endswith('.zip'):
        kwargs['compression'] = 'zip'
    return pd.read_csv(source, **kwargs)


def _prepare(d: pd.DataFrame) -> pd.DataFrame:
    d['parsed_datetime'] = pd.to_datetime(d['date'], errors='coerce')
    d['date_only'] = d['parsed_datetime'].dt.date
    return _downcast(d)


@st.cache_resource(show_spinner="Завантаження бази даних...")
def load_default_dataset(path: str = DEFAULT_FILE_PATH):
    """Shared, single-copy load of the default on-disk dataset.

    Deliberately st.cache_resource (not cache_data): the whole app shares ONE
    dataframe instance instead of handing every session its own copy.
    """
    header_cols = _probe_header_columns(path)
    usecols = [c for c in NEEDED_COLUMNS if header_cols is None or c in header_cols] or None
    d = _read_any(path, usecols=usecols)
    return _prepare(d)


@st.cache_data(show_spinner="Завантаження файлу...")
def load_uploaded_dataset(uploaded_file):
    """Per-session load for a user-supplied file override.

    Intentionally st.cache_data here: an upload is specific to the session
    that provided it, so it's correct — not just acceptable — for it to live
    in that one session's memory rather than being shared app-wide.
    """
    header_cols = _probe_header_columns(uploaded_file)
    usecols = [c for c in NEEDED_COLUMNS if header_cols is None or c in header_cols] or None
    d = _read_any(uploaded_file, usecols=usecols)
    return _prepare(d)


def get_active_dataframe(default_path: str = DEFAULT_FILE_PATH):
    """What every page should call instead of reading st.session_state['df'].

    Returns this session's uploaded override if one was set, otherwise the
    single shared default dataset.
    """
    custom = st.session_state.get('custom_df')
    if custom is not None:
        return custom
    try:
        return load_default_dataset(default_path)
    except Exception as e:
        st.session_state['load_error'] = str(e)
        return None
