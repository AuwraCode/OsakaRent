import streamlit as st
import pandas as pd
import xgboost as xgb
import folium
from streamlit_folium import st_folium
import os
import time
from scraper import run_osaka_miner

# --- CONFIGURATION ---
st.set_page_config(
    page_title="Osaka Real Estate Arbitrage Engine",
    layout="wide",
    page_icon="🏯",
    initial_sidebar_state="collapsed"
)

# --- CSS: DARK MODE, CARD SEPARATION & HIGH CONTRAST ---
st.markdown("""
<style>
    /* 1. Global Background Reset */
    .stApp {
        background-color: #0e1117; /* Pitch black background for the page */
    }

    /* 2. CARD STYLING (The fix for white spaces) */
    /* Target the container with border (st.container(border=True)) */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #151921; /* Deep Charcoal Card Background */
        border: 1px solid #30333F; /* Subtle border */
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 15px; /* Space between cards */
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3); /* Lift it off the page */
    }
    
    /* Remove default Streamlit gaps inside the card */
    div[data-testid="stVerticalBlockBorderWrapper"] > div {
        gap: 0.5rem;
    }

    /* 3. Typography & Compactness */
    h1, h3 { padding-top: 0rem; padding-bottom: 0rem; }
    div[data-testid="stExpander"] div[data-testid="stVerticalBlock"] { gap: 0.5rem; }

    /* 4. Image Sizing */
    img { 
        height: 180px; 
        object-fit: cover; 
        width: 100%; 
        border-radius: 6px; 
        border: 1px solid #333;
    }
    
    /* 5. Custom Tags */
    .tag { display: inline-block; padding: 3px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 700; margin-right: 5px; margin-bottom: 5px;}
    .tag-green { background: #0f3d24; color: #66ff99; border: 1px solid #1a5c35; } /* Neon Green on Dark */
    .tag-red { background: #3d0f0f; color: #ff6666; border: 1px solid #5c1a1a; } /* Neon Red on Dark */
    .tag-blue { background: #0f243d; color: #66b3ff; border: 1px solid #1a355c; } /* Neon Blue on Dark */
    
    /* 6. Button Styling */
    .stButton button { 
        width: 100%; 
        background-color: #262730; 
        color: white; 
        border: 1px solid #444;
    }
    .stButton button:hover {
        border-color: #00ff00;
        color: #00ff00;
    }
</style>
""", unsafe_allow_html=True)

# --- DATA LOADER ---
DATA_PATH = "../data/osaka_listings.csv"

@st.cache_data
def load_data():
    if not os.path.exists(DATA_PATH): return pd.DataFrame()
    return pd.read_csv(DATA_PATH)

df = load_data()

# --- TOP BAR ---
c_title, c_kpi1, c_kpi2, c_kpi3 = st.columns([4, 1, 1, 1])
with c_title:
    st.title("🏯 Osaka Arbitrage Engine")
    st.caption("Advanced Real Estate Analytics & Mining System")

# KPIs at the top
if not df.empty:
    with c_kpi1: st.metric("Total Assets", len(df))
    with c_kpi2: st.metric("Avg Rent", f"¥{int(df['total_rent'].mean()):,}")
    with c_kpi3: st.metric("Mapped", len(df.dropna(subset=['lat'])))

