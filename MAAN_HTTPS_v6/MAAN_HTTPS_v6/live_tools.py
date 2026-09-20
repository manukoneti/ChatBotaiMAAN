"""Live lookups; never substitute model guesses for failed external data."""
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit
import requests


def route(prompt, mode, history=None):
    if mode != 'auto': return mode, prompt
    text=prompt.strip()
    # Explicit searches win, even if the query discusses weather science.
    explicit = re.search(r"\b(search|look up|lookup|google|find online)\b|వెతుకు|సెర్చ్",text,re.I)
    media = re.search(r"\b(youtube|you tube|trailer|teaser|official video|video link|website link|download link)\b|యూట్యూబ్|లింక్",text,re.I)
    general = re.search(r"^(explain|define|what (?:is|are)|how (?:does|do))\b",text,re.I)
    live_weather = re.search(r"\b(weather|wheather|forecast|temperature|rain|raining)\b|వాతావరణం|వర్షం",text,re.I)
    if explicit or (media and not (general and not re.search(r'\b(link|find|give|show|latest)\b',text,re.I))):
        query=text
        if re.search(r'\byou\s*tube\b',text,re.I) and 'site:' not in text.lower():query += ' site:youtube.com'
        return 'web',query
    if live_weather:
        conceptual = re.search(r"\b(what is|what are|explain|define|how does|why does|difference|meaning|write|poem|story)\b",text,re.I)
        local = re.search(r"\b(in|at|today|tomorrow|now|tonight|this week)\b",text,re.I)
        if not conceptual or local:return 'weather',prompt
    # Follow up a city clarification within the same conversation only.
    if history and history[-1].get('role')=='assistant':
        last=history[-1]['content']
        if last.startswith(('Which city?', 'I found several places.','City not found.')):
            if len(text)<=100 and not re.search(r'\b(hi|hello|thanks|explain|write|forget|stop|help|what|why|how)\b',text,re.I):
                return 'weather',prompt
    creative = re.search(r"^(write|draft|compose|translate|rewrite|summari[sz]e)\b",text,re.I)
    if not creative and re.search(r"\b(latest|news|current|today|tonight|live score|scores|price|prices|exchange rate|release date)\b|తాజా|వార్తలు|ధర",text,re.I):
        return 'web',prompt
    if re.search(r"\b(give|find|show|send|share|get)\b.*\b(link|url|website)\b",text,re.I):return 'web',prompt
    return 'chat',prompt


def city_query(text):
    text = re.sub(r'(?i)\b(what is|what.s|tell me|show me|please|weather|wheather|forecast|temperature|status|today|tomorrow|now|current|tonight|this week|will it|is it|raining|rain|how is|how.s|in|at|the|for)\b', ' ', text)
    return re.sub(r'\s+', ' ', text).strip(' ?!.,')


def get_json(url, params):
    with requests.get(url, params=params, timeout=(5,15)) as r:
        r.raise_for_status()
        return r.json()


def weather(query):
    city = city_query(query)
    if not city or city.lower() in ('here','my location'):
        return 'Which city? Enter a city, for example Hyderabad. I do not track your location.'
    # Comma-separated state/country disambiguates cities without silently choosing.
    parts = [p.strip() for p in city.split(',')]
    places = get_json('https://geocoding-api.open-meteo.com/v1/search', {'name':parts[0], 'count':10, 'language':'en', 'format':'json'}).get('results', [])
    if len(parts)>1:
        places = [p for p in places if all(s.lower() in ' '.join(str(p.get(k,'')) for k in ('name','admin1','country','country_code')).lower() for s in parts[1:])]
    def label(p):return ', '.join(str(p[k]) for k in ('name','admin1','country') if p.get(k))
    if not places:return 'City not found. Try the English city name, optionally followed by state or country.'
    if len(places)>1:
        return 'I found several places. Enter one with its state/country:\n\n'+'\n'.join(dict.fromkeys(label(p) for p in places))
    p=places[0]
    data=get_json('https://api.open-meteo.com/v1/forecast', {'latitude':p['latitude'],'longitude':p['longitude'],'current':'temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m','daily':'temperature_2m_max,temperature_2m_min,precipitation_probability_max','forecast_days':3,'timezone':'auto'})
    c=data['current']; d=data['daily']
    def val(v):return 'unavailable' if v is None else str(v)
    lines=[label(p),f"Current model estimate · {c['time']} ({data['timezone']})",f"Temperature: {val(c['temperature_2m'])} °C · Feels like: {val(c['apparent_temperature'])} °C",f"Humidity: {val(c['relative_humidity_2m'])}% · Wind: {val(c['wind_speed_10m'])} km/h",'', '3-day forecast']
    for i,day in enumerate(d['time']):
        lines.append(f"{day}: {val(d['temperature_2m_min'][i])}–{val(d['temperature_2m_max'][i])} °C · Max rain probability: {val(d['precipitation_probability_max'][i])}%")
    return '\n'.join(lines)+'\n\nWeather: Open-Meteo (CC BY 4.0); locations: GeoNames\nhttps://open-meteo.com/'


def web_search(query):
    from ddgs import DDGS
    results=DDGS(timeout=10).text(query, max_results=5, backend='duckduckgo')
    lines=['Web results · '+datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),'Search excerpts may be incomplete or out of date. Open the sources to verify.']
    for r in results:
        url=str(r.get('href',''))
        parsed=urlsplit(url)
        if parsed.scheme not in ('http','https') or not parsed.netloc:continue
        lines.extend(['',str(r.get('title','Source'))[:200],str(r.get('body',''))[:650],url])
    if len(lines)==2:return 'No web results found. Try a more specific search.'
    return '\n'.join(lines)


def lookup(mode, query):
    try:return weather(query) if mode=='weather' else web_search(query)
    except Exception:
        return ('Weather service' if mode=='weather' else 'Web search')+' is unavailable or rate-limited right now. Please try again later. I have not guessed an answer.'
