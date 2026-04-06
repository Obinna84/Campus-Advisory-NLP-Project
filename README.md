# Campus Safety Language Map

A one-week NLP + GIS class project built as a Streamlit web app. The app reads campus safety alert text, classifies each incident, extracts locations, geocodes them, and displays the results on an interactive map.

## Features
- Upload a CSV of school safety emails or crime alerts
- Paste a raw email directly into the sidebar parser
- Auto-classify incidents into categories such as Sexual Misconduct, Theft, Violence, Suspicious Activity, Safety Hazard, and Vehicle Incident
- Extract locations from natural-language descriptions when a location column is missing
- Geocode locations into map coordinates
- Visualize incidents on an interactive Folium map
- Filter by incident category and date
- Preview how the NLP pipeline parsed a raw email before adding it

## Expected CSV format
Required column:
- `description`

Optional columns:
- `location`
- `date`
- `category`

Example:

```csv
 description,location,date,category
 "Misdemeanor sexual abuse reported near the 500 block of W Street NW at 7:19 pm.",500 block of W Street NW,2026-04-06,Sexual Misconduct
 "Suspicious person observed near Founders Library.",Founders Library,2026-03-10,Suspicious Activity
```

## Setup
```bash
python -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Project structure
```text
campus_safety_app/
├── app.py
├── requirements.txt
├── README.md
└── data/
    └── sample_alerts.csv
```

## How NLP is used
1. **Cleaning:** removes repeated boilerplate and extra whitespace.
2. **Classification:** uses incident-specific keywords to tag each alert.
3. **Location extraction:** pulls locations like building names or street blocks from the text.
4. **Geocoding:** converts extracted locations into latitude and longitude.
5. **Mapping:** plots the results on an interactive GIS map.

## Notes
- Geocoding depends on the quality of the location text.
- Exact results will be best when campus buildings or street names are explicit.
- You can expand the `KNOWN_LOCATIONS` dictionary in `app.py` for your campus.