# =========================================================
# 1. HIGH-DENSITY CONTROL PANEL
# =========================================================
with st.expander("🎛️  SYSTEM CONTROLS & FILTERS", expanded=True):
    
    # --- ROW 1: MINING OPERATIONS ---
    col_mine, col_filter1, col_filter2, col_filter3 = st.columns([1.5, 1.5, 1.5, 1.5])
    
    with col_mine:
        st.markdown("**⛏️ Data Mining**")
        pages_scan = st.slider("Scan Depth (Pages)", 1, 50, 2, help="50 pages ≈ 1 hour of processing (Geocoding)")
        if st.button("🔴 EXECUTE MINER"):
            status_box = st.empty()
            prog_bar = st.progress(0)
            
            try:
                with st.spinner("Connecting to Japan Residential Database..."):
                    new_df = run_osaka_miner(max_pages=pages_scan, status_placeholder=status_box, progress_bar=prog_bar)
                st.success(f"Ingested {len(new_df)} units.")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"Critical Failure: {e}")

    if not df.empty:
        # --- ROW 1 CONT: FILTERS ---
        with col_filter1:
            st.markdown("**💴 Financials**")
            min_r, max_r = int(df['total_rent'].min()), int(df['total_rent'].max())
            rent_range = st.slider("Rent (¥)", min_r, max_r, (min_r, max_r))
            zero_key = st.checkbox("No Key Money / Deposit")

        with col_filter2:
            st.markdown("**📐 Specs**")
            min_s, max_s = int(df['size_m2'].min()), int(df['size_m2'].max())
            size_range = st.slider("Size (m²)", min_s, max_s, (20, 100))
            min_floor = st.number_input("Min Floor", 1, 50, 2)

        with col_filter3:
            st.markdown("**🏢 Building**")
            max_age = int(df['age'].max())
            age_range = st.slider("Max Age (Years)", 0, max_age, 35)
            layouts = st.multiselect("Layouts", df['layout'].unique(), default=df['layout'].value_counts().index[:5].tolist())

# =========================================================
# 2. ANALYTICAL ENGINE
# =========================================================
if df.empty:
    st.info("System Idle. Initialize Miner to begin data ingestion.")
