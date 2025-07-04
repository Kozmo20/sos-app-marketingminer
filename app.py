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
def fetch_mm_data_single(api_key, keyword, country_code):
    """
    Sťahuje dáta pre jedno kľúčové slovo z Marketing Miner API.
    """
    base_url = f"{MM_API_URL}/keywords/search-volume-data?api_token={api_key}&lang={country_code}"
    endpoint_url = f"{base_url}&keyword={quote(keyword.strip())}"
    
    response = requests.get(endpoint_url)
    
    if response.status_code != 200:
        raise Exception(f"Chyba pri komunikácii s Marketing Miner API pre '{keyword}': {response.status_code} - {response.text}")
    
    return response.json()

def fetch_mm_data(api_key, keyword_list, country_code):
    """
    Sťahuje dáta pre všetky kľúčové slová - každé volanie osobne.
    Toto rieši problém, keď API berie len posledné kľúčové slovo z viacerých parametrov.
    """
    all_responses = []
    
    # Hlavná informácia - viditeľná
    st.info(f"📡 Načítavam dáta pre {len(keyword_list)} kľúčových slov...")
    
    progress_bar = st.progress(0)
    status_placeholder = st.empty()
    
    for i, keyword in enumerate(keyword_list):
        try:
            status_placeholder.text(f"Spracovávam: '{keyword}' ({i+1}/{len(keyword_list)})")
            
            response = fetch_mm_data_single(api_key, keyword, country_code)
            all_responses.append(response)
            
            progress_bar.progress((i + 1) / len(keyword_list))
            
        except Exception as e:
            st.error(f"❌ Chyba pri spracovaní kľúčového slova '{keyword}': {e}")
            continue
    
    # Vyčistíme progress indikátory
    progress_bar.empty()
    status_placeholder.empty()
    
    # Skombinujeme všetky odpovede do jednej štruktúry
    combined_response = {
        'status': 'success',
        'data': []
    }
    
    for response in all_responses:
        if response.get('status') == 'success' and 'data' in response:
            if isinstance(response['data'], list):
                combined_response['data'].extend(response['data'])
            else:
                combined_response['data'].append(response['data'])
    
    st.success(f"✅ Úspešne načítané dáta pre {len(all_responses)} kľúčových slov!")
    return combined_response

def process_mm_response(json_data):
    """
    Spracuje JSON odpoveď z Marketing Miner do čistého Pandas DataFrame.
    Upravená verzia pre správnu štruktúru API odpovede Marketing Miner.
    """
    all_data = []
    processed_keywords = []  # Sledujeme aké kľúčové slová sme skutočně spracovali
    
    # Skontrolujeme, či je status v poriadku
    if json_data.get('status') != 'success':
        error_message = json_data.get('message', 'Neznáma chyba API')
        raise Exception(f"API vrátilo chybu: {error_message}")
    
    # Získame dáta
    data = json_data.get('data', [])
    
    if not data:
        st.warning("API vrátilo prázdne dáta.")
        return pd.DataFrame(), []
    
    # Debug informácie - skryté pod expander
    with st.expander("🔍 Zobraziť technické detaily spracovania", expanded=False):
        st.subheader("Štruktúra JSON odpovede")
        st.json(json_data)
        st.info(f"Spracovávam {len(data)} kľúčových slov z API")
    
    # Spracujeme dáta - očakávame pole objektov
    if isinstance(data, list):
        # Aktuálny rok - predpokladáme, že mesačné dáta sú z posledných 12 mesiacov
        current_year = datetime.now().year
        
        for item in data:
            if not isinstance(item, dict):
                continue
                
            # Získame názov kľúčového slova
            keyword_name = item.get('keyword', 'Unknown')
            processed_keywords.append(keyword_name)
            
            # Hľadáme mesačné dáta v 'monthly_sv'
            monthly_data = item.get('monthly_sv', {})
            
            if not monthly_data:
                with st.expander("⚠️ Varovania", expanded=False):
                    st.warning(f"Nenašli sa mesačné dáta pre kľúčové slovo: {keyword_name}")
                continue
            
            # Debug informácie - skryté
            with st.expander("🔍 Zobraziť technické detaily spracovania", expanded=False):
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
                        with st.expander("⚠️ Varovania", expanded=False):
                            st.warning(f"Problém s mesiacom '{month_str}' pre kľúčové slovo '{keyword_name}': {e}")
                        continue
    
    # Hlavná informácia - viditeľná
    st.success(f"✅ Spracované dáta pre kľúčové slová: {', '.join(processed_keywords)}")
    
    # Debug informácie - skryté
    with st.expander("🔍 Zobraziť detailné informácie o spracovaných dátumoch", expanded=False):
        st.info(f"Celkový počet záznamov: {len(all_data)}")
        if all_data:
            df_temp = pd.DataFrame(all_data)
            st.info("Prehľad spracovaných dátumov:")
            for keyword in processed_keywords:
                keyword_data = df_temp[df_temp['Keyword'] == keyword]
                if not keyword_data.empty:
                    dates = keyword_data['Date'].dt.strftime('%Y-%m').unique()
                    st.text(f"  {keyword}: {', '.join(sorted(dates))}")
    
    if not all_data:
        st.error("Nepodarilo sa extrahovať žiadne platné dáta z API odpovede")
        return pd.DataFrame(), []
    
    # Zoradíme dáta podľa dátumu
    df = pd.DataFrame(all_data)
    df = df.sort_values('Date')
    
    return df, processed_keywords


