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

def process_mm_response(json_data):
    """
    Spracuje JSON odpoveď z Marketing Miner do čistého Pandas DataFrame.
    Táto verzia najprv zobrazí štruktúru JSON pre debugging.
    """
    # Debug: Zobrazíme štruktúru JSON odpovede
    st.subheader("🔍 Debug: Štruktúra JSON odpovede")
    st.json(json_data)
    
    all_data = []
    
    # Skúsime rôzne možné štruktúry JSON odpovede
    try:
        # Variant 1: Originálna logika (status + data)
        if json_data.get('status') == 'success' and 'data' in json_data:
            st.info("Používam originálnu logiku spracovania (status + data)")
            for keyword_name, keyword_info in json_data.get('data', {}).items():
                if isinstance(keyword_info, dict) and 'search_volume' in keyword_info:
                    for date_str, volume in keyword_info['search_volume'].items():
                        all_data.append({
                            'Keyword': keyword_name,
                            'Date': datetime.strptime(date_str, '%Y-%m'),
                            'Search Volume': volume
                        })
        
        # Variant 2: Priame pole/zoznam kľúčových slov v koreňovom objekte
        elif isinstance(json_data, list):
            st.info("Spracovávam ako zoznam kľúčových slov")
            for item in json_data:
                if isinstance(item, dict) and 'keyword' in item:
                    keyword_name = item['keyword']
                    # Hľadáme mesačné dáta - môžu byť v rôznych kľúčoch
                    monthly_data = item.get('monthly_data', item.get('search_volume', item.get('data', {})))
                    if isinstance(monthly_data, dict):
                        for date_str, volume in monthly_data.items():
                            try:
                                all_data.append({
                                    'Keyword': keyword_name,
                                    'Date': datetime.strptime(date_str, '%Y-%m'),
                                    'Search Volume': volume
                                })
                            except ValueError:
                                # Skúsime iný formát dátumu
                                continue
        
        # Variant 3: Kľúčové slová sú priamo v koreňovom objekte
        elif isinstance(json_data, dict):
            st.info("Spracovávam ako slovník kľúčových slov v koreňovom objekte")
            for key, value in json_data.items():
                # Preskočíme systémové kľúče
                if key in ['status', 'message', 'error', 'success']:
                    continue
                
                # Ak je hodnota slovník, môže obsahovať dáta o kľúčovom slove
                if isinstance(value, dict):
                    keyword_name = key
                    
                    # Hľadáme mesačné dáta v rôznych možných kľúčoch
                    for possible_key in ['search_volume', 'monthly_data', 'data', 'volumes']:
                        if possible_key in value and isinstance(value[possible_key], dict):
                            for date_str, volume in value[possible_key].items():
                                try:
                                    all_data.append({
                                        'Keyword': keyword_name,
                                        'Date': datetime.strptime(date_str, '%Y-%m'),
                                        'Search Volume': volume
                                    })
                                except ValueError:
                                    continue
                            break
        
        # Variant 4: Štandardná štruktúra s results/keywords
        if not all_data and 'results' in json_data:
            st.info("Spracovávam štruktúru s 'results'")
            results = json_data['results']
            if isinstance(results, list):
                for item in results:
                    if isinstance(item, dict) and 'keyword' in item:
                        keyword_name = item['keyword']
                        monthly_data = item.get('monthly_searches', item.get('search_volume', {}))
                        if isinstance(monthly_data, dict):
                            for date_str, volume in monthly_data.items():
                                try:
                                    all_data.append({
                                        'Keyword': keyword_name,
                                        'Date': datetime.strptime(date_str, '%Y-%m'),
                                        'Search Volume': volume
                                    })
                                except ValueError:
                                    continue
        
        # Variant 5: Každé kľúčové slovo má svoj vlastný objekt s mesačnými dátami
        if not all_data:
            st.info("Skúšam alternatívnu štruktúru pre každé kľúčové slovo")
            for key, value in json_data.items():
                if isinstance(value, dict):
                    # Ak obsahuje priamo mesačné dáta (rok-mesiac: objem)
                    potential_monthly_data = {}
                    for sub_key, sub_value in value.items():
                        # Skúsime rozpoznať formát YYYY-MM
                        if isinstance(sub_key, str) and len(sub_key) == 7 and sub_key.count('-') == 1:
                            try:
                                datetime.strptime(sub_key, '%Y-%m')
                                potential_monthly_data[sub_key] = sub_value
                            except ValueError:
                                continue
                    
                    if potential_monthly_data:
                        for date_str, volume in potential_monthly_data.items():
                            all_data.append({
                                'Keyword': key,
                                'Date': datetime.strptime(date_str, '%Y-%m'),
                                'Search Volume': volume
                            })
        
        st.info(f"Spracované {len(all_data)} záznamov dát")
        
    except Exception as e:
        st.error(f"Chyba pri spracovaní JSON odpovede: {e}")
        st.info("Skúste skontrolovať štruktúru JSON odpovede vyššie")
    
    if not all_data:
        if 'message' in json_data:
            raise Exception(f"API vrátilo chybu: {json_data['message']}")
        st.warning("Nepodarilo sa extrahovať žiadne dáta z JSON odpovede. Skontrolujte štruktúru JSON vyššie.")
        return pd.DataFrame()
        
    return pd.DataFrame(all_data)


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
            keywords_string = ','.join(keyword_list)
            
            raw_data = fetch_mm_data(api_key, keywords_string, country_code)
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
