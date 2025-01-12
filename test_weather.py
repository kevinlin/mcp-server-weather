import pytest
import pytest_asyncio
from pytest_httpx import HTTPXMock
from weather import format_alert, make_nws_request, get_alerts, get_forecast


# Sample API response fixtures
@pytest.fixture
def sample_alert_response():
    return {
        "features": [{
            "properties": {
                "event": "Severe Thunderstorm Warning",
                "areaDesc": "Northern California",
                "severity": "Severe",
                "description": "Strong storms expected",
                "instruction": "Take shelter"
            }
        }]
    }


@pytest.fixture
def sample_points_response():
    return {
        "properties": {
            "forecast": "https://api.weather.gov/gridpoints/MTR/84,105/forecast"
        }
    }


@pytest.fixture
def sample_forecast_response():
    return {
        "properties": {
            "periods": [{
                "name": "Tonight",
                "temperature": 72,
                "temperatureUnit": "F",
                "windSpeed": "10 mph",
                "windDirection": "NW",
                "detailedForecast": "Clear skies"
            }]
        }
    }


# Unit Tests
def test_format_alert():
    alert_feature = {
        "properties": {
            "event": "Test Alert",
            "areaDesc": "Test Area",
            "severity": "Moderate",
            "description": "Test Description",
            "instruction": "Test Instructions"
        }
    }
    formatted = format_alert(alert_feature)
    assert "Test Alert" in formatted
    assert "Test Area" in formatted
    assert "Moderate" in formatted


# Integration Tests
@pytest.mark.asyncio
async def test_get_alerts_success(httpx_mock: HTTPXMock, sample_alert_response):
    httpx_mock.add_response(
        url="https://api.weather.gov/alerts/active/area/CA",
        json=sample_alert_response
    )

    result = await get_alerts("CA")
    assert "Severe Thunderstorm Warning" in result
    assert "Northern California" in result


@pytest.mark.asyncio
async def test_get_alerts_no_alerts(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://api.weather.gov/alerts/active/area/CA",
        json={"features": []}
    )

    result = await get_alerts("CA")
    assert "No active alerts" in result


@pytest.mark.asyncio
async def test_get_forecast_success(
        httpx_mock: HTTPXMock,
        sample_points_response,
        sample_forecast_response
):
    # Mock both API calls needed for forecast
    httpx_mock.add_response(
        url="https://api.weather.gov/points/37.7749,-122.4194",
        json=sample_points_response
    )
    httpx_mock.add_response(
        url="https://api.weather.gov/gridpoints/MTR/84,105/forecast",
        json=sample_forecast_response
    )

    result = await get_forecast(37.7749, -122.4194)
    assert "Tonight" in result
    assert "72°F" in result
    assert "10 mph NW" in result


# Error Cases
@pytest.mark.asyncio
async def test_get_alerts_network_error(httpx_mock: HTTPXMock):
    httpx_mock.add_exception(
        url="https://api.weather.gov/alerts/active/area/CA",
        exception=TimeoutError()
    )

    result = await get_alerts("CA")
    assert "Unable to fetch alerts" in result


@pytest.mark.asyncio
async def test_get_forecast_invalid_json(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://api.weather.gov/points/37.7749,-122.4194",
        content=b"Invalid JSON"
    )

    result = await get_forecast(37.7749, -122.4194)
    assert "Unable to fetch forecast data" in result