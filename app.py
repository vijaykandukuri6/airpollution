from flask import Flask, render_template_string, jsonify
import requests
import pandas as pd
import os
from datetime import datetime, timedelta
import json

app = Flask(__name__)

# Define 5 major cities with their coordinates
CITIES = {
    "Delhi": {"lat": 28.7041, "lon": 77.1025},
    "Mumbai": {"lat": 19.0760, "lon": 72.8777},
    "Beijing": {"lat": 39.9042, "lon": 116.4074},
    "Los Angeles": {"lat": 34.0522, "lon": -118.2437},
    "London": {"lat": 51.5074, "lon": -0.1278}
}

def fetch_air_pollution_data(city_name, lat, lon, days=30):
    """
    Fetch air pollution data for a city over the last 30 days.
    Uses Open-Meteo Air Quality API (free, no API key required)
    """
    try:
        # Use dates within available historical data (adjust based on API availability)
        # The API may not have data for future dates, so we use a fixed historical period
        end_date = datetime(2025, 12, 31).date()  # Use latest available data
        start_date = end_date - timedelta(days=days-1)
        
        url = "https://archive-api.open-meteo.com/v1/archive"
        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "daily": "pm2_5,pm10,o3,no2,so2",
            "timezone": "auto"
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Create DataFrame from the response
        df = pd.DataFrame({
            'date': pd.to_datetime(data['daily']['time']),
            'PM2.5': data['daily']['pm2_5'],
            'PM10': data['daily']['pm10'],
            'O3': data['daily']['o3'],
            'NO2': data['daily']['no2'],
            'SO2': data['daily']['so2']
        })
        
        df['city'] = city_name
        return df
    
    except Exception as e:
        print(f"Error fetching data for {city_name}: {str(e)}")
        return None

def get_all_pollution_data():
    """Fetch air pollution data for all cities"""
    all_data = []
    
    for city_name, coords in CITIES.items():
        print(f"Fetching data for {city_name}...")
        df = fetch_air_pollution_data(city_name, coords["lat"], coords["lon"])
        if df is not None:
            all_data.append(df)
    
    if all_data:
        combined_df = pd.concat(all_data, ignore_index=True)
        return combined_df
    return None

