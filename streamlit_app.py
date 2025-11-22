import streamlit as st
import requests
import pandas as pd
import math
import itertools
from streamlit_autorefresh import st_autorefresh

# ------------------------------
# Utility: Round up to HK$10
# ------------------------------
def round_up_to_10(x):
    try:
        v = float(x)
    except:
        return 10
    return max(10, math.ceil(v / 10.0) * 10)

# ------------------------------
# Fetch QIN (Quinella) odds
# ------------------------------
def fetch_qin_odds(race_no):
    url = f"https://racing.stheadline.com/api/raceOdds/latest?raceNo={race_no}&type=quin&rev=2"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=5)
        r.raise_for_status()
        j = r.json()
    except:
        return {}

    race_odds = j.get("data", {}).get("quin", {}).get("raceOddsList", [])
    odds = {}
    for item in race_odds:
        h1 = item.get("horseNo1")
        h2 = item.get("horseNo2")
        val = item.get("value")
        if h1 is None or h2 is None or val is None:
            continue
        key = f"{int(h1)}-{int(h2)}"
        try:
            odds[key] = float(val)
        except:
            continue
    return odds

# ------------------------------
# Fetch QPL (Place-Quin / place-quin) odds
# ------------------------------
def fetch_qpl_odds(race_no):
    url = f"https://racing.stheadline.com/api/raceOdds/latest?raceNo={race_no}&type=place-quin&rev=2"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=5)
        r.raise_for_status()
        j = r.json()
    except:
        return {}

    data = j.get("data")
    if not isinstance(data, dict):
        return {}

    pq = data.get("place-quin")
    if not pq or not isinstance(pq, dict):
        return {}

    odds_list = pq.get("raceOddsList")
    if not isinstance(odds_list, list):
        return {}

    odds = {}
    for item in odds_list:
        h1 = item.get("horseNo1")
        h2 = item.get("horseNo2")
        val = item.get("value")
        if h1 is None or h2 is None or val is None:
            continue
        key = f"{int(h1)}-{int(h2)}"
        try:
            odds[key] = float(val)
        except:
            continue
    return odds

# ------------------------------
# Banker Dutching
# ------------------------------
def dutch_banker(banker, others, odds_dict, total_stake):
    pairs = {}
    for o in others:
        k1 = f"{banker}-{o}"
        k2 = f"{o}-{banker}"
        if k1 in odds_dict:
            pairs[k1] = odds_dict[k1]
        elif k2 in odds_dict:
            pairs[k2] = odds_dict[k2]

    if not pairs:
        return {}, {}, {}

    inv_sum = sum(1/v for v in pairs.values())
    raw = {p: total_stake / (odds * inv_sum) for p, odds in pairs.items()}
    stakes = {p: round_up_to_10(s) for p, s in raw.items()}
    total_staked = sum(stakes.values())
    returns = {p: stakes[p]*pairs[p] for p in pairs}
    profit = {p: returns[p]-total_staked for p in pairs}
    return pairs, stakes, profit

# ------------------------------
# Non-banker Dutching
# ------------------------------
def dutch_non_banker(selected, odds_dict, total_stake):
    combos = list(itertools.combinations(selected, 2))
    pairs = {}
    for a,b in combos:
        k1 = f"{a}-{b}"
        k2 = f"{b}-{a}"
        if k1 in odds_dict:
            pairs[k1] = odds_dict[k1]
        elif k2 in odds_dict:
            pairs[k2] = odds_dict[k2]
    if not pairs:
        return {}, {}, {}
    inv_sum = sum(1/v for v in pairs.values())
    raw = {p: total_stake / (odds*inv_sum) for p, odds in pairs.items()}
    stakes = {p: round_up_to_10(s) for p, s in raw.items()}
    total_staked = sum(stakes.values())
    returns = {p: stakes[p]*pairs[p] for p in pairs}
    profit = {p: returns[p]-total_staked for p in pairs}
    return pairs, stakes, profit

# ------------------------------
# Streamlit UI
# ------------------------------
st.title("🏇 HKJC QIN + QPL Dutching Calculator (One Screen)")

# Sidebar inputs
race_no = st.sidebar.number_input("Race No.", 1, 12, 1)
total_stake_qin = st.sidebar.number_input("Total Stake (QIN)", 10.0, 999999.0, 100.0, 10.0)
total_stake_qpl = st.sidebar.number_input("Total Stake (QPL)", 10.0, 999999.0, 100.0, 10.0)
market_option = st.sidebar.selectbox("Select Market", ["QIN only", "QPL only", "Both"])
auto_refresh = st.sidebar.checkbox("Auto refresh every 10s", True)
if auto_refresh:
    st_autorefresh(interval=10*1000, key="refresh")

