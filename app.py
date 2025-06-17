import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime
from urllib.parse import quote

# --- Konfigurácia stránky ---
st.set_page_config(page_title="Share of Volume | Marketing Miner API", layout="wide")
MM_API_URL = "https://profilers-api.marketingminer.com"

# --- Funkcia na sťahovanie dát z Marketing Miner API (s cachovaním) ---
@st.cache_data(ttl="24h")
def fetch_mm_data(api_key, keywords_string, country_code):
    """
    Sťahuje dáta o hľadanosti z Marketing Miner API pomocou GET požiadavky s manuálne vytvorenou URL.
    """
    keywords_encoded = quote(keywords_string)
    endpoint_url = f"{MM_API_URL}/keywords/search-volume-data?api_token={api_key}&lang={country_code}&keyword={keywords_encoded}"
    
    st.info("Finálna URL adresa, ktorá sa posiela na server:")
    st.code(endpoint_url, language="text")
    
    st.info(f"Posielam požiadavku na Marketing Miner API...")
    response = requests.get(endpoint_url)

    if response.status_code != 200:
        raise Exception(f"Chyba pri komunikácii s Marketing Miner API: {response.status_code} - {response.text}")

    st.success("Dáta z Marketing Miner úspešne stiahnuté!")
    return response.json()

# FINÁLNE OPRAVENÁ FUNKCIA NA SPRACOVANIE ODPOVEDE
def process_mm_response(json_data):
    """
    Spracuje JSON odpoveď z Marketing Miner do čistého Pandas DataFrame.
    """
    all_data = []
    # Skontrolujeme, či je status v poriadku
    if json_data.get('status') == 'success':
        # Dáta sú v slovníku (dictionary), kde kľúč je hľadané slovo. Iterujeme cez kľúče a hodnoty.
        for keyword_name, keyword_info in json_data.get('data', {}).items():
            # Keyword_info je ďalší slovník, ktorý obsahuje dáta pre jedno slovo
            if isinstance(keyword_info, dict) and 'search_volume' in keyword_info:
                for date_str, volume in keyword_info['search_volume'].items():
                    all_data.append({
                        'Keyword': keyword_name,
                        'Date': datetime.strptime(date_str, '%Y-%m'),
                        'Search Volume': volume
                    })
    
    if not all_data:
        # Ak sme nenašli dáta, skontrolujeme, či API nevrátilo nejakú chybu vnútri odpovede
        if 'result' in json_data and 'errors' in json_data['result'] and json_data['result']['errors']:
             raise Exception(f"API vrátilo chybu v dátach: {json_data['result']['errors']}")
        return pd.DataFrame()
        
    return pd.DataFrame(all_data)


# --- Hlavná aplikácia ---
st.title("🚀 Share of Volume Analýza (cez Marketing Miner API)")
st.markdown("Finálna verzia (v7) - Postavená podľa presnej dokumentácie.")

# --- Vstupné polia v bočnom paneli ---
with st.sidebar:
    st.header("⚙️ Nastavenia analýzy")

    api_key = st.secrets.get("MARKETING_MINER_API_KEY", "")
    if not api_key:
        st.error("Chýba API kľúč! Nastavte ho prosím v 'Settings -> Secrets'.")

    keywords_input = st.text_area("Zadajte kľúčové slová (oddelené čiarkou)", "fingo, hyponamiru")
    keyword_list = [kw.strip() for kw in keywords_input.split(',') if kw.strip()]

    country_mapping = {'Slovensko': 'sk', 'Česko': 'cs'}
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
            keywords_string = ','.join(keyword_list)
            
            # Použijeme cachovanie, takže opätovné spustenie nebude míňať kredity
            raw_data = fetch_mm_data(api_key, keywords_string, country_code)
            long_df = process_mm_response(raw_data)

            if long_df.empty:
                st.error("Nepodarilo sa získať žiadne dáta. Skontrolujte kľúčové slová alebo či API nevrátilo chybu v odpovedi.")
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
                    fig_pie = px.pie(values=avg_sov.values, names=avg_sov.index, title=f'Priemerný podiel za obdobie {start_date.strftime("%d.%m.%Y")} - {end_date.strftime("%d.%m.%Y")}', hole=.4)
                    st.plotly_chart(fig_pie, use_container_width=True)

                    st.header("Vývoj Share of Volume v čase (Mesačne)")
                    fig_bar = px.bar(sov_df, x=sov_df.index, y=sov_df.columns, title='Mesačný vývoj SoV', labels={'value': 'Share of Volume (%)', 'index': 'Mesiac', 'variable': 'Kľúčové slovo'})
                    st.plotly_chart(fig_bar, use_container_width=True)

                    st.header("Podkladové dáta (Mesačný objem vyhľadávaní)")
                    st.dataframe(wide_df_filtered.drop(columns='Total Volume'))

        except Exception as e:
            st.error(f"Vyskytla sa chyba: {e}")
