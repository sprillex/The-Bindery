import requests
import json
from abc import ABC, abstractmethod

class WeatherService(ABC):
    def __init__(self, api_key=None):
        self.api_key = api_key

    @abstractmethod
    def get_forecast(self, lat, lon):
        pass

    def _format_html(self, title, forecast_data, source_name):
        html = f"<html><head><title>{title}</title><meta charset='utf-8'></head><body>"
        html += f"<h1>{title}</h1>"
        html += f"<h3>Source: {source_name}</h3>"
        html += "<hr>"

        # This is a generic formatter. Subclasses can override or we can make this smarter.
        # For now, let's assume forecast_data is a list of dicts with 'period', 'desc', 'temp'

        if isinstance(forecast_data, list):
            for item in forecast_data:
                period = item.get('period', 'Unknown Period')
                temp = item.get('temp', '')
                desc = item.get('desc', '')
                icon = item.get('icon', '')

                html += f"<div><h4>{period}</h4>"
                if icon:
                    html += f"<img src='{icon}' alt='Weather Icon'><br>"
                html += f"<strong>Temperature:</strong> {temp}<br>"
                html += f"<p>{desc}</p></div><hr>"
        elif isinstance(forecast_data, dict):
             html += "<pre>" + json.dumps(forecast_data, indent=2) + "</pre>"
        else:
             html += str(forecast_data)

        html += "</body></html>"
        return html

class OpenWeatherMapOneCallService(WeatherService):
    def get_forecast(self, lat, lon):
        # https://openweathermap.org/api/one-call-3
        # Requires Key
        url = "https://api.openweathermap.org/data/3.0/onecall"
        params = {
            'lat': lat,
            'lon': lon,
            'exclude': 'minutely',
            'units': 'imperial',
            'appid': self.api_key
        }
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Process data into list
            forecast_items = []

            # Current
            current = data.get('current', {})
            forecast_items.append({
                'period': 'Current',
                'temp': f"{current.get('temp')} F",
                'desc': current.get('weather', [{}])[0].get('description', ''),
                'icon': "" # OWM icons are separate URLs, keeping simple for now
            })

            # Daily
            import datetime
            for day in data.get('daily', []):
                dt = day.get('dt') # Timestamp
                date_str = datetime.datetime.fromtimestamp(dt).strftime('%A, %B %d')

                temp_min = day.get('temp', {}).get('min')
                temp_max = day.get('temp', {}).get('max')

                forecast_items.append({
                    'period': date_str,
                    'temp': f"High: {temp_max} F / Low: {temp_min} F",
                    'desc': day.get('weather', [{}])[0].get('description', '')
                })

            return self._format_html(f"Weather for {lat}, {lon}", forecast_items, "OpenWeatherMap (One Call)")
        except Exception as e:
            return f"<html><body><h1>Error</h1><p>{str(e)}</p></body></html>"

class OpenWeatherMapService(WeatherService):
    def get_forecast(self, lat, lon):
        # https://openweathermap.org/current
        # https://openweathermap.org/forecast5
        # 5 day / 3 hour forecast
        url = "https://api.openweathermap.org/data/2.5/forecast"
        params = {
            'lat': lat,
            'lon': lon,
            'units': 'imperial',
            'appid': self.api_key
        }
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            # This API returns a list of 3-hour chunks (list of 40 items for 5 days)
            forecast_items = []

            for item in data.get('list', []):
                dt_txt = item.get('dt_txt') # "2022-08-30 15:00:00"
                main = item.get('main', {})
                weather = item.get('weather', [{}])[0]

                forecast_items.append({
                    'period': dt_txt,
                    'temp': f"{main.get('temp')} F (Feels like {main.get('feels_like')} F)",
                    'desc': f"{weather.get('main')} - {weather.get('description')}"
                })

            city_name = data.get('city', {}).get('name', f"{lat}, {lon}")
            return self._format_html(f"Weather for {city_name}", forecast_items, "OpenWeatherMap (Free v2.5)")

        except Exception as e:
             return f"<html><body><h1>Error</h1><p>{str(e)}</p></body></html>"

