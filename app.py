import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime

# --- Konfigurácia stránky ---
st.set_page_config(page_title="Share of Volume | Marketing Miner API", layout="wide")
# SPRÁVNA ZÁKLADNÁ ADRESA PODĽA NOVÉHO ODKAZU
MM_API_URL = "https://profilers-api.marketingminer.com"

# --- Funkcia na sťahovanie dát z Marketing Miner API (s cachovaním) ---
@st.cache_data(ttl="24h")
def fetch_mm_data(api_key, keywords, country_code):
    """
    Sťahuje dáta o hľadanosti z Marketing Miner API pomocou GET požiadavky.
    """
    # SPRÁVNA CESTA K ENDPOINTU PODĽA NOVÉHO ODKAZU
    endpoint = f"{MM_API_URL}/keywords/search-volume-data"
    
    # Parametre sa posielajú priamo v URL, nie v tele
    params = {
        'token': api_key,
        'database': country_code,
        'keywords': list(keywords)
    }

    st.info(f"Posielam požiadavku na Marketing Miner API pre {len(keywords)} kľúčových slov...")
    # Používame GET požiadavku
    response = requests.get(endpoint, params=params)

    if response.status_code != 200:
        raise Exception(f"Chyba pri komunikácii s Marketing Miner API: {response.status_code} - {response.text}")

    st.success("Dáta z Marketing Miner úspešne stiahnuté!")
    return response.json()

def process_mm_response(json_data):
    """
    Spracuje JSON odpoveď z Marketing Miner do čistého Pandas DataFrame.
    """
    all_data = []
    # Spracovanie odpovede zostáva rovnaké, ak je štruktúra dát podobná
    for keyword, data in json_data.get('result', {}).items():
        if data.get('status') == 'ok' and 'search_volume' in data:
            for date_str, volume in data['search_volume'].items():
                all_data.append({
                    'Keyword': keyword,
                    'Date': datetime.strptime(date_str, '%Y-%m'),
                    'Search Volume': volume
                })
    if not all_data:
        return pd.DataFrame()
    return pd.DataFrame(all_data)

# --- Hlavná aplikácia ---
st.title("🚀 Share of Volume Analýza (cez Marketing Miner API)")
st.markdown("Finálna verzia (v2) napojená na Marketing Miner API pre stabilné dáta.")

# --- Vstupné polia v bočnom paneli ---
with st.sidebar:
    st.header("⚙️ Nastavenia analýzy")

    api_key = st.secrets.get("MARKETING_MINER_API_KEY", "")
    if not api_key:
        st.error("Chýba API kľúč! Nastavte ho prosím v 'Settings -> Secrets'.")

    keywords_input = st.text_area("Zadajte kľúčové slová (oddelené čiarkou)", "Adidas, Nike, Reebok, Puma")
    keyword_list = [kw.strip() for kw in keywords_input.split(',') if kw.strip()]

    country_mapping = {'Slovensko': 'sk', 'Česko': 'cz'}
    selected_country_name = st.selectbox("Zvoľte krajinu", options=list(country_mapping.keys()))
    country_code = country_mapping[selected_country_name]

    st.markdown("### Zvoľte časové obdobie pre zobrazenie")
    start_date = st.date_input("Dátum od", datetime(datetime.now().year - 3, 1, 1))
    end_date = st.date_input("Dátum do", datetime.now())

    run_button = st.button(label="Spustiť analýzu")

# --- Logika po kliknutí na tlačidlo ---
if run_button:
    if not api_key:
        st.stop()
    if not keyword_list:
        st.warning("Prosím, zadajte aspoň jedno kľúčové slovo.")
    else:
        try:
            raw_data = fetch_mm_data(api_key, tuple(keyword_list), country_code)
            long_df = process_mm_response(raw_data)

            if long_df.empty:
                st.error("Nepodarilo sa získať žiadne dáta. Skontrolujte kľúčové slová alebo API odpoveď.")
            else:
                wide_df = long_df.pivot(index='Date', columns='Keyword', values='Search Volume').fillna(0)
                
                start_date_pd = pd.to_datetime(start_date)
                end_date_pd = pd.to_datetime(end_date)
                wide_df_filtered = wide_df[(wide_df.index.to_period('M') >= start_date_pd.to_period('M')) & (wide_df.index.to_period('M') <= end_date_pd.to_period('M'))]

                if wide_df_filtered.empty:
                    st.warning("Vo zvolenom časovom období nie sú žiadne dáta.")
                else:
                    wide_df_filtered['Total Volume'] = wide_df_filtered.sum(axis=1)
                    sov_df = pd.DataFrame(index=wide_df_filtered.index)
                    for kw in keyword_list:
                        if kw in wide_df_filtered.columns:
                            sov_df[kw] = wide_df_filtered.apply(
                                lambda row: (row[kw] / row['Total Volume']) * 100 if row['Total Volume'] > 0 else 0, axis=1)

                    st.header("Share of Volume (Mesačný priemer)")
                    avg_sov = sov_df.mean()
                    fig_pie = px.pie(values=avg_sov.values, names=avg_sov.index, title