@app.route("/")
def home():
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Air Pollution Data - Last 30 Days</title>
        <link rel="stylesheet" href="/static/styles.css">
        <style>
            h1 { color: #333; text-align: center; }
            .refresh-btn { font-size: 16px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🌍 Air Pollution Levels - Last 30 Days</h1>
            <div class="info">
                <strong>Note:</strong> Data shows average pollutant concentrations (µg/m³) over the last 30 days.
                <br>PM2.5 and PM10 = Particulate Matter | O3 = Ozone | NO2 = Nitrogen Dioxide | SO2 = Sulfur Dioxide
            </div>
            <button class="refresh-btn" onclick="location.href='/browse'">📄 Browse Data</button>
            <div class="cities" id="cities-container">
                <p>Loading data...</p>
            </div>
        </div>
        <script>
            fetch('/api/pollution-data')
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Network response was not ok');
                    }
                    return response.json();
                })
                .then(data => {
                    const container = document.getElementById('cities-container');
                    container.innerHTML = '';
                    
                    if (!Array.isArray(data)) {
                        throw new Error('Invalid data format received');
                    }
                    
                    if (data.length === 0) {
                        container.innerHTML = '<p style="color: orange;">No data available. Please try again later.</p>';
                        return;
                    }
                    
                    const groupedData = {};
                    data.forEach(record => {
                        if (!groupedData[record.city]) {
                            groupedData[record.city] = [];
                        }
                        groupedData[record.city].push(record);
                    });
                    
                    Object.keys(groupedData).forEach(city => {
                        const records = groupedData[city];
                        const avg = (arr) => {
                            const filtered = arr.filter(v => v !== null && v !== undefined && !isNaN(v));
                            return filtered.length > 0 ? filtered.reduce((a, b) => a + b, 0) / filtered.length : 0;
                        };
                        
                        const avgData = {
                            pm25: avg(records.map(r => r['PM2.5'])).toFixed(2),
                            pm10: avg(records.map(r => r['PM10'])).toFixed(2),
                            o3: avg(records.map(r => r['O3'])).toFixed(2),
                            no2: avg(records.map(r => r['NO2'])).toFixed(2),
                            so2: avg(records.map(r => r['SO2'])).toFixed(2)
                        };
                        
                        const card = document.createElement('div');
                        card.className = 'city-card';
                        card.innerHTML = `
                            <h3>${city}</h3>
                            <div class="metric">
                                <span class="metric-label">PM2.5 (µg/m³)</span>
                                <span class="metric-value">${avgData.pm25}</span>
                            </div>
                            <div class="metric">
                                <span class="metric-label">PM10 (µg/m³)</span>
                                <span class="metric-value">${avgData.pm10}</span>
                            </div>
                            <div class="metric">
                                <span class="metric-label">O3 (µg/m³)</span>
                                <span class="metric-value">${avgData.o3}</span>
                            </div>
                            <div class="metric">
                                <span class="metric-label">NO2 (ppb)</span>
                                <span class="metric-value">${avgData.no2}</span>
                            </div>
                            <div class="metric">
                                <span class="metric-label">SO2 (ppb)</span>
                                <span class="metric-value">${avgData.so2}</span>
                            </div>
                        `;
                        container.appendChild(card);
                    });
                })
                .catch(error => {
                    console.error('Error:', error);
                    document.getElementById('cities-container').innerHTML = '<p style="color: red;">Error loading data: ' + error.message + '. Please refresh the page.</p>';
                });
        </script>
    </body>
    </html>
    """
    return render_template_string(html_template)

@app.route("/api/pollution-data")
def api_pollution_data():
    """API endpoint to return air pollution data as JSON"""
    try:
        df = get_all_pollution_data()
        if df is not None and not df.empty:
            # Replace NaN values with None for JSON serialization
            df = df.where(pd.notna(df), None)
            records = df.to_dict('records')
            return jsonify(records)
        else:
            return jsonify([]), 200
    except Exception as e:
        print(f"API Error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/download-csv")
def download_csv():
    """Download air pollution data as CSV"""
    df = get_all_pollution_data()
    if df is not None:
        csv_data = df.to_csv(index=False)
        return csv_data, 200, {'Content-Disposition': 'attachment; filename="air_pollution_30days.csv"', 'Content-Type': 'text/csv'}
    return "Error: Could not fetch data", 500


@app.route("/browse")
def browse():
        """Browse raw pollution data in a table"""
        # Prefer local CSV if available
        csv_path = os.path.join(os.getcwd(), 'air_pollution_30_days.csv')
        if os.path.exists(csv_path):
                try:
                        df = pd.read_csv(csv_path, parse_dates=['Date'])
                        df_sorted = df.sort_values(['City', 'Date'])
                except Exception as e:
                        return render_template_string(f'<p style="color: red;">Error reading CSV: {e}</p><p><a href="/">Back</a></p>')
        else:
                # fallback to fetching from API
                df = get_all_pollution_data()
                if df is None or df.empty:
                        return render_template_string('<p style="color: red;">No data available to browse.</p><p><a href="/">Back</a></p>')
                df_sorted = df.sort_values(['city', 'date'])

        table_html = df_sorted.to_html(classes='table', index=False, border=0)

        browse_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Browse Air Pollution Data</title>
            <link rel="stylesheet" href="/static/styles.css">
            <style>
                /* small overrides specific to browse view */
                .back { margin-top: 10px; display: inline-block; padding: 8px 12px; background:#4CAF50; color: white; text-decoration: none; border-radius:4px; }
            </style>
        </head>
        <body>
            <div class="container">
                <h2>Browse Raw Air Pollution Data</h2>
                <p>Showing records for the selected period. Use your browser find (Ctrl+F) to search.</p>
                {{ table_html|safe }}
                <p><a class="back" href="/">← Back</a> <a class="back" href="/download-csv" style="background:#1976d2;margin-left:8px;">Download CSV</a></p>
            </div>
        </body>
        </html>
        """
        return render_template_string(browse_template, table_html=table_html)

if __name__ == "__main__":
    app.run(debug=True)