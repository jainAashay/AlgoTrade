"""
REST client module for exchange communication.
"""
import json
import logging
from typing import Dict, List, Optional, Any
import requests
import time
import json
import hmac
import hashlib

from delta_rest_client import DeltaRestClient
from configs.config_loader import Config
from exceptions import ExchangeError

logger = logging.getLogger(__name__)


class RestClient:
    """REST client for Delta Exchange API."""
    
    def __init__(self):
        """Initialize REST client."""
        self.base_url = Config.get("exchange", "rest_url").rstrip("/")
        self.api_key = Config.get("exchange", "api_key")
        self.api_secret = Config.get("exchange", "api_secret")
        
        self.delta_client = DeltaRestClient(
            base_url=self.base_url,
            api_key=self.api_key,
            api_secret=self.api_secret
        )
        
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        logger.info(f"REST client initialized for {self.base_url}")

    def send_request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None, body: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send a generic REST request, merging default session headers with any provided custom headers."""
        method = method.upper()
        params = params or {}
        body = body or {}
        url = self.base_url + path
        
        # Start with default session headers
        request_headers = dict(self.session.headers)
        #
        # # Ensure Host header is present
        # parsed_url = urlparse(self.base_url)
        # if parsed_url.netloc:
        #     request_headers["Host"] = parsed_url.netloc

        try:
            kwargs = {
                "method": method,
                "url": url,
                "params": params,
                "headers": request_headers,
                "timeout": 10,
            }

            if method in ("POST", "PUT", "PATCH"):
                kwargs["json"] = body
            response = self.session.request(**kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.exception(f"REST request failed: {method} {path}")
            raise ExchangeError(f"REST request failed: {method} {path}") from e

    def send_public_request(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send a public (unauthenticated) request."""
        return self.send_request("GET", path, params=params, headers={})

    def send_private_request(self,method: str,path: str,body: Optional[Dict[str, Any]] = None,headers: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:

        method = method.upper()
        timestamp = str(int(time.time()))

        body_json = ""
        if body:
            # IMPORTANT: compact JSON, no spaces
            body_json = json.dumps(body, separators=(",", ":"))

        # ---- Signature payload ----
        signature_payload = method + timestamp + path + body_json

        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            signature_payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        request_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "api-key": self.api_key,
            "timestamp": timestamp,
            "signature": signature
        }

        if headers:
            request_headers.update(headers)

        url = self.base_url + path

        response = requests.request(
            method=method,
            url=url,
            headers=request_headers,
            data=body_json if body else None,
            timeout=10
        )

        # ---- Error handling ----
        if response.status_code >= 400:
            raise Exception(
                f"Delta API error {response.status_code}: {response.text}"
            )

        return response.json()

    def fetch_ohlc(self, symbol: str, resolution: str, start_ts: int, end_ts: int) -> List[Dict[str, Any]]:
        """Fetch OHLC candles from Delta Exchange."""
        try:
            params = {
                "symbol": symbol,
                "resolution": resolution,
                "start": int(start_ts),
                "end": int(end_ts)
            }

            response = self.send_public_request("/v2/history/candles", params=params)
            candles = response.get("result", [])

            return [{
                "ts": c["time"],
                "open": float(c["open"]),
                "high": float(c["high"]),
                "low": float(c["low"]),
                "close": float(c["close"]),
                "volume": float(c["volume"])
            } for c in candles]
        except Exception as e:
            logger.exception(f"Error fetching OHLC data for {symbol}")
            raise ExchangeError(f"Failed to fetch OHLC data for {symbol}") from e

    def get_assets(self):
        """Fetch wallet balances from Delta Exchange."""
        try:
            response = self.delta_client.get_assets()
            logger.info(f"Assets response : {response}")
            return response
        except Exception as e:
            logger.exception("Error fetching wallet balances")
            raise ExchangeError("Failed to fetch wallet balances") from e

    def get_fill_history(self, symbol: str, query_params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Fetch fill history from Delta Exchange."""
        try:
            response = self.delta_client.fills(query=query_params,page_size=500)
            logger.info(f"Fill history response for {symbol}: {response}")
            return response
        except Exception as e:
            logger.exception(f"Error fetching fill history for {symbol}")
            raise ExchangeError(f"Failed to fetch fill history for {symbol}") from e





# Simple global instance
_rest_client = None

def get_rest_client() -> RestClient:
    """Get the global RestClient instance."""
    global _rest_client
    if _rest_client is None:
        _rest_client = RestClient()
    return _rest_client

