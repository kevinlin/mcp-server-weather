 from unittest.mock import patch
from dotenv import load_dotenv
import os
import pytest
from pytest_httpx import HTTPXMock

load_dotenv()

API_KEY = os.getenv("OWM_API_KEY")

from weather import (
    format_alert,
    make_owm_request,
    get_alerts,
    get_forecast
)


# API Request Fixtures
@pytest.fixture
def sample_weather_response():
    return {
        "weather": [{
            "id": 200,
            "main": "Thunderstorm",
            "description": "thunderstorm with heavy rain"
        }],
        "main": {
            "temp": 35.5,  # Celsius
            "humidity": 80
        },
        "wind": {
            "speed": 7.5  # m/s
        },
        "name": "Test City"
    }


@pytest.fixture
def sample_forecast_response():
    return {
        "list": [
            {
                "dt_txt": "2025-01-12 12:00:00",
                "main": {
                    "temp": 24.5,  # Celsius
                    "feels_like": 25.5,
                    "humidity": 65
                },
                "weather": [{
                    "main": "Clear",
                    "description": "clear sky"
                }],
                "wind": {
                    "speed": 3.5  # m/s
                }
            }
        ]
    }


# API Request Tests
@pytest.mark.asyncio
async def test_make_owm_request_success(httpx_mock: HTTPXMock):
    test_url = "https://api.openweathermap.org/data/2.5/weather"
    test_params = {"q": "TestCity"}
    expected_response = {"status": "success"}

    # Add URL matching while keeping the simple structure that worked
    httpx_mock.add_response(
        url=f"{test_url}?q=TestCity&appid={API_KEY}&units=metric",
        json=expected_response
    )

    # Add request inspection for debugging
    result = await make_owm_request(test_url, test_params)

    # Get the request(s) made to our mock
    requests = httpx_mock.get_requests()
    print(f"Requests made: {[r.url for r in requests]}")

    assert len(requests) == 1
    assert str(requests[0].url).startswith(test_url)

    assert result == expected_response


@pytest.mark.asyncio
async def test_make_owm_request_timeout(httpx_mock: HTTPXMock):
    test_url = "https://api.openweathermap.org/data/2.5/weather"
    test_params = {"q": "TestCity"}

    httpx_mock.add_exception(
        url=f"{test_url}?q=TestCity&appid={API_KEY}&units=metric",
        exception=TimeoutError()
    )

    result = await make_owm_request(test_url, test_params)
    assert result is None


# Alert Formatting Tests
def test_format_alert_extreme_heat(sample_weather_response):
    sample_weather_response["main"]["temp"] = 36.0  # Above 35°C
    alert = format_alert(sample_weather_response)

    assert alert is not None
    assert "Extreme Heat" in alert
    assert "36.0°C" in alert
    assert "Test City" in alert
    assert "7.5 m/s" in alert


def test_format_alert_freezing(sample_weather_response):
    sample_weather_response["main"]["temp"] = -1.0  # Below 0°C
    alert = format_alert(sample_weather_response)

    assert alert is not None
    assert "Freezing Conditions" in alert
    assert "-1.0°C" in alert


def test_format_alert_severe_weather(sample_weather_response):
    alert = format_alert(sample_weather_response)
    assert alert is not None
    assert "Thunderstorm" in alert
    assert "thunderstorm with heavy rain" in alert


def test_format_alert_no_alert_needed(sample_weather_response):
    # Update both main and description to be consistent
    sample_weather_response["weather"][0].update({
        "main": "Clear",
        "description": "clear sky"  # Update description to match main weather
    })
    sample_weather_response["main"]["temp"] = 20.0  # Normal temperature
    alert = format_alert(sample_weather_response)
    assert alert is None


# Get Alerts Tests
@pytest.mark.asyncio
async def test_get_alerts_success(httpx_mock: HTTPXMock, sample_weather_response):
    for city in ["Los Angeles", "San Francisco", "Sacramento"]:
        httpx_mock.add_response(
            url=f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric",
            json=sample_weather_response
        )

    result = await get_alerts("CA")
    assert "Test City" in result
    assert "Thunderstorm" in result
    assert "35.5°C" in result
    assert "7.5 m/s" in result


@pytest.mark.asyncio
async def test_get_alerts_invalid_state():
    result = await get_alerts("XX")
    assert "not supported yet" in result


@pytest.mark.asyncio
async def test_get_alerts_no_severe_weather(httpx_mock: HTTPXMock, sample_weather_response):
    # Update both main and description to be consistent
    sample_weather_response["weather"][0].update({
        "main": "Clear",
        "description": "clear sky"  # Update description to match main weather
    })
    sample_weather_response["main"]["temp"] = 20.0  # Normal temperature

    for city in ["Los Angeles", "San Francisco", "Sacramento"]:
        httpx_mock.add_response(
            url=f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric",
            json=sample_weather_response
        )

    result = await get_alerts("CA")
    assert "No severe weather alerts" in result


# Get Forecast Tests
@pytest.mark.asyncio
async def test_get_forecast_success(httpx_mock: HTTPXMock, sample_forecast_response):
    lat, lon = 34.0522, -118.2437
    httpx_mock.add_response(
        url=f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={API_KEY}&units=metric",
        json=sample_forecast_response
    )

    result = await get_forecast(lat, lon)
    assert "24.5°C" in result
    assert "25.5°C" in result  # Feels like
    assert "clear sky" in result
    assert "3.5 m/s" in result


@pytest.mark.asyncio
async def test_get_forecast_failed_request(httpx_mock: HTTPXMock):
    lat, lon = 34.0522, -118.2437
    httpx_mock.add_response(
        url=f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={API_KEY}&units=metric",
        status_code=500
    )

    result = await get_forecast(lat, lon)
    assert "Unable to fetch forecast data" in result


# Edge Cases and Error Handling
def test_format_alert_missing_data():
    incomplete_data = {
        "weather": [{"main": "Clear"}],  # Missing description
        "main": {},  # Missing temperature
        "name": "Test City"
    }
    alert = format_alert(incomplete_data)
    assert alert is None


@pytest.mark.asyncio
async def test_make_owm_request_invalid_json(httpx_mock: HTTPXMock):
    test_url = "https://api.openweathermap.org/data/2.5/weather"
    test_params = {"q": "TestCity"}

    httpx_mock.add_response(
        url=f"{test_url}?q=TestCity&appid={API_KEY}&units=metric",
        content=b"Invalid JSON"
    )

    result = await make_owm_request(test_url, test_params)
    assert result is None
