"""Modelo real: Cloudflare Workers AI a través de AI Gateway con ``httpx``."""

from typing import Dict, List, Optional

import httpx

from app.config import Config
from app.llm import ModelResponse, ModelUnavailable

GATEWAY_URL = (
    "https://gateway.ai.cloudflare.com/v1/{account}/{gateway}"
    "/workers-ai/v1/chat/completions"
)
REQUEST_TIMEOUT_SECONDS = 30.0
CACHE_TTL_HEADER = "cf-aig-cache-ttl"
CACHE_STATUS_HEADER = "cf-aig-cache-status"
AIG_AUTH_HEADER = "cf-aig-authorization"

__all__ = ["GatewayModel", "ModelUnavailable"]


# Proveedor de modelo: cumple la interfaz ``Model``, de un solo método.
# pylint: disable-next=too-few-public-methods
class GatewayModel:
    """Modelo servido por AI Gateway.

    Los tokens se toman de la configuración: ``cf_api_token`` va en el
    encabezado ``Authorization`` (Workers AI) y ``cf_aig_token``, si existe,
    en ``cf-aig-authorization`` (gateway autenticado). Ninguno se escribe en
    mensajes de error ni en el log.

    :param config: Configuración con las variables ``CF_*`` y las palancas.
    :param model_name: Nombre del modelo de Workers AI que se solicita.
    :param transport: Transporte ``httpx`` inyectado; ``None`` usa la red.
    """

    def __init__(
        self,
        config: Config,
        model_name: str,
        transport: Optional[httpx.BaseTransport] = None,
    ):
        self.name = model_name
        self._config = config
        self._url = GATEWAY_URL.format(
            account=config.cf_account_id, gateway=config.cf_gateway_id
        )
        self._client = httpx.Client(
            transport=transport, timeout=REQUEST_TIMEOUT_SECONDS
        )

    def _headers(self) -> Dict[str, str]:
        """Arma los encabezados de la llamada.

        :return: Encabezados con credenciales y, si aplica, token del gateway
            y vigencia de caché.
        """
        headers = {"Authorization": f"Bearer {self._config.cf_api_token}"}
        if self._config.cf_aig_token:
            headers[AIG_AUTH_HEADER] = f"Bearer {self._config.cf_aig_token}"
        if self._config.cache_ttl_seconds > 0:
            headers[CACHE_TTL_HEADER] = str(self._config.cache_ttl_seconds)
        return headers

    def complete(self, messages: List[Dict[str, str]]) -> ModelResponse:
        """Llama al modelo y lee texto, tokens y estado de caché.

        :param messages: Mensajes con ``role`` y ``content``.
        :return: La respuesta del modelo.
        :raises ModelUnavailable: Si la llamada falla o la respuesta no es válida.
        """
        body = {
            "model": self.name,
            "messages": messages,
            "max_tokens": self._config.model_max_tokens,
            "temperature": self._config.model_temperature,
        }
        try:
            response = self._client.post(self._url, headers=self._headers(), json=body)
        except httpx.HTTPError as error:
            raise ModelUnavailable(
                f"Gateway request failed: {type(error).__name__}"
            ) from None
        if response.status_code >= 400:
            raise ModelUnavailable(
                f"Gateway returned status {response.status_code}",
                status_code=response.status_code,
            )
        return self._parse(response)

    @staticmethod
    def _parse(response: httpx.Response) -> ModelResponse:
        """Interpreta la respuesta del gateway.

        :param response: Respuesta HTTP exitosa.
        :return: Texto, tokens y bandera de caché.
        :raises ModelUnavailable: Si el cuerpo no tiene el formato esperado.
        """
        try:
            data = response.json()
            text = data["choices"][0]["message"]["content"]
            usage = data["usage"]
            input_tokens = int(usage["prompt_tokens"])
            output_tokens = int(usage["completion_tokens"])
        except (ValueError, KeyError, IndexError, TypeError):
            raise ModelUnavailable("Gateway returned an invalid response") from None
        if not isinstance(text, str):
            raise ModelUnavailable("Gateway returned an invalid response")
        status = response.headers.get(CACHE_STATUS_HEADER, "")
        return ModelResponse(
            text, input_tokens, output_tokens, cached=status.upper() == "HIT"
        )
