# Fabric & Upholstery Inventory Aging & Statutory Liability Dashboard

An executive dashboard for monitoring raw-material inventory valuation, statutory tax
liabilities (12% Import Duty, 8% VAT), aging distribution, and 4-month demand projections.

**Live:** https://phamtienhung-joe.github.io/fabric-inventory-aging-report/

> **Portfolio demo.** Every identifier and figure in the published dataset is synthetic:
> item codes, batch numbers, suppliers, customers, POs, descriptions, and all monetary
> values. The application logic, calculation rules, and interaction design are the real work.

---

## Business Logic & Calculation Rules

### 1. Scope & Filtering
- **Product Groups**: `RM_FABRIC` (fabric), `RM_LEATHER` (leather), `RM_PU/PVC` (synthetic leather).
- **Location Exclusion**: defect and WIP locations excluded.
- **Quantity Basis**: physical on-hand inventory.

### 2. Standard Cost Valuation & Customer Mapping
- **Standard Costs**: mapped from Dynamics 365 Supply Chain Management (`InventOnhandItem`).
  Customer-owned material (`COM`) carries $0.00 standard cost liability.
- **Customer Program**: material mapped to a customer program through a cross-reference table.

### 3. Aging Buckets & Financial Liability
- **Aging Tiers**:
  - `0 - 3 months` (0 to 89 days)
  - `3 - 6 months` (90 to 179 days)
  - `6 - 12 months` (180 to 359 days)
  - `12 - 24 months` (360 to 719 days)
  - `+24 months` (720+ days)
- **Statutory Taxes**:
  - `Total Cost` = `Physical Inventory` x `Standard Cost`
  - `Import Duty` = `Total Cost` x 12%
  - `VAT` = (`Total Cost` + `Import Duty`) x 8%
  - `Total After Tax` = `Total Cost` + `Import Duty` + `VAT`

### 4. 4-Month Raw Material Stock Projection
- **Formula**: `Ending Stock (M)` = `Starting Stock` + `Inbound (Registered PO)` - `Monthly Allocated Demand`
- **AWS (Average Weeks of Stock)**: measured against forward average weekly demand.

---

## Architecture & Tech Stack

- **Frontend Dashboard**: React 18, Vite 6, Tailwind CSS. Built to static assets (`base: './'`).
- **Data Layer**: a normalized `inventory_data.json` carrying metadata aggregates plus
  per-batch records, fetched at runtime.
- **CI/CD Deployment**: GitHub Actions workflow (`.github/workflows/deploy.yml`) builds and
  publishes to GitHub Pages on every push to `main`.

---

## Local Development

```bash
# 1. Install dependencies
npm install

# 2. Start local development server
npm run dev

# 3. Compile static production build
npm run build
```
