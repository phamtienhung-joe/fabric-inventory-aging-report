Monthly fabric stock and liability



- Export from [Power BI](https://app.powerbi.com/groups/me/reports/b366a706-e603-43c3-a5bd-3e3d5454d692/d76c2aad770ecb003555?ctid=8363f4f8-f36b-40f0-93d1-9bf80555473b&experience=power-bi)

- Data table columns: BATCHNUMBER    ITEMNUMBER    CONFIGURATION    PRODUCTGROUPID    WAREHOUSE    LOCATION    PHYSICALINVENTORY    REGISTERED    PHYSICALRESERVED    AVAILABLEPHYSICAL    Qty_Inspection    TransferQty    DESCRIPTION    PO    Inventtransid    receive_date    Supplier Code    PR    PR Line    Stanrdcost    MANUFACTURINGDATE    Aging    Registered_PO    Registered_WO
  
  * **RULES**:

- PRODUCTGROUPID = "RM" (all Raw Materials)

- ITEMNUMBER: Starting with LH (-01,-03,-07) -> ignore the rest

- LOCATION: Filter out ...-DEFECT; UPH WIP

- QTY for Report: Take column PHYSICALINVENTORY

- Add column to pack category for Aging column, range 0-3 months, 3-6 months, 6-12 months; 12-24 months and +24 months

- Calculate Value (PHYSICALINVENTORY x Stanrdcost), name "Total Cost". Show Batch as well.

- Add "Import Duty"; "VAT"; "Total After Tax" (based on Standard Cost). Detail please see report "RSG UPH Arhaus Aged Detail Cover_FORM"

- Calculate AWS - average week of stock, import TAX, "Total Cost" x 12%. Detail please see report "RSG UPH Arhaus Aged Detail Cover_FORM"

- Standard cost - taken from table On-hand in the link "https://rsc-prod.operations.dynamics.com/?cmp=rff&mi=InventOnhandItem"; Map to data.
