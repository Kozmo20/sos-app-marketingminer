import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
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
    
    # Progress indikátory
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
    
    return combined_response

def process_mm_response(json_data):
    """
    Spracuje JSON odpoveď z Marketing Miner do čistého Pandas DataFrame.
    Upravená verzia pre správnu štruktúru API odpovede Marketing Miner.
    """
    all_data = []
    processed_keywords = []
    debug_info = []  # Zbierame debug informácie
    
    # Skontrolujeme, či je status v poriadku
    if json_data.get('status') != 'success':
        error_message = json_data.get('message', 'Neznáma chyba API')
        raise Exception(f"API vrátilo chybu: {error_message}")
    
    # Získame dáta
    data = json_data.get('data', [])
    
    if not data:
        st.warning("API vrátilo prázdne dáta.")
        return pd.DataFrame(), [], debug_info, json_data
    
    debug_info.append(f"Spracovávam {len(data)} kľúčových slov z API")
    
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
                debug_info.append(f"Nenašli sa mesačné dáta pre kľúčové slovo: {keyword_name}")
                continue
            
            debug_info.append(f"Spracovávam mesačné dáta pre '{keyword_name}': {monthly_data}")
            
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
                        debug_info.append(f"Problém s mesiacom '{month_str}' pre kľúčové slovo '{keyword_name}': {e}")
                        continue
    
    # Len jedna správa o úspešnom spracovaní
    if processed_keywords:
        st.success(f"✅ Úspešne spracované dáta pre: {', '.join(processed_keywords)}")
    
    debug_info.append(f"Celkový počet záznamov: {len(all_data)}")
    if all_data:
        df_temp = pd.DataFrame(all_data)
        for keyword in processed_keywords:
            keyword_data = df_temp[df_temp['Keyword'] == keyword]
            if not keyword_data.empty:
                dates = keyword_data['Date'].dt.strftime('%Y-%m').unique()
                debug_info.append(f"  {keyword}: {', '.join(sorted(dates))}")
    
    if not all_data:
        st.error("Nepodarilo sa extrahovať žiadne platné dáta z API odpovede")
        return pd.DataFrame(), [], debug_info, json_data
    
    # Zoradíme dáta podľa dátumu
    df = pd.DataFrame(all_data)
    df = df.sort_values('Date')
    
    return df, processed_keywords, debug_info, json_data


# --- Hlavná aplikácia ---
st.title("🚀 Invelity Share of Volume Analýza")

# Informačný panel - zbalený v expanderi
with st.expander("ℹ️ Informácie o aplikácii", expanded=False):
    st.markdown("**Dátový zdroj:** Marketing Miner API")
    st.markdown("**Verzia:** v13 - Vyčistené notifikácie a technické detaily")
    st.markdown("**Vývojár:** Invelity")

with st.sidebar:
    st.header("⚙️ Nastavenia analýzy")

    # API kľúč kontrola
    api_key = st.secrets.get("MARKETING_MINER_API_KEY", "")
    if not api_key:
        st.error("Chýba API kľúč! Nastavte ho prosím v 'Settings -> Secrets'.")

    # Základné nastavenia - hlavný expander
    with st.expander("🎯 Základné nastavenia", expanded=True):
        keywords_input = st.text_area("Zadajte kľúčové slová (oddelené čiarkou)", "fingo, hyponamiru")
        keyword_list = [kw.strip() for kw in keywords_input.split(',') if kw.strip()]
        
        country_mapping = {'Slovensko': 'sk', 'Česko': 'cs'}
        selected_country_name = st.selectbox("Zvoľte krajinu", options=list(country_mapping.keys()))
        country_code = country_mapping[selected_country_name]

    # Časové obdobie - druhý expander
    with st.expander("📅 Časové obdobie", expanded=True):
        st.info("⚠️ Marketing Miner API poskytuje dáta len za posledných 12 mesiacov")
        
        # Nastavíme rozumné defaultné obdobie - posledných 12 mesiacov
        default_start = datetime.now().replace(day=1) - pd.DateOffset(months=11)
        start_date = st.date_input("Dátum od", default_start.date())
        end_date = st.date_input("Dátum do", datetime.now().date())
        
        # Upozornenie ak si používateľ vyberie príliš staré dátumy  
        if start_date < (datetime.now() - pd.DateOffset(months=12)).date():
            st.warning("⚠️ Vybrané obdobie môže obsahovať mesiace, pre ktoré API neposkytuje dáta (staršie ako 12 mesiacov).")

    # Debug informácie - tretí expander (zbalený)
    with st.expander("🔍 Debug informácie", expanded=False):
        st.info(f"Spracované kľúčové slová ({len(keyword_list)}): {', '.join(keyword_list)}")
        st.info(f"Krajina: {selected_country_name} ({country_code})")
        st.info(f"Obdobie: {start_date} - {end_date}")

    # Tlačidlo na spustenie
    st.markdown("---")
    run_button = st.button(label="🚀 Spustiť analýzu", type="primary")

