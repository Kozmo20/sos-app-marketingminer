import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime
from urllib.parse import quote
import json

# --- Konfigurácia stránky ---
st.set_page_config(page_title="Share of Volume | Marketing Miner API", layout="wide")
MM_API_URL = "https://profilers-api.marketingminer.com"

# --- Funkcia na sťahovanie dát z Marketing Miner API (s cachovaním) ---
@st.cache_data(ttl="24h")
def fetch_mm_data(api_key, keyword_list, country_code):
    """
    Sťahuje dáta o hľadanosti z Marketing Miner API pomocou GET požiadavky.
    Používa správny formát s viacerými keyword parametrami.
    """
    # Vytvoríme URL s viacerými keyword parametrami
    base_url = f"{MM_API_URL}/keywords/search-volume-data?api_token={api_key}&lang={country_code}"
    
    # Pridáme každé kľúčové slovo ako samostatný parameter
    keyword_params = []
    for keyword in keyword_list:
        keyword_params.append(f"keyword={quote(keyword.strip())}")
    
    # Finálna URL
    endpoint_url = base_url + "&" + "&".join(keyword_params)
    
    st.info("Finálna URL adresa, ktorá sa posiela na server:")
    st.code(endpoint_url, language="text")
    
    st.info(f"Posielam požiadavku na Marketing Miner API...")
    response = requests.get(endpoint_url)

    if response.status_code != 200:
        raise Exception(f"Chyba pri komunikácii s Marketing Miner API: {response.status_code} - {response.text}")

    st.success("Dáta z Marketing Miner úspešne stiahnuté!")
    return response.json()

def process_mm_response(json_data):
    """
    Spracuje JSON odpoveď z Marketing Miner do čistého Pandas DataFrame.
    Upravená verzia pre správnu štruktúru API odpovede Marketing Miner.
    """
    # Debug: Zobrazíme štruktúru JSON odpovede
    st.subheader("🔍 Debug: Štruktúra JSON odpovede")
    st.json(json_data)
    
    all_data = []
    
    # Skontrolujeme, či je status v poriadku
    if json_data.get('status') != 'success':
        error_message = json_data.get('message', 'Neznáma chyba API')
        raise Exception(f"API vrátilo chybu: {error_message}")
    
    # Získame dáta
    data = json_data.get('data', [])
    
    if not data:
        st.warning("API vrátilo prázdne dáta.")
        return pd.DataFrame()
    
    # Spracujeme dáta - očakávame pole objektov
    if isinstance(data, list):
        st.info(f"Spracovávam {len(data)} kľúčových slov z API")
        
        # Aktuálny rok - predpokladáme, že mesačné dáta sú z posledných 12 mesiacov
        current_year = datetime.now().year
        
        for item in data:
            if not isinstance(item, dict):
                continue
                
            # Získame názov kľúčového slova
            keyword_name = item.get('keyword', 'Unknown')
            
            # Hľadáme mesačné dáta v 'monthly_sv'
            monthly_data = item.get('monthly_sv', {})
            
            if not monthly_data:
                st.warning(f"Nenašli sa mesačné dáta pre kľúčové slovo: {keyword_name}")
                continue
            
            st.info(f"Spracovávam mesačné dáta pre '{keyword_name}': {monthly_data}")
            
            # Spracujeme mesačné dáta - formát {"10": 180, "11": 210, ...}
            if isinstance(monthly_data, dict):
                for month_str, volume in monthly_data.items():
                    try:
                        # Konvertujeme mesiac na číslo
                        month_num = int(month_str)
                        
                        # Vytvoríme dátum - použijeme aktuálny rok pre mesiace <= aktuálny mesiac
                        # a predchádzajúci rok pre mesiace > aktuálny mesiac
                        current_month = datetime.now().month
                        
                        if month_num <= current_month:
                            year = current_year
                        else:
                            year = current_year - 1
                        
                        # Vytvoríme dátum
                        date_obj = datetime(year, month_num, 1)
                        
                        # Pridáme záznam
                        volume_int = int(volume) if isinstance(volume, (int, float, str)) and str(volume).replace('-', '').isdigit() else 0
                        
                        all_data.append({
                            'Keyword': keyword_name,
                            'Date': date_obj,
                            'Search Volume': volume_int
                        })
                        
                    except (ValueError, TypeError) as e:
                        st.warning(f"Problém s mesiacom '{month_str}' pre kľúčové slovo '{keyword_name}': {e}")
                        continue
    
    st.success(f"Úspešne spracované {len(all_data)} mesačných záznamov")
    
    if not all_data:
        st.error("Nepodarilo sa extrahovať žiadne platné dáta z API odpovede")
        return pd.DataFrame()
    
    # Zoradíme dáta podľa dátumu
    df = pd.DataFrame(all_data)
    df = df.sort_values('Date')
    
    # Zobrazíme debug informácie o dátumoch
    st.info("Spracované dátumy:")
    for _, row in df.iterrows():
        st.text(f"  {row['Keyword']}: {row['Date'].strftime('%Y-%m')} -> {row['Search Volume']}")
    
    return df


# --- Hlavná aplikácia (zvyšok kódu je pravdepodobne v poriadku) ---
st.title("🚀 Share of Volume Analýza (cez Marketing Miner API)")
st.markdown("Finálna verzia (v8) - S vylepšeným debugovan ím a flexibilným spracovaním JSON odpovede.")

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

if run_button:
    if not api_key:
        st.stop()
    if not keyword_list:
        st.warning("Prosím, zadajte aspoň jedno kľúčové slovo.")
    else:
        try:
            raw_data = fetch_mm_data(api_key, keyword_list, country_code)
            long_df = process_mm_response(raw_data)

            if long_df.empty:
                st.error("Nepodarilo sa získať žiadne dáta. Skontrolujte štruktúru JSON odpovede vyššie a kontaktujte podporu.")
            else:
                st.success(f"Úspešne spracované dáta pre {len(long_df)} záznamov!")
                
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