else:
    # --- FILTER LOGIC ---
    mask = (
        (df['total_rent'].between(rent_range[0], rent_range[1])) &
        (df['size_m2'].between(size_range[0], size_range[1])) &
        (df['age'] <= age_range) &
        (df['floor'] >= min_floor) &
        (df['layout'].isin(layouts))
    )
    df_filtered = df[mask].copy()
    
    if zero_key:
        df_filtered = df_filtered[(df_filtered['key_money'] == 0) & (df_filtered['deposit'] == 0)]

    if df_filtered.empty:
        st.warning("No assets match criteria.")
    else:
        # --- XGBOOST VALUATION ---
        df_filtered['layout_code'] = df_filtered['layout'].astype('category').cat.codes
        features = ['size_m2', 'age', 'floor', 'layout_code']
        target = 'total_rent'
        
        ml_df = df_filtered.dropna(subset=features + [target])
        
        if len(ml_df) > 5:
            model = xgb.XGBRegressor(objective='reg:squarederror', n_estimators=100)
            model.fit(ml_df[features], ml_df[target])
            df_filtered['predicted_rent'] = model.predict(df_filtered[features].fillna(0))
            df_filtered['residual'] = df_filtered['total_rent'] - df_filtered['predicted_rent']
            
            def get_status(row):
                if row['residual'] < -5000: return "Undervalued"
                if row['residual'] > 5000: return "Overpriced"
                return "Fair Value"
            
            df_filtered['status'] = df_filtered.apply(get_status, axis=1)

        # --- VIEW TABS ---
        t_list, t_map, t_raw = st.tabs(["📋 List View", "🗺️ Full Map", "💾 Data Export"])

        # --- TAB 1: LIST ---
        with t_list:
            # Pagination
            ITEMS = 12
            if 'page' not in st.session_state: st.session_state.page = 0
            
            # Sorting
            sort_opt = st.selectbox("Sort By", ["Best Deal (Arbitrage)", "Cheapest Rent", "Largest Size"], index=0)
            if sort_opt == "Best Deal (Arbitrage)":
                df_view = df_filtered.sort_values('residual', ascending=True)
            elif sort_opt == "Cheapest Rent":
                df_view = df_filtered.sort_values('total_rent', ascending=True)
            else:
                df_view = df_filtered.sort_values('size_m2', ascending=False)
            
            # Slice
            max_p = max(1, (len(df_view) // ITEMS) + 1)
            if st.session_state.page >= max_p: st.session_state.page = max_p - 1
            if st.session_state.page < 0: st.session_state.page = 0
            
            start = st.session_state.page * ITEMS
            page_df = df_view.iloc[start : start + ITEMS]
            
            st.markdown(f"**Showing {start+1}-{min(start+ITEMS, len(df_view))} of {len(df_view)}**")
            
            # Render Grid
            for _, row in page_df.iterrows():
                # CRITICAL CHANGE: We use st.container(border=True) which our CSS targets
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([1.2, 2.5, 1.5, 1])
                    
                    with c1:
                        if pd.notna(row.get('image_url')) and row['image_url']:
                            st.image(row['image_url'])
                        else:
                            st.markdown('<div style="height:160px; background:#333; color:#777; display:flex; align-items:center; justify-content:center; border-radius:4px;">No IMG</div>', unsafe_allow_html=True)
                            
                    with c2:
                        st.subheader(row['name'])
                        st.caption(f"📍 {row['address']}")
                        
                        # Tags
                        tags_html = ""
                        status = row.get('status')
                        if status == "Undervalued":
                            tags_html += f"<span class='tag tag-green'>💎 Save ¥{int(row['residual']*-1):,}</span>"
                        elif status == "Overpriced":
                            tags_html += "<span class='tag tag-red'>Overpriced</span>"
                        
                        if row['size_m2'] > 50: tags_html += "<span class='tag tag-blue'>Large</span>"
                        st.markdown(tags_html, unsafe_allow_html=True)
                        
                        st.write(f"**{row['layout']}** | {row['size_m2']}m² | {row['floor']}F | {row['age']} yrs")
                        
                    with c3:
                        st.metric("Rent", f"¥{int(row['total_rent']):,}")
                        if 'residual' in row:
                            val = int(row['residual']) * -1
                            st.metric("Arbitrage", f"¥{val:,}", delta=val)
                            
                    with c4:
                        st.write("")
                        st.link_button("View ↗", row['link'])

            # Controls
            b1, _, b2 = st.columns([1, 4, 1])
            if b1.button("⬅️ Prev"):
                st.session_state.page -= 1
                st.rerun()
            if b2.button("Next ➡️"):
                st.session_state.page += 1
                st.rerun()

        # --- TAB 2: FULL MAP (UNLIMITED) ---
        with t_map:
            map_data = df_filtered.dropna(subset=['lat', 'lon'])
            if map_data.empty:
                st.warning("No geospatial data. Run the miner to populate coordinates.")
            else:
                st.write(f"Mapping {len(map_data)} assets across Osaka.")
                
                # Center on Data
                center = [map_data['lat'].mean(), map_data['lon'].mean()]
                m = folium.Map(location=center, zoom_start=12, tiles="CartoDB dark_matter")
                
                # Marker Cluster
                from folium.plugins import MarkerCluster
                marker_cluster = MarkerCluster().add_to(m)
                
                for _, row in map_data.iterrows():
                    status = row.get('status', 'N/A')
                    color = "green" if status == "Undervalued" else "red" if status == "Overpriced" else "gray"
                    
                    # Popup Link
                    popup_html = f"""
                    <div style="font-family:sans-serif; width:220px; color: black;">
                        <b>{row['name']}</b><br>
                        Rent: ¥{int(row['total_rent']):,}<br>
                        Status: <span style='color:{color}; font-weight:bold;'>{status}</span><br>
                        Size: {row['size_m2']} m²<br>
                        <a href="{row['link']}" target="_blank">View Listing</a>
                    </div>
                    """
                    
                    # --- FIXED BLIP DETAILS ---
                    # Tooltip now shows much more than just price
                    tooltip_text = f"{row['name']} | ¥{int(row['total_rent']):,} | {status}"
                    
                    folium.CircleMarker(
                        location=[row['lat'], row['lon']],
                        radius=5, color=color, fill=True, fill_color=color, fill_opacity=0.8,
                        popup=popup_html,
                        tooltip=tooltip_text 
                    ).add_to(marker_cluster)
                
                st_folium(m, height=700, use_container_width=True)

        # --- TAB 3: EXPORT ---
        with t_raw:
            st.markdown("### 💾 Export Data")
            st.write("Download the full dataset for Excel/Python analysis.")
            csv = df_filtered.to_csv(index=False).encode('utf-8')
            st.download_button("Download CSV", data=csv, file_name="osaka_arbitrage_data.csv", mime="text/csv")