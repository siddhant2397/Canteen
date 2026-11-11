
import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime

st.set_page_config(page_title="Canteen Portal", page_icon="☕", layout="wide")

# Connect to Google Sheet via Streamlit native connection
conn = st.connection("gsheets", type=GSheetsConnection)

# Helper function to read data with zero cache so updates reflect live
def load_data(sheet_name):
    return conn.read(worksheet=sheet_name, ttl=0)

# -------------------------------------------------------------
# SIDEBAR NAVIGATION
# -------------------------------------------------------------
st.sidebar.title("📌 Canteen Portal")
view_mode = st.sidebar.radio("Navigation", ["Customer Portal", "Admin Dashboard"])

# =============================================================
# VIEW 1: CUSTOMER PORTAL
# =============================================================
if view_mode == "Customer Portal":
    st.title("🍽️ Canteen Menu & Demands")
    st.caption("Live availability, pricing, and demand submission.")
    
    # Load inventory from Google Sheets
    df_inv = load_data("Inventory")
    
    # Ensure correct data types
    if not df_inv.empty:
        df_inv["Price"] = pd.to_numeric(df_inv["Price"], errors="coerce").fillna(0)
        df_inv["Stock"] = pd.to_numeric(df_inv["Stock"], errors="coerce").fillna(0).astype(int)
        df_inv["Available"] = df_inv["Available"].astype(str).str.strip().str.title()
    
    tab_menu, tab_demand = st.tabs(["📋 Menu & Stock Status", "📝 Demand Unavailable Item"])
    
    # --- Tab 1: View Menu ---
    with tab_menu:
        if not df_inv.empty:
            # Status filter
            status_filter = st.radio(
                "Filter Items:", 
                ["All Items", "Available Only", "Out of Stock / Unavailable"], 
                horizontal=True
            )
            
            display_df = df_inv.copy()
            if status_filter == "Available Only":
                display_df = display_df[display_df["Available"] == "Yes"]
            elif status_filter == "Out of Stock / Unavailable":
                display_df = display_df[display_df["Available"] == "No"]
                
            # Category filter
            categories = ["All"] + sorted(display_df["Category"].dropna().unique().tolist())
            selected_cat = st.selectbox("Category Filter:", categories)
            if selected_cat != "All":
                display_df = display_df[display_df["Category"] == selected_cat]
                
            # Visual status column
            display_df["Status"] = display_df.apply(
                lambda r: f"🟢 Available ({r['Stock']} in stock)" if r["Available"] == "Yes" and r["Stock"] > 0 else "🔴 Not Available",
                axis=1
            )
            display_df["Price (₹)"] = display_df["Price"].apply(lambda p: f"₹{p:.2f}")
            
            # Show table
            st.dataframe(
                display_df[["Item Name", "Category", "Price (₹)", "Status"]],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("Inventory sheet is currently empty.")

    # --- Tab 2: User Demand Form ---
    with tab_demand:
        st.subheader("Request an Item Not Currently Available")
        st.write("Submit a request for permissible items that are currently out of stock or not listed.")
        
        # Populate list of non-available items from inventory + allow custom typing
        unavail_items = []
        if not df_inv.empty:
            unavail_items = df_inv[df_inv["Available"] == "No"]["Item Name"].tolist()
        
        with st.form("demand_form", clear_on_submit=True):
            user_id = st.text_input("Unique ID Number (Roll No / Employee ID / Service No)")
            user_name = st.text_input("Your Full Name")
            
            selection_type = st.radio("Item Type:", ["Select from unavailable canteen list", "Other permissible item"])
            
            if selection_type == "Select from unavailable canteen list" and unavail_items:
                requested_item = st.selectbox("Select Item:", unavail_items)
            else:
                requested_item = st.text_input("Enter Item Name:")
                
            submit_demand = st.form_submit_button("Submit Demand")
            
            if submit_demand:
                if not user_id.strip() or not user_name.strip() or not requested_item.strip():
                    st.error("Please fill in all details before submitting.")
                else:
                    df_demand = load_data("Demand")
                    new_entry = pd.DataFrame([{
                        "Unique ID": str(user_id).strip(),
                        "Name": user_name.strip(),
                        "Item Requested": requested_item.strip(),
                        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }])
                    
                    updated_demand = pd.concat([df_demand, new_entry], ignore_index=True)
                    conn.update(worksheet="Demand", data=updated_demand)
                    st.success(f"Demand recorded for '{requested_item}'. Thank you, {user_name}!")

# =============================================================
# VIEW 2: ADMIN DASHBOARD
# =============================================================
else:
    st.title("⚙️ Canteen Admin Panel")
    
    admin_pin = st.sidebar.text_input("Enter Admin PIN", type="password")
    
    if admin_pin != "1234":  # Replace with your secure PIN
        st.warning("Please enter the correct Admin PIN in the sidebar to access controls.")
    else:
        st.success("Authenticated as Admin")
        df_inv = load_data("Inventory")
        df_demand = load_data("Demand")
        
        tab_admin_stock, tab_admin_demand, tab_admin_add = st.tabs([
            "📦 Manage Inventory & Stock", 
            "📊 Demand Analytics", 
            "➕ Add New Permissible Item"
        ])
        
        # --- Admin Tab 1: Edit Stock / Price / Availability ---
        with tab_admin_stock:
            st.subheader("Edit Existing Items")
            st.caption("Modify price, stock quantity, or toggle availability directly.")
            
            if not df_inv.empty:
                item_to_edit = st.selectbox("Select Item to Update:", df_inv["Item Name"].tolist())
                current_row = df_inv[df_inv["Item Name"] == item_to_edit].iloc[0]
                
                with st.form("edit_item_form"):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        new_price = st.number_input("Selling Price (₹)", value=float(current_row["Price"]), step=1.0)
                    with col2:
                        new_stock = st.number_input("Current Stock Count", value=int(current_row["Stock"]), step=1, min_value=0)
                    with col3:
                        avail_index = 0 if str(current_row["Available"]).strip().title() == "Yes" else 1
                        new_avail = st.selectbox("Available for Sale?", ["Yes", "No"], index=avail_index)
                    
                    save_changes = st.form_submit_button("Save Changes to Google Sheet")
                    
                    if save_changes:
                        idx = df_inv[df_inv["Item Name"] == item_to_edit].index[0]
                        df_inv.at[idx, "Price"] = new_price
                        df_inv.at[idx, "Stock"] = new_stock
                        df_inv.at[idx, "Available"] = new_avail
                        
                        conn.update(worksheet="Inventory", data=df_inv)
                        st.success(f"Updated {item_to_edit} successfully!")
                        st.rerun()
            else:
                st.info("No items in inventory.")
                
        # --- Admin Tab 2: Demand Dashboard ---
        with tab_admin_demand:
            st.subheader("Demand & Restock Insights")
            if not df_demand.empty:
                col_chart, col_summary = st.columns([3, 2])
                
                demand_counts = df_demand["Item Requested"].value_counts().reset_index()
                demand_counts.columns = ["Item Requested", "Total Demands"]
                
                with col_chart:
                    st.write("**Most Requested Items:**")
                    st.bar_chart(demand_counts.set_index("Item Requested"))
                    
                with col_summary:
                    st.write("**Top Demanded Items Summary:**")
                    st.dataframe(demand_counts, use_container_width=True, hide_index=True)
                
                st.divider()
                st.subheader("Individual Request Log")
                st.dataframe(df_demand.sort_values(by="Timestamp", ascending=False), use_container_width=True, hide_index=True)
            else:
                st.info("No customer demands recorded yet.")

        # --- Admin Tab 3: Add New Item ---
        with tab_admin_add:
            st.subheader("Add a New Permissible Item to Catalog")
            with st.form("add_item_form", clear_on_submit=True):
                add_name = st.text_input("Item Name")
                add_cat = st.selectbox("Category", ["Beverages", "Snacks", "Meals", "Packaged Goods", "Toiletries", "Other"])
                add_price = st.number_input("Selling Price (₹)", min_value=1.0, step=1.0)
                add_stock = st.number_input("Opening Stock", min_value=0, step=1)
                add_avail = st.selectbox("Is it Available right now?", ["Yes", "No"])
                
                if st.form_submit_button("Add Item"):
                    if not add_name.strip():
                        st.error("Item name is required.")
                    else:
                        new_item = pd.DataFrame([{
                            "Item Name": add_name.strip(),
                            "Category": add_cat,
                            "Price": add_price,
                            "Stock": add_stock,
                            "Available": add_avail
                        }])
                        updated_inv = pd.concat([df_inv, new_item], ignore_index=True)
                        conn.update(worksheet="Inventory", data=updated_inv)
                        st.success(f"Added {add_name} to Google Sheets!")
                        st.rerun()