# Fetch odds based on selection
qin_odds = {}
qpl_odds = {}

if market_option in ["QIN only", "Both"]:
    qin_odds = fetch_qin_odds(race_no)
    if not qin_odds:
        st.warning("No QIN odds available for this race.")

if market_option in ["QPL only", "Both"]:
    qpl_odds = fetch_qpl_odds(race_no)
    if not qpl_odds:
        st.warning("QPL (place-quin) odds are not available for this race.")
        if market_option == "QPL only":
            st.stop()

# Horse list
all_horses = sorted({int(h) for d in (qin_odds, qpl_odds) for k in d.keys() for h in k.split("-")})

# Display odds
st.subheader("📈 Odds")
col1, col2 = st.columns(2)
if market_option in ["QIN only", "Both"]:
    with col1:
        st.markdown("### QIN Odds")
        df_qin = pd.DataFrame([{"Pair":k,"Odd":v} for k,v in qin_odds.items()])
        st.dataframe(df_qin)
if market_option in ["QPL only", "Both"]:
    with col2:
        st.markdown("### QPL Odds")
        df_qpl = pd.DataFrame([{"Pair":k,"Odd":v} for k,v in qpl_odds.items()])
        st.dataframe(df_qpl)

# ------------------------------
# QIN Banker
# ------------------------------
if market_option in ["QIN only", "Both"]:
    st.subheader("🎯 QIN Banker Dutching")
    banker_qin = st.selectbox("QIN Banker", all_horses, key="banker_qin")
    others_qin = [h for h in all_horses if h!=banker_qin]
    selected_qin = st.multiselect("QIN副馬", others_qin, key="qin_select")
    if selected_qin:
        pairs, stakes, profit = dutch_banker(banker_qin, selected_qin, qin_odds, total_stake_qin)
        if pairs:
            df = pd.DataFrame({
                "Pair": list(pairs.keys()),
                "Odd": list(pairs.values()),
                "Stake": [stakes[p] for p in pairs],
                "Return": [stakes[p]*pairs[p] for p in pairs],
                "Profit": [profit[p] for p in pairs]
            })
            st.dataframe(df)

# ------------------------------
# QIN Non-banker
# ------------------------------
if market_option in ["QIN only", "Both"]:
    st.subheader("🧮 QIN Non-Banker Dutching")
    selected = st.multiselect("Select horses (all 2-way combinations)", all_horses, key="qin_nb")
    if len(selected)>=2:
        pairs, stakes, profit = dutch_non_banker(selected, qin_odds, total_stake_qin)
        if pairs:
            df = pd.DataFrame({
                "Pair": list(pairs.keys()),
                "Odd": list(pairs.values()),
                "Stake": [stakes[p] for p in pairs],
                "Return": [stakes[p]*pairs[p] for p in pairs],
                "Profit": [profit[p] for p in pairs]
            })
            st.dataframe(df)

# ------------------------------
# QPL Banker
# ------------------------------
if market_option in ["QPL only", "Both"]:
    st.subheader("🎯 QPL Banker Dutching")
    banker_qpl = st.selectbox("QPL Banker", all_horses, key="banker_qpl")
    others_qpl = [h for h in all_horses if h!=banker_qpl]
    selected_qpl = st.multiselect("QPL副馬", others_qpl, key="qpl_select")
    if selected_qpl:
        pairs, stakes, profit = dutch_banker(banker_qpl, selected_qpl, qpl_odds, total_stake_qpl)
        if pairs:
            df = pd.DataFrame({
                "Pair": list(pairs.keys()),
                "Odd": list(pairs.values()),
                "Stake": [stakes[p] for p in pairs],
                "Return": [stakes[p]*pairs[p] for p in pairs],
                "Profit": [profit[p] for p in pairs]
            })
            st.dataframe(df)

# ------------------------------
# QPL Non-banker
# ------------------------------
if market_option in ["QPL only", "Both"]:
    st.subheader("🧮 QPL Non-Banker Dutching")
    selected = st.multiselect("Select horses (all 2-way combinations)", all_horses, key="qpl_nb")
    if len(selected)>=2:
        pairs, stakes, profit = dutch_non_banker(selected, qpl_odds, total_stake_qpl)
        if pairs:
            df = pd.DataFrame({
                "Pair": list(pairs.keys()),
                "Odd": list(pairs.values()),
                "Stake": [stakes[p] for p in pairs],
                "Return": [stakes[p]*pairs[p] for p in pairs],
                "Profit": [profit[p] for p in pairs]
            })
            st.dataframe(df)