if run_button:
    if not api_key:
        st.stop()
    if not keyword_list:
        st.warning("Prosím, zadajte aspoň jedno kľúčové slovo.")
    else:
        try:
            raw_data = fetch_mm_data(api_key, keyword_list, country_code)
            long_df, actual_keywords, debug_info, json_data = process_mm_response(raw_data)

            if long_df.empty:
                st.error("Nepodarilo sa získať žiadne dáta. Skontrolujte technické detaily nižšie.")
            else:
                # Vytvoríme pivot tabuľku
                wide_df = long_df.pivot(index='Date', columns='Keyword', values='Search Volume').fillna(0)
                
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
                    
                    for kw in available_keywords:
                        sov_df[kw] = wide_df_filtered.apply(
                            lambda row: (row[kw] / row['Total Volume']) * 100 if row['Total Volume'] > 0 else 0, axis=1)

                    # Zobrazenie výsledkov - vylepšené rozloženie
                    st.header("📊 Share of Volume - Prehľad")
                    
                    # Vytvoríme dva stĺpce pre koláčový graf a stĺpcový graf
                    col1, col2 = st.columns([1, 2])
                    
                    with col1:
                        st.subheader("Mesačný priemer")
                        avg_sov = sov_df.mean()
                        
                        fig_pie = px.pie(
                            values=avg_sov.values, 
                            names=avg_sov.index, 
                            title=f'Priemerný podiel za obdobie<br>{start_date.strftime("%d.%m.%Y")} - {end_date.strftime("%d.%m.%Y")}', 
                            hole=.4
                        )
                        fig_pie.update_layout(height=500)
                        st.plotly_chart(fig_pie, use_container_width=True)
                        
                        # Pridáme priemerné SoV hodnoty ku koláčovému grafu
                        st.subheader("Priemerné SoV hodnoty")
                        for kw, avg_val in avg_sov.items():
                            st.metric(label=kw, value=f"{avg_val:.2f}%")
                    
                    with col2:
                        st.subheader("Mesačný vývoj (Stĺpcový graf)")
                        fig_bar = px.bar(
                            sov_df, 
                            x=sov_df.index, 
                            y=sov_df.columns, 
                            title='Mesačný vývoj Share of Volume (%)', 
                            labels={'value': 'Share of Volume (%)', 'index': 'Mesiac', 'variable': 'Kľúčové slovo'},
                            height=500
                        )
                        fig_bar.update_layout(
                            xaxis_title="Mesiac",
                            yaxis_title="Share of Volume (%)",
                            legend_title="Kľúčové slovo"
                        )
                        st.plotly_chart(fig_bar, use_container_width=True)

                    # Pridáme čiarový graf
                    st.header("📈 Vývoj Share of Volume v čase (Čiarový graf)")
                    fig_line = px.line(
                        sov_df, 
                        x=sov_df.index, 
                        y=sov_df.columns,
                        title='Trendy Share of Volume pre jednotlivých konkurentov',
                        labels={'value': 'Share of Volume (%)', 'index': 'Mesiac', 'variable': 'Kľúčové slovo'},
                        height=400,
                        markers=True
                    )
                    fig_line.update_layout(
                        xaxis_title="Mesiac",
                        yaxis_title="Share of Volume (%)",
                        legend_title="Kľúčové slovo",
                        hovermode='x unified'
                    )
                    st.plotly_chart(fig_line, use_container_width=True)

                    # Pridáme aj graf absolútnych hodnôt
                    st.header("📊 Absolútne hodnoty vyhľadávaní")
                    volume_df = wide_df_filtered.drop(columns='Total Volume')
                    
                    fig_volume = px.line(
                        volume_df, 
                        x=volume_df.index, 
                        y=volume_df.columns,
                        title='Mesačný objem vyhľadávaní (absolútne hodnoty)',
                        labels={'value': 'Počet vyhľadávaní', 'index': 'Mesiac', 'variable': 'Kľúčové slovo'},
                        height=400,
                        markers=True
                    )
                    fig_volume.update_layout(
                        xaxis_title="Mesiac",
                        yaxis_title="Počet vyhľadávaní",
                        legend_title="Kľúčové slovo",
                        hovermode='x unified'
                    )
                    st.plotly_chart(fig_volume, use_container_width=True)

                    # Samostatné dropdowny pre Share of Volume a Mesačný objem vyhľadávaní
                    with st.expander("📋 Share of Volume - Detailná tabuľka", expanded=False):
                        st.subheader("Share of Volume (%)")
                        st.dataframe(sov_df.round(2))
                    
                    with st.expander("📋 Mesačný objem vyhľadávaní - Detailná tabuľka", expanded=False):
                        st.subheader("Mesačný objem vyhľadávaní (absolútne hodnoty)")
                        st.dataframe(volume_df)

                    # Podkladové dáta a technické informácie - jeden veľký expander
                    with st.expander("🔧 Technické detaily a podkladové dáta", expanded=False):
                        # Debug informácie zo spracovania
                        st.subheader("Debug informácie zo spracovania")
                        for info in debug_info:
                            st.text(f"• {info}")
                        
                        # DataFrame detaily
                        st.subheader("Technické detaily DataFrame")
                        st.info(f"Stĺpce v DataFrame: {list(wide_df.columns)}")
                        st.info(f"Skutočne spracované kľúčové slová z API: {actual_keywords}")
                        st.info(f"Počítam SoV pre dostupné kľúčové slová: {available_keywords}")
                        st.info(f"Celkový počet záznamov: {len(long_df)}")
                        
                        # JSON odpoveď z API
                        st.subheader("Štruktúra JSON odpovede z API")
                        st.json(json_data)
                        
                        # Surové dáta DataFrame
                        st.subheader("Surové dáta (prvých 10 riadkov)")
                        st.dataframe(wide_df.head(10))
                        
                        # Filtrované dáta pre výpočet
                        st.subheader("Filtrované dáta pre výpočet SoV")
                        st.dataframe(wide_df_filtered.drop(columns='Total Volume'))

        except Exception as e:
            st.error(f"Vyskytla sa chyba: {e}")
            st.error("Skúste skontrolovať technické detaily v expanderi nižšie pre viac informácií.")
