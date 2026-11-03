"""
ETL Pipeline for Monthly Fabric Stock & Liability Report
Processes:
1. Details.xlsx (Power BI Export)
2. raw_data/InventoryOnHand_20261023.xlsx (D365 Standard Costs)
3. raw_data/RM to Customer.xlsx (Customer Mapping)
4. raw_data/RSG UPH Aged Detail Cover_FORM.xlsx (Demand & Reference)

Outputs:
- src/data/inventory_data.json (for React dashboard)
- public/inventory_data.json (for static fetch)
"""

import os
import json
import openpyxl
from datetime import datetime

def parse_date(val):
    if val is None:
        return ""
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d")
    return str(val).split(" ")[0]

def get_aging_bucket(days):
    if days is None:
        return "Unknown"
    try:
        d = float(days)
    except:
        return "Unknown"

    if d < 90:
        return "0-3 months"
    elif d < 180:
        return "3-6 months"
    elif d < 360:
        return "6-12 months"
    elif d < 720:
        return "12-24 months"
    else:
        return "+24 months"

def main():
    import zipfile
    zip_path = "FW__PowerBI_-_monthly_fabric_stock_and_liability.zip"
    if not os.path.exists("raw_data") and os.path.exists(zip_path):
        print(f"Extracting {zip_path}...")
        os.makedirs("raw_data", exist_ok=True)
        with zipfile.ZipFile(zip_path, 'r') as z:
            z.extractall("raw_data")

    print("Step 1: Loading Standard Costs...")
    cost_map = {}
    cost_by_item = {}
    onhand_file = "raw_data/InventoryOnHand_20261023.xlsx"
    if os.path.exists(onhand_file):
        wb_c = openpyxl.load_workbook(onhand_file, data_only=True)
        ws_c = wb_c["Inventory OnHand"]
        headers_c = [ws_c.cell(1, c).value for c in range(1, ws_c.max_column + 1)]
        item_idx = headers_c.index("Item Id")
        cost_idx = headers_c.index("Standard Cost")
        batch_idx = headers_c.index("Batch")

        for r in range(2, ws_c.max_row + 1):
            it = ws_c.cell(r, item_idx + 1).value
            co = ws_c.cell(r, cost_idx + 1).value
            ba = ws_c.cell(r, batch_idx + 1).value
            if it and co is not None:
                try:
                    c_val = float(co)
                    cost_by_item[str(it).strip().upper()] = c_val
                    if ba:
                        cost_map[(str(it).strip().upper(), str(ba).strip().upper())] = c_val
                except:
                    pass

    # Reference costs fallback
    ref_file = "raw_data/RSG UPH Aged Detail Cover_FORM.xlsx"
    if os.path.exists(ref_file):
        wb_r = openpyxl.load_workbook(ref_file, data_only=True)
        ws_ar = wb_r["AR COVERS"]
        for r in range(3, ws_ar.max_row + 1):
            part = ws_ar.cell(r, 3).value
            cost = ws_ar.cell(r, 7).value
            if part and cost:
                try:
                    p_key = str(part).strip().upper()
                    if p_key not in cost_by_item:
                        cost_by_item[p_key] = float(cost)
                except:
                    pass

    print(f"Loaded {len(cost_by_item)} distinct item costs.")

    print("Step 2: Loading Customer Mapping...")
    customer_map = {}
    cust_file = "raw_data/RM to Customer.xlsx"
    if os.path.exists(cust_file):
        wb_cust = openpyxl.load_workbook(cust_file, data_only=True)
        ws_cust = wb_cust["Sheet1"]
        for r in range(3, ws_cust.max_row + 1):
            cust = ws_cust.cell(r, 2).value
            part = ws_cust.cell(r, 3).value
            if part and cust:
                customer_map[str(part).strip().upper()] = str(cust).strip()
    print(f"Loaded {len(customer_map)} customer mappings.")

    print("Step 3: Loading Demand & Allocation from Reference...")
    demand_by_part = {}
    monthly_demand = {}
    monthly_incoming = {}
    # Define 4 projection months
    proj_months = ["2026-11", "2026-12", "2027-01", "2027-02"]

    if os.path.exists(ref_file):
        wb_ref = openpyxl.load_workbook(ref_file, data_only=True)
        ws_dem = wb_ref["Demand"]
        # Demand cols: Col 6 = PART NUMBER, Col 8 = RE QDATE, Col 9 = TOTAL PLANNED ISSUE QTY
        # Incoming PO cols: Col 14 = QTYALLOCATED PO (col index 13), Col 21 = PO ETA (col index 20)
        for r in range(3, ws_dem.max_row + 1):
            part = ws_dem.cell(r, 6).value
            req_date = ws_dem.cell(r, 8).value
            qty = ws_dem.cell(r, 9).value
            po_qty = ws_dem.cell(r, 14).value
            po_eta = ws_dem.cell(r, 21).value

            if part:
                p_key = str(part).strip().upper()

                # Process Demand
                if qty:
                    try:
                        q_val = float(qty)
                    except:
                        q_val = 0.0
                    demand_by_part[p_key] = demand_by_part.get(p_key, 0.0) + q_val

                    # Determine demand month
                    m_str = None
                    if req_date:
                        d_s = str(req_date).strip().upper()
                        for pm in proj_months:
                            y, m = pm.split("-")
                            month_abbr = datetime.strptime(m, "%m").strftime("%b").upper()
                            if month_abbr in d_s and y in d_s:
                                m_str = pm
                                break
                    if not m_str:
                        m_str = proj_months[0]

                    if p_key not in monthly_demand:
                        monthly_demand[p_key] = {pm: 0.0 for pm in proj_months}
                    monthly_demand[p_key][m_str] += q_val

                # Process Incoming PO
                if po_qty:
                    try:
                        po_val = float(po_qty)
                    except:
                        po_val = 0.0
                    if po_val > 0:
                        m_inc_str = proj_months[0]
                        if po_eta:
                            eta_s = str(po_eta).strip().upper()
                            if "DEC" in eta_s: m_inc_str = "2026-12"
                            elif "JAN" in eta_s: m_inc_str = "2027-01"
                            elif "FEB" in eta_s: m_inc_str = "2027-02"
                            elif "NOV" in eta_s: m_inc_str = "2026-11"
                        if p_key not in monthly_incoming:
                            monthly_incoming[p_key] = {pm: 0.0 for pm in proj_months}
                        monthly_incoming[p_key][m_inc_str] += po_val

    print(f"Loaded demand for {len(demand_by_part)} distinct parts.")
    print(f"Loaded incoming POs for {len(monthly_incoming)} distinct parts.")

    print("Step 4: Processing Details.xlsx...")
    wb_d = openpyxl.load_workbook("Details.xlsx", read_only=True)
    ws_d = wb_d["Export"]

    records = []

    # Details columns:
    # 0: BATCHNUMBER
    # 1: ITEMNUMBER
    # 2: CONFIGURATION
    # 3: PRODUCTGROUPID
    # 4: WAREHOUSE
    # 5: LOCATION
    # 6: PHYSICALINVENTORY
    # 7: REGISTERED
    # 8: PHYSICALRESERVED
    # 9: AVAILABLEPHYSICAL
    # 10: Qty_Inspection
    # 11: TransferQty
    # 12: DESCRIPTION
    # 13: PO
    # 14: Inventtransid
    # 15: receive_date
    # 16: Supplier Code
    # 17: PR
    # 18: PR Line
    # 19: Stanrdcost
    # 20: MANUFACTURINGDATE
    # 21: Aging
    # 22: Registered_PO
    # 23: Registered_WO

    for row in ws_d.iter_rows(min_row=2, values_only=True):
        item = str(row[1]).strip() if row[1] else ""
        if not item.startswith(("LH-01", "LH-03", "LH-07")):
            continue

        prod_group = str(row[3]).strip() if row[3] else ""
        # Only take Fabric, Leather, and PU/PVC
        if prod_group not in ("RM_FABRIC", "RM_LEATHER", "RM_PU/PVC"):
            continue

        loc = str(row[5]).strip() if row[5] else ""
        loc_upper = loc.upper()
        if "DEFECT" in loc_upper or loc_upper == "UPH WIP":
            continue

        batch = str(row[0]).strip() if row[0] else ""
        item_upper = item.upper()
        batch_upper = batch.upper()

        # Quantity
        try:
            qty = float(row[6]) if row[6] is not None else 0.0
        except:
            qty = 0.0

        # Registered PO / Incoming
        try:
            reg_po = float(row[22]) if row[22] is not None else 0.0
        except:
            reg_po = 0.0

        # Available & Reserved
        try:
            avail = float(row[9]) if row[9] is not None else 0.0
        except:
            avail = 0.0

        try:
            reserved = float(row[8]) if row[8] is not None else 0.0
        except:
            reserved = 0.0

        # Standard Cost
        cost = 0.0
        # If COM item, cost is 0
        if "COM" in item_upper:
            cost = 0.0
        elif row[19] is not None and float(row[19]) > 0:
            cost = float(row[19])
        elif (item_upper, batch_upper) in cost_map and cost_map[(item_upper, batch_upper)] > 0:
            cost = cost_map[(item_upper, batch_upper)]
        elif item_upper in cost_by_item and cost_by_item[item_upper] > 0:
            cost = cost_by_item[item_upper]

        # Customer Mapping
        customer = customer_map.get(item_upper)
        if not customer:
            parts = item_upper.split("-")
            if len(parts) >= 3:
                base_part = f"{parts[0]}-{parts[1]}-{parts[2]}"
                customer = customer_map.get(base_part, "OTHERS")
            else:
                customer = "OTHERS"

        # Aging in Days & Bucket
        try:
            aging_days = int(row[21]) if row[21] is not None else 0
        except:
            aging_days = 0
        aging_bucket = get_aging_bucket(aging_days)

        # Financial Calculations (per NOTES.md and RSG template)
        total_cost = round(qty * cost, 2)
        import_duty = round(total_cost * 0.12, 2)
        vat = round((total_cost + import_duty) * 0.08, 2)
        total_after_tax = round(total_cost + import_duty + vat, 2)

        # UOM inference
        # LH-01 (Leather): usually SqFt or Yard; LH-03 (Fabric): Yard or Meter; LH-07: Meter
        uom = "SqFt" if item.startswith("LH-01") else ("Meter" if item.startswith("LH-07") else "Yard")

        record = {
            "batch": batch,
            "item": item,
            "customer": customer,
            "product_group": str(row[3]).strip() if row[3] else "RM_FABRIC",
            "warehouse": str(row[4]).strip() if row[4] else "",
            "location": loc,
            "qty": round(qty, 2),
            "available": round(avail, 2),
            "reserved": round(reserved, 2),
            "registered_po": round(reg_po, 2),
            "description": str(row[12]).strip() if row[12] else "",
            "po": str(row[13]).strip() if row[13] else "",
            "receive_date": parse_date(row[15]),
            "mfg_date": parse_date(row[20]),
            "supplier": str(row[16]).strip() if row[16] else "",
            "standard_cost": round(cost, 2),
            "total_cost": total_cost,
            "import_duty": import_duty,
            "vat": vat,
            "total_after_tax": total_after_tax,
            "aging_days": aging_days,
            "aging_bucket": aging_bucket,
            "uom": uom,
            "is_com": "COM" in item_upper
        }
        records.append(record)

    print(f"Processed {len(records)} inventory batch records.")

    # Step 5: Aggregate item-level 4-month projection matrix
    item_aggregates = {}
    for r in records:
        it = r["item"].upper()
        if it not in item_aggregates:
            item_aggregates[it] = {
                "item": r["item"],
                "customer": r["customer"],
                "description": r["description"],
                "supplier": r["supplier"],
                "standard_cost": r["standard_cost"],
                "total_qty": 0.0,
                "total_cost": 0.0,
                "total_after_tax": 0.0,
                "registered_po": 0.0,
                "demand": demand_by_part.get(it, 0.0),
                "monthly_demand": monthly_demand.get(it, {pm: 0.0 for pm in proj_months}),
                "aging_qty": {
                    "0-3 months": 0.0,
                    "3-6 months": 0.0,
                    "6-12 months": 0.0,
                    "12-24 months": 0.0,
                    "+24 months": 0.0
                }
            }
        agg = item_aggregates[it]
        agg["total_qty"] += r["qty"]
        agg["total_cost"] += r["total_cost"]
        agg["total_after_tax"] += r["total_after_tax"]
        agg["registered_po"] += r["registered_po"]
        agg["aging_qty"][r["aging_bucket"]] += r["qty"]

    # Calculate Stock Projection & Balance per item (matching AR COVERS format):
    # Balance = Current On-Hand - Total Demand
    # Final Free Stock = Balance + Total Incoming = Current On-Hand + Total Incoming - Total Demand
    projections = []
    for it, agg in item_aggregates.items():
        start_stock = agg["total_qty"]
        m_inc = monthly_incoming.get(it, {pm: 0.0 for pm in proj_months}).copy()
        if agg["registered_po"] > sum(m_inc.values()):
            diff = agg["registered_po"] - sum(m_inc.values())
            m_inc[proj_months[0]] += diff

        total_inc = round(sum(m_inc.values()), 2)
        total_demand = round(sum(agg["monthly_demand"].values()), 2)

        balance = round(start_stock - total_demand, 2)
        free_stock = round(start_stock + total_inc - total_demand, 2)

        # Average weekly consumption (AWS) = total_demand / (4 months * 4.33 weeks)
        avg_weekly_demand = (total_demand / 17.3) if total_demand > 0 else 0.0
        aws = round(start_stock / avg_weekly_demand, 1) if avg_weekly_demand > 0 else 999.0

        uom = "SqFt" if agg["item"].startswith("LH-01") else ("Meter" if agg["item"].startswith("LH-07") else "Yard")
        free_stock_cost = round(max(0, free_stock) * agg["standard_cost"], 2)
        free_stock_tax = round(free_stock_cost * 1.2096, 2)

        status = "Surplus"
        if free_stock < 0:
            status = "Deficit"
        elif aws > 0 and aws < 4:
            status = "Low Buffer"
        elif aws >= 4 and aws <= 16:
            status = "Balanced"

        projections.append({
            "item": agg["item"],
            "customer": agg["customer"],
            "description": agg["description"],
            "supplier": agg["supplier"],
            "uom": uom,
            "standard_cost": agg["standard_cost"],
            "on_hand": round(start_stock, 2),
            "incoming": total_inc,
            "demand": total_demand,
            "balance": balance,
            "free_stock": free_stock,
            "free_stock_cost": free_stock_cost,
            "free_stock_tax": free_stock_tax,
            "aws": aws if aws < 999 else "No Demand",
            "status": status,
            "total_cost": round(agg["total_cost"], 2),
            "total_after_tax": round(agg["total_after_tax"], 2)
        })

    # Summary KPIs
    total_qty = sum(r["qty"] for r in records)
    total_cost = sum(r["total_cost"] for r in records)
    total_duty = sum(r["import_duty"] for r in records)
    total_vat = sum(r["vat"] for r in records)
    total_after_tax = sum(r["total_after_tax"] for r in records)

    # Aging tier breakdown
    aging_summary = {}
    for bucket in ["0-3 months", "3-6 months", "6-12 months", "12-24 months", "+24 months"]:
        b_records = [r for r in records if r["aging_bucket"] == bucket]
        b_qty = sum(r["qty"] for r in b_records)
        b_cost = sum(r["total_cost"] for r in b_records)
        b_duty = sum(r["import_duty"] for r in b_records)
        b_vat = sum(r["vat"] for r in b_records)
        b_tax = sum(r["total_after_tax"] for r in b_records)
        aging_summary[bucket] = {
            "count": len(b_records),
            "qty": round(b_qty, 2),
            "cost": round(b_cost, 2),
            "import_duty": round(b_duty, 2),
            "vat": round(b_vat, 2),
            "total_after_tax": round(b_tax, 2),
            "qty_pct": round(b_qty / total_qty * 100, 1) if total_qty > 0 else 0,
            "cost_pct": round(b_cost / total_cost * 100, 1) if total_cost > 0 else 0
        }

    # Customer breakdown
    customers = sorted(list(set(r["customer"] for r in records)))
    warehouses = sorted(list(set(r["warehouse"] for r in records if r["warehouse"])))
    product_groups = sorted(list(set(r["product_group"] for r in records)))

    dataset = {
        "metadata": {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_batches": len(records),
            "distinct_items": len(item_aggregates),
            "projection_months": ["Nov 2026", "Dec 2026", "Jan 2027", "Feb 2027"],
            "totals": {
                "qty": round(total_qty, 2),
                "total_cost": round(total_cost, 2),
                "import_duty": round(total_duty, 2),
                "vat": round(total_vat, 2),
                "total_after_tax": round(total_after_tax, 2),
                "aged_over_180d_cost": round(sum(aging_summary[b]["cost"] for b in ["6-12 months", "12-24 months", "+24 months"]), 2),
                "aged_over_180d_tax": round(sum(aging_summary[b]["total_after_tax"] for b in ["6-12 months", "12-24 months", "+24 months"]), 2)
            },
            "aging_summary": aging_summary,
            "customers": customers,
            "warehouses": warehouses,
            "product_groups": product_groups
        },
        "records": records,
        "projections": projections
    }

    # Ensure output dirs
    os.makedirs("src/data", exist_ok=True)
    os.makedirs("public", exist_ok=True)

    with open("src/data/inventory_data.json", "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False)

    with open("public/inventory_data.json", "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False)

    print("Success: Wrote inventory_data.json to src/data/ and public/")
    print(f"Total Batches: {len(records)}, Total Valuation: ${total_cost:,.2f}, Total After Tax: ${total_after_tax:,.2f}")

if __name__ == "__main__":
    main()
