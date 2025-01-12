import os
from typing import Any
import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

# Initialize FastMCP server
mcp = FastMCP("weather")

# Constants
OWM_API_BASE = "https://api.openweathermap.org/data/2.5"
API_KEY = os.getenv("OWM_API_KEY")


async def make_owm_request(url: str, params: dict) -> dict[str, Any] | None:
    """Make a request to the OpenWeatherMap API with error handling."""
    params["appid"] = API_KEY
    params["units"] = "metric"  # Temperature in Celsius and wind speed in meter/sec

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return None


def format_alert(weather_data: dict) -> str | None:
    """Format severe weather conditions into an alert-style message."""
    if not weather_data:
        return None

    # Check for severe conditions
    main = weather_data.get("weather", [{}])[0]
    temp = weather_data.get("main", {})
    current_temp = temp.get("temp")

    severe_conditions = []

    # Check temperature extremes only if temperature data is available
    if current_temp is not None:
        if temp.get("temp") > 35:  # Extreme heat threshold in Celsius
            severe_conditions.append("Extreme Heat")
        elif temp.get("temp") < 0:  # Freezing point in Celsius
            severe_conditions.append("Freezing Conditions")

    # Check severe weather types
    severe_weather_types = {
        "thunderstorm": "Thunderstorm",
        "tornado": "Tornado",
        "hurricane": "Hurricane",
        "snow": "Heavy Snow",
    }

    weather_id = str(main.get("id", ""))
    weather_main = main.get("main", "").lower()

    for key, alert_type in severe_weather_types.items():
        if key in weather_main or key in main.get("description", "").lower():
            severe_conditions.append(alert_type)

    if not severe_conditions:
        return None

    return f"""
Severe Weather Alert
Conditions: {', '.join(severe_conditions)}
Location: {weather_data.get('name', 'Unknown')}
Temperature: {temp.get('temp')}°C
Description: {main.get('description', 'No description available')}
Humidity: {temp.get('humidity')}%
Wind Speed: {weather_data.get('wind', {}).get('speed')} m/s
"""


@mcp.tool()
async def get_alerts(state: str) -> str:
    """Get weather alerts for a US state.

    Args:
        state: Two-letter US state code (e.g. CA, NY)
    """
    # Map of major cities per state for sampling weather conditions
    state_cities = {
        "CA": ["Los Angeles", "San Francisco", "Sacramento"],
        "NY": ["New York", "Buffalo", "Albany"],
        # Add more states and cities as needed
    }

    cities = state_cities.get(state.upper(), [])
    if not cities:
        return f"State {state} not supported yet. Please add cities to the state_cities mapping."

    alerts = []
    for city in cities:
        url = f"{OWM_API_BASE}/weather"
        data = await make_owm_request(url, {"q": city})

        if alert := format_alert(data):
            alerts.append(alert)

    if not alerts:
        return f"No severe weather alerts for {state}"

    return "\n---\n".join(alerts)


@mcp.tool()
async def get_forecast(latitude: float, longitude: float) -> str:
    """Get weather forecast for a location.

    Args:
        latitude: Latitude of the location
        longitude: Longitude of the location
    """
    url = f"{OWM_API_BASE}/forecast"
    data = await make_owm_request(url, {
        "lat": latitude,
        "lon": longitude
    })

    if not data or "list" not in data:
        return "Unable to fetch forecast data for this location."

    # Format the periods into a readable forecast
    forecasts = []
    for period in data["list"][:5]:  # Show next 5 periods
        main = period["main"]
        weather = period["weather"][0]

        forecast = f"""
Time: {period['dt_txt']}
Temperature: {main['temp']}°C
Feels Like: {main['feels_like']}°C
Conditions: {weather['main']} - {weather['description']}
Humidity: {main['humidity']}%
Wind: {period['wind']['speed']} m/s
"""
        forecasts.append(forecast)

    return "\n---\n".join(forecasts)


if __name__ == "__main__":
    mcp.run(transport='stdio')
