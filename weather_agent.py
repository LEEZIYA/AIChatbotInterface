from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
import requests
import time

def print_hi(name):
    print(f'Hi, {name}')


client = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.7,
    # api_key=os.getenv("OPENAI_API_KEY")
)

def get_coordinates(place):
    url = "https://nominatim.openstreetmap.org/search"

    params = {
        "q": place,
        "format": "json",
        "limit": 1
    }

    headers = {
        "User-Agent": "geo-script-python"
    }

    response = requests.get(url, params=params, headers=headers)

    if response.status_code == 200:
        data = response.json()

        if data:
            lat = data[0]["lat"]
            lon = data[0]["lon"]
            print(f"Location: {place}")
            print(f"Latitude: {lat}")
            print(f"Longitude: {lon}")
        else:
            print("Location not found.")
        return lat, lon
    else:
        print("Error:", response.status_code)
        return None, None

def get_weather(lat, lon):

    url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": lat,
        "longitude": lon,
        "current_weather": True,
        "hourly": "temperature_2m,relativehumidity_2m,windspeed_10m,precipitation"
    }

    response = requests.get(url, params=params)

    return response.json()

def analyze_weather(weather_data):

    prompt = f"""
    You are a professional weather monitoring AI.
    Analyze the following weather data and generate a monitoring report.

    Include:
    - Current conditions
    - Temperature
    - Humidity
    - Wind speed
    - Rain probability
    - Any potential severe weather warnings
    - Safety recommendations

    Weather data:
    {weather_data}
    """

    response = client.invoke(prompt)
    return response.content

def weather_agent():

    location = input("Enter country/state/city: ")

    lat, lon = get_coordinates(location)

    #print(f"\nCoordinates: {lat}, {lon}")
    print("Weather monitoring started...\n")

    while True:

        weather_data = get_weather(lat, lon)

        report = analyze_weather(weather_data)

        print("----- WEATHER REPORT -----")
        print(report)
        print("--------------------------\n")

        #time.sleep(600)

if __name__ == '__main__':
    #print_hi('PyCharm')
    # all_flights = flight_api()
    #place = input("Enter a country or state: ")
    #get_coordinates(place)
    weather_agent()
    """
    sample output
    
    C:\Users\e_sha\PycharmProjects\PythonProject\.venv\Scripts\python.exe C:\AIChatbotInterface\weather_agent.py 
C:\Users\e_sha\PycharmProjects\PythonProject\.venv\Lib\site-packages\langchain_core\_api\deprecation.py:25: UserWarning: Core Pydantic V1 functionality isn't compatible with Python 3.14 or greater.
  from pydantic.v1.fields import FieldInfo as FieldInfoV1
Enter country/state/city: singapore
Location: singapore
Latitude: 1.3571070
Longitude: 103.8194992

Coordinates: 1.3571070, 103.8194992
Weather monitoring started...

----- WEATHER REPORT -----
### Weather Monitoring Report

**Location:** Latitude 1.375, Longitude 103.875  
**Date & Time of Report:** 2026-03-07, 14:15 GMT

---

#### Current Conditions:
- **Weather Code:** Partly Cloudy (WMO Code 3)
- **Day/Night Status:** Night

#### Temperature:
- **Current Temperature:** 25.9 °C

#### Humidity:
- **Current Humidity:** 86% 

#### Wind Speed:
- **Current Wind Speed:** 7.4 km/h
- **Wind Direction:** 43° (Northeast)

#### Rain Probability:
- **Current Precipitation:** 0.0 mm (no rain observed)
- **Estimated Rain Probability:** Low (based on current data)

#### Severe Weather Warnings:
- **Warnings:** No severe weather warnings issued at this time. 

#### Safety Recommendations:
1. **Outdoor Activities:** Ideal weather for outdoor activities; however, be cautious of potential changes in weather conditions, particularly regarding humidity and wind.
2. **Hydration:** Stay hydrated, especially due to the high humidity levels.
3. **Night Visibility:** If outdoors at night, ensure proper lighting as visibility may decrease.
4. **Monitor Weather Updates:** Continue to monitor local weather services for any rapid changes or updates, especially for the upcoming hours.

---

**Additional Notes:**
- The temperature is expected to remain stable with possible fluctuations throughout the night. 
- The humidity indicates a muggy atmosphere; outdoor activities should be planned accordingly. 
- No immediate concerns for severe weather, but conditions can change; remain alert. 

Stay safe and enjoy the evening!
--------------------------

"""


