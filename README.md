# Tabelog Map

## Introduction

This is a map for Tabelog Hyakumeiten (百名店) featuring restaurants across all cuisine types. It visualizes top-rated establishments from Japan's leading restaurant review platform.

## Setup Steps

### Prerequisites
```bash
pip install -r requirements.txt
```

### Configuration
Update your Google Maps API key in the script (e.g., `GOOGLE_API_KEY = 'your_api_key_here'`).

### Run the Application
```bash
python tabelog-map.py
```

This will launch a GUI where you can:
1. Collect/update restaurant data from Tabelog
2. Generate an interactive HTML map

## Result

The interactive map displays:
- **Location markers** for each Hyakumeiten restaurant
- **Cuisine filters** to explore by food type (default unchecked)
- **Restaurant details** including ratings, address, and Tabelog links
- **Multiple base map options** including Google Street View