# --- Hlavná aplikácia ---
st.title("🚀 Share of Volume Analýza (cez Marketing Miner API)")
st.markdown("**Finálna verzia (v11)** - Čisté UI: všetky technické detaily sú skryté pod expandery.")

with st.sidebar:
    st.header("⚙️ Nastavenia analýzy")

    api_key = st.secrets.get("MARKETING_MINER_API_KEY", "")
    if not api_key:
        st.error("Chýba API kľúč! Nastavte ho prosím v 'Settings -> Secrets'.")

    keywords_input = st.text_area("Zadajte kľúčové slová (oddelené čiarkou)", "fingo, hyponamiru")
    keyword_list = [kw.strip() for kw in keywords_input.split(',') if kw.strip()]
    
    # Debug: Zobrazme spracované kľúčové slová - skryté
    with st.expander("🔍 Zobraziť spracované kľúčové slová", expanded=False):
        st.info(f"Spracované kľúčové slová ({len(keyword_list)}): {', '.join(keyword_list)}")

    country_mapping = {'Slovensko': 'sk', 'Česko': 'cs'}
    selected_country_name = st.selectbox("Zvoľte krajinu", options=list(country_mapping.keys()))
    country_code = country_mapping[selected_country_name]

    st.markdown("### Zvoľte časové obdobie pre zobrazenie")
    st.info("⚠️ Poznámka: Marketing Miner API poskytuje dáta len za posledných 12 mesiacov")
    
    # Nastavíme rozumné defaultné obdobie - posledných 12 mesiacov
    default_start = datetime.now().replace(day=1) - pd.DateOffset(months=11)
    start_date = st.date_input("Dátum od", default_start.date())
    end_date = st.date_input("Dátum do", datetime.now().date())
    
    # Upozornenie ak si používateľ vyberie príliš staré dátumy  
    if start_date < (datetime.now() - pd.DateOffset(months=12)).date():
        st.warning("⚠️ Vybrané obdobie môže obsahovať mesiace, pre ktoré API neposkytuje dáta (staršie ako 12 mesiacov).")

    run_button = st.button(label="Spustiť analýzu")

if run_button:
    if not api_key:
        st.stop()
    if not keyword_list:
        st.warning("Prosím, zadajte aspoň jedno kľúčové slovo.")
    else:
        try:
            raw_data = fetch_mm_data(api_key, keyword_list, country_code)
            long_df, actual_keywords = process_mm_response(raw_data)

            if long_df.empty:
                st.error("Nepodarilo sa získať žiadne dáta. Skontrolujte štruktúru JSON odpovede vyššie a kontaktujte podporu.")
            else:
                st.success(f"Úspešne spracované dáta pre {len(long_df)} záznamov!")
                
                # Vytvoríme pivot tabuľku
                wide_df = long_df.pivot(index='Date', columns='Keyword', values='Search Volume').fillna(0)
                
                # Debug informácie - skryté
                with st.expander("🔍 Zobraziť technické detaily DataFrame", expanded=False):
                    st.info(f"Stĺpce v DataFrame: {list(wide_df.columns)}")
                    st.info(f"Skutočne spracované kľúčové slová z API: {actual_keywords}")
                    st.dataframe(wide_df.head())
                
                # Filtrujeme podľa dátumu
                start_date_pd = pd.to_datetime(start_date)
                end_date_pd = pd.to_datetime(end_date)
                wide_df_filtered = wide_df[(wide_df.index.to_period('M') >= start_date_pd.to_period('M')) & (wide_df.index.to_period('M') <= end_date_pd.to_period('M'))]

                if wide_df_filtered.empty:
                    st.warning("Vo zvolenom časovom období nie sú žiadne dáta.")
                else:
                    # Vypočítame celkový objem
                    wide_df_filtered['Total Volume'] = wide_df_filtered.sum(axis=1)
                    
                    # Vytvoríme Share of Volume DataFrame
                    sov_df = pd.DataFrame(index=wide_df_filtered.index)
                    
                    # Používame skutočné názvy stĺpcov z DataFrame namiesto pôvodného keyword_list
                    available_keywords = [col for col in wide_df_filtered.columns if col != 'Total Volume']
                    
                    # Debug informácie - skryté
                    with st.expander("🔍 Zobraziť výpočet Share of Volume", expanded=False):
                        st.info(f"Počítam SoV pre dostupné kľúčové slová: {available_keywords}")
                        st.dataframe(wide_df_filtered)
                    
                    for kw in available_keywords:
                        sov_df[kw] = wide_df_filtered.apply(
                            lambda row: (row[kw] / row['Total Volume']) * 100 if row['Total Volume'] > 0 else 0, axis=1)

                    # Zobrazenie výsledkov
                    st.header("📊 Share of Volume (Mesačný priemer)")
                    avg_sov = sov_df.mean()
                    
                    # Debug informácie - skryté 
                    with st.expander("🔍 Zobraziť priemerné SoV hodnoty", expanded=False):
                        st.info("Priemerné SoV hodnoty:")
                        for kw, avg_val in avg_sov.items():
                            st.text(f"  {kw}: {avg_val:.2f}%")
                    
                    fig_pie = px.pie(
                        values=avg_sov.values, 
                        names=avg_sov.index, 
                        title=f'Priemerný podiel za obdobie {start_date.strftime("%d.%m.%Y")} - {end_date.strftime("%d.%m.%Y")}', 
                        hole=.4
                    )
                    st.plotly_chart(fig_pie, use_container_width=True)

                    st.header("📈 Vývoj Share of Volume v čase (Mesačne)")
                    fig_bar = px.bar(
                        sov_df, 
                        x=sov_df.index, 
                        y=sov_df.columns, 
                        title='Mesačný vývoj SoV', 
                        labels={'value': 'Share of Volume (%)', 'index': 'Mesiac', 'variable': 'Kľúčové slovo'}
                    )
                    st.plotly_chart(fig_bar, use_container_width=True)

                    # Podkladové dáta - skryté pod expander
                    with st.expander("📋 Zobraziť podkladové dáta (Mesačný objem vyhľadávaní)", expanded=False):
                        st.dataframe(wide_df_filtered.drop(columns='Total Volume'))

        except Exception as e:
            st.error(f"Vyskytla sa chyba: {e}")
            st.error("Skúste skontrolovať debug informácie vyššie pre viac detailov.")
