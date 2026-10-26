# Power BI (optional)

Exports the pipeline's results for a Power BI report. Run from the repository root:

```bash
.venv/bin/python scripts/export_powerbi.py                  # -> data_local/powerbi/: CSVs + host_churn.xlsx
.venv/bin/python scripts/export_powerbi.py --contact-list   # adds the top 500 hosts per quarter (host ids)
```

In the browser (app.powerbi.com), import `host_churn.xlsx` (*New item → Semantic model → Excel → Browse this device*)
so every table lands in one semantic model; each uploaded CSV would become its own. In Power BI Desktop, load the CSVs
(*Get data → Text/CSV*). Either way, paste [model.tmdl](model.tmdl) into TMDL view and select *Apply*:
it relates `dim_quarter`, `dim_variant` and `dim_k` to the fact tables on `quarter`, `variant` and `k`, and adds the
shared DAX measures. Then refresh the semantic model: TMDL changes metadata only, so the new relationships hold no data
until it is recalculated. Filter `dim_variant` to `retain`, or every total doubles. In Desktop, save as a `.pbip` project,
not a `.pbix`: a `.pbix` holds a copy of the data and is git-ignored. Keep `contact_list` out of anything shared or
published to the web.