class WeatherAPIService(WeatherService):
    def get_forecast(self, lat, lon):
        # http://api.weatherapi.com/v1/forecast.json?key=<key>&q=<lat>,<lon>&days=3
        url = "http://api.weatherapi.com/v1/forecast.json"
        params = {
            'key': self.api_key,
            'q': f"{lat},{lon}",
            'days': 3
        }
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            forecast_items = []

            # Current
            current = data.get('current', {})
            forecast_items.append({
                'period': 'Current',
                'temp': f"{current.get('temp_f')} F",
                'desc': current.get('condition', {}).get('text', '')
            })

            # Forecast
            for day in data.get('forecast', {}).get('forecastday', []):
                date = day.get('date')
                day_data = day.get('day', {})
                max_temp = day_data.get('maxtemp_f')
                min_temp = day_data.get('mintemp_f')
                desc = day_data.get('condition', {}).get('text')

                forecast_items.append({
                    'period': date,
                    'temp': f"High: {max_temp} F / Low: {min_temp} F",
                    'desc': desc
                })

            return self._format_html(f"Weather for {data.get('location', {}).get('name')}", forecast_items, "WeatherAPI.com")

        except Exception as e:
            return f"<html><body><h1>Error</h1><p>{str(e)}</p></body></html>"

class NWSService(WeatherService):
    def get_forecast(self, lat, lon):
        # 1. Get Points
        headers = {'User-Agent': '(rachel-module-creator, contact@example.com)'}
        point_url = f"https://api.weather.gov/points/{lat},{lon}"

        try:
            r1 = requests.get(point_url, headers=headers, timeout=10)
            r1.raise_for_status()
            point_data = r1.json()

            forecast_url = point_data.get('properties', {}).get('forecast')
            if not forecast_url:
                raise Exception("No forecast URL found")

            # 2. Get Forecast
            r2 = requests.get(forecast_url, headers=headers, timeout=10)
            r2.raise_for_status()
            forecast_data = r2.json()

            periods = forecast_data.get('properties', {}).get('periods', [])

            items = []
            for p in periods:
                items.append({
                    'period': p.get('name'),
                    'temp': f"{p.get('temperature')} {p.get('temperatureUnit')}",
                    'desc': p.get('detailedForecast')
                })

            location_props = point_data.get('properties', {}).get('relativeLocation', {}).get('properties', {})
            city = location_props.get('city', 'Unknown City')
            state = location_props.get('state', 'Unknown State')

            return self._format_html(f"Weather for {city}, {state}", items, "National Weather Service")

        except Exception as e:
            return f"<html><body><h1>Error</h1><p>{str(e)}</p></body></html>"

class TomorrowIOService(WeatherService):
    def get_forecast(self, lat, lon):
        # https://api.tomorrow.io/v4/weather/forecast?location=lat,lon&units=imperial&apikey=...
        url = "https://api.tomorrow.io/v4/weather/forecast"
        params = {
            'location': f"{lat},{lon}",
            'units': 'imperial',
            'apikey': self.api_key
        }
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Simple parsing of daily data
            items = []
            timelines = data.get('timelines', {})
            daily = timelines.get('daily', [])

            for day in daily:
                time = day.get('time')
                values = day.get('values', {})
                temp_avg = values.get('temperatureAvg')

                items.append({
                    'period': time,
                    'temp': f"Avg: {temp_avg} F",
                    'desc': "Detailed data available in JSON raw view if needed."
                })

            return self._format_html(f"Weather for {lat}, {lon}", items, "Tomorrow.io")
        except Exception as e:
             return f"<html><body><h1>Error</h1><p>{str(e)}</p></body></html>"

class VisualCrossingService(WeatherService):
    def get_forecast(self, lat, lon):
         # https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/[location]/[date1]/[date2]?key=YOUR_API_KEY
         url = f"https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/{lat},{lon}"
         params = {'key': self.api_key}
         try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            items = []
            days = data.get('days', [])
            for day in days:
                items.append({
                    'period': day.get('datetime'),
                    'temp': f"High: {day.get('tempmax')} / Low: {day.get('tempmin')}",
                    'desc': day.get('description')
                })

            return self._format_html(f"Weather for {data.get('address')}", items, "Visual Crossing")
         except Exception as e:
            return f"<html><body><h1>Error</h1><p>{str(e)}</p></body></html>"

def get_weather_service(service_name, api_key=None):
    if service_name == 'openweathermap':
        return OpenWeatherMapService(api_key)
    elif service_name == 'openweathermap_onecall':
        return OpenWeatherMapOneCallService(api_key)
    elif service_name == 'weatherapi':
        return WeatherAPIService(api_key)
    elif service_name == 'nws':
        return NWSService(api_key)
    elif service_name == 'tomorrowio':
        return TomorrowIOService(api_key)
    elif service_name == 'visualcrossing':
        return VisualCrossingService(api_key)
    else:
        raise ValueError("Unknown service")
