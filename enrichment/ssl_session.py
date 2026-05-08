"""
Gemeinsame requests-Session mit Windows-Zertifikatsspeicher.
Löst SSL-Fehler auf Corporate-Netzwerken mit SSL-Inspektion.
"""
import requests

def _make_session() -> requests.Session:
    session = requests.Session()
    try:
        import truststore
        import ssl
        ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        # requests erwartet einen Adapter; wir nutzen HTTPAdapter mit custom verify-Pfad
        # Einfachster Weg: urllib3 patchen via truststore.inject_into_ssl()
        truststore.inject_into_ssl()
    except Exception:
        pass
    return session

# Einmal erzeugen, überall importieren
_session = _make_session()

def get(url: str, **kwargs) -> requests.Response:
    return _session.get(url, **kwargs)

def post(url: str, **kwargs) -> requests.Response:
    return _session.post(url, **kwargs)
