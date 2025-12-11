"""Config flow to configure MyHome."""
import asyncio
import ipaddress
import re
from typing import Dict, Optional
import OWNd
import inspect


import async_timeout
from voluptuous import Schema, Required, Coerce, All, Range, In
from homeassistant.config_entries import ConfigFlow, OptionsFlow, CONN_CLASS_LOCAL_PUSH
from homeassistant.const import (
    CONF_FRIENDLY_NAME,
    CONF_HOST,
    CONF_ID,
    CONF_MAC,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
)
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from OWNd.connection import OWNGateway, OWNSession
from OWNd.discovery import find_gateways

from .const import (
    CONF_ADDRESS,
    CONF_DEVICE_TYPE,
    CONF_FIRMWARE,
    CONF_MANUFACTURER,
    CONF_MANUFACTURER_URL,
    CONF_OWN_PASSWORD,
    CONF_SSDP_LOCATION,
    CONF_SSDP_ST,
    CONF_UDN,
    CONF_WORKER_COUNT,
    CONF_FILE_PATH,
    CONF_GENERATE_EVENTS,
    DOMAIN,
    LOGGER,
)
from .gateway import MyHOMEGatewayHandler


class MACAddress:
    def __init__(self, mac: str):
        mac = re.sub("[.:-]", "", mac).upper()
        mac = "".join(mac.split())
        if len(mac) != 12 or not mac.isalnum() or re.search("[G-Z]", mac):
            raise ValueError("Invalid MAC address")
        self.mac = mac

    def __repr__(self) -> str:
        return ":".join(self.mac[i : i + 2] for i in range(0, 12, 2))

    def __str__(self) -> str:
        return ":".join(self.mac[i : i + 2] for i in range(0, 12, 2))


class MyhomeFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a MyHome config flow."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_LOCAL_PUSH

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return MyhomeOptionsFlowHandler(config_entry)

    def __init__(self):
        self.gateway_handler: Optional[OWNGateway] = None
        self.discovered_gateways: Optional[Dict[str, OWNGateway]] = None
        self._existing_entry = None

    async def async_step_user(self, user_input=None):
        """User initiated flow (manual or discovered gateways)."""

        # Se l'utente ha già scelto qualcosa dalla select
        if user_input is not None:
            serial = user_input["serial"]

            # Scelta "Custom"
            if serial == "00:00:00:00:00:00":
                return await self.async_step_custom()

            # Gateway scoperto
            if self.discovered_gateways and serial in self.discovered_gateways:
                self.gateway_handler = await OWNGateway.build_from_discovery_info(
                    self.discovered_gateways[serial]
                )
                await self.async_set_unique_id(
                    dr.format_mac(self.gateway_handler.serial),
                    raise_on_progress=False,
                )
                # Chiediamo subito la password
                return await self.async_step_password()

        # Primo passaggio: discovery dei gateway
        try:
            with async_timeout.timeout(5):
                local_gateways = await find_gateways()
        except asyncio.TimeoutError:
            return self.async_abort(reason="discovery_timeout")

        # Se vuoi, qui puoi filtrare quelli già configurati:
        already_configured = self._async_current_ids(False)
        # Esempio (lasciato commentato):
        # local_gateways = [
        #     gw for gw in local_gateways
        #     if dr.format_mac(gw["serialNumber"]) not in already_configured
        # ]

        self.discovered_gateways = {gw["serialNumber"]: gw for gw in local_gateways}

        # Mostra scelta gateway o Custom
        options = {
            **{
                gw["serialNumber"]: f"{gw['modelName']} Gateway ({gw['address']})"
                for gw in local_gateways
            },
            "00:00:00:00:00:00": "Custom",
        }

        return self.async_show_form(
            step_id="user",
            data_schema=Schema({Required("serial"): In(options)}),
        )

    async def async_step_custom(self, user_input=None, errors=None):
        """Manual gateway setup."""
        if errors is None:
            errors = {}

        if user_input is not None:
            # Validazione IP
            try:
                user_input["address"] = str(ipaddress.IPv4Address(user_input["address"]))
            except ipaddress.AddressValueError:
                errors["address"] = "invalid_ip"

            # Validazione MAC
            try:
                user_input["serialNumber"] = dr.format_mac(
                    f"{MACAddress(user_input['serialNumber'])}"
                )
            except ValueError:
                errors["serialNumber"] = "invalid_mac"

            if not errors:
                # Estraggo la password
                password = str(user_input[CONF_OWN_PASSWORD])

                # Valori di default per i campi "SSDP-like"
                user_input.setdefault("ssdp_location", None)
                user_input.setdefault("ssdp_st", None)
                user_input.setdefault("deviceType", None)
                user_input.setdefault("friendlyName", None)
                user_input.setdefault("manufacturer", "BTicino S.p.A.")
                user_input.setdefault("manufacturerURL", "http://www.bticino.it")
                user_input.setdefault("modelNumber", None)
                user_input.setdefault("UDN", None)

                # Creo la gateway
                self.gateway_handler = OWNGateway(user_input)
                self.gateway_handler.password = password

                await self.async_set_unique_id(
                    user_input["serialNumber"], raise_on_progress=False
                )

                # Provo subito il test di connessione
                return await self.async_step_test_connection()

        # Suggerimenti per i campi
        address_suggestion = user_input.get("address") if user_input else "192.168.1.135"
        port_suggestion = user_input.get("port") if user_input else 20000
        serial_suggestion = (
            user_input.get("serialNumber") if user_input else "00:03:50:00:00:00"
        )
        model_suggestion = user_input.get("modelName") if user_input else "F454"

        return self.async_show_form(
            step_id="custom",
            data_schema=Schema(
                {
                    Required(
                        "address",
                        description={"suggested_value": address_suggestion},
                    ): str,
                    Required(
                        "port",
                        description={"suggested_value": port_suggestion},
                    ): int,
                    Required(
                        "serialNumber",
                        description={"suggested_value": serial_suggestion},
                    ): str,
                    Required(
                        "modelName",
                        description={"suggested_value": model_suggestion},
                    ): str,
                    # Password richiesta subito
                    Required(CONF_OWN_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_password(self, user_input=None, errors=None):
        """Ask for password (or reentry)."""
        if errors is None:
            errors = {}

        if user_input is not None:
            self.gateway_handler.password = str(user_input[CONF_OWN_PASSWORD])
            return await self.async_step_test_connection()

        suggested = getattr(self.gateway_handler, "password", "12345")
        return self.async_show_form(
            step_id="password",
            data_schema=Schema(
                {
                    Required(
                        CONF_OWN_PASSWORD,
                        description={"suggested_value": suggested},
                    ): str,
                }
            ),
            description_placeholders={
                CONF_HOST: getattr(self.gateway_handler, "host", ""),
                CONF_NAME: getattr(self.gateway_handler, "model_name", ""),
                CONF_MAC: getattr(self.gateway_handler, "serial", ""),
            },
            errors=errors,
        )

    async def async_step_test_connection(self, user_input=None, errors=None):
        """Test connection using host, port, and password."""
        if errors is None:
            errors = {}

        gateway = self.gateway_handler
        assert gateway is not None

        # DEBUG: dove sta OWNd nel config_flow
        try:
            LOGGER.warning(
                "CONFIG_FLOW: OWNd loaded from: %s, version: %s",
                inspect.getfile(OWNd),
                getattr(OWNd, "__version__", "unknown"),
            )
        except Exception as e:
            LOGGER.error("CONFIG_FLOW: Failed to inspect OWNd module: %s", e)

        test_session = OWNSession(
            gateway=gateway,
            logger=LOGGER,
            connection_type="command",
        )
        
        LOGGER.warning(
            "CONFIG_FLOW: starting command test session to %s:%s (password set: %s)",
            gateway.address,
            gateway.port,
            bool(gateway.password),
        )
        
        test_result = await test_session.test_connection()
        LOGGER.warning("CONFIG_FLOW: test result: %s", test_result)
        
        if test_result["Success"]:
            _new_entry_data = {
                CONF_ID: dr.format_mac(gateway.serial),
                CONF_HOST: gateway.address,
                CONF_PORT: gateway.port,
                CONF_PASSWORD: gateway.password,
                CONF_SSDP_LOCATION: gateway.ssdp_location,
                CONF_SSDP_ST: gateway.ssdp_st,
                CONF_DEVICE_TYPE: gateway.device_type,
                CONF_FRIENDLY_NAME: gateway.friendly_name,
                CONF_MANUFACTURER: gateway.manufacturer,
                CONF_MANUFACTURER_URL: gateway.manufacturer_url,
                CONF_NAME: gateway.model_name,
                CONF_FIRMWARE: gateway.model_number,
                CONF_MAC: dr.format_mac(gateway.serial),
                CONF_UDN: gateway.udn,
            }
            return self.async_create_entry(
                title=f"{gateway.model_name} Gateway",
                data=_new_entry_data,
            )

        # Password mancante o errata: rimando allo step password
        if test_result["Message"] in ["password_required", "password_error", "password_retry"]:
            errors["password"] = test_result["Message"]
            return await self.async_step_password(errors=errors)

        # Altri errori: abort
        return self.async_abort(reason=test_result["Message"])


class MyhomeOptionsFlowHandler(OptionsFlow):
    """Handle MyHome options."""

    def __init__(self, config_entry):
        self.config_entry = config_entry
        self.options = dict(config_entry.options)
        self.data = dict(config_entry.data)
        if CONF_WORKER_COUNT not in self.options:
            self.options[CONF_WORKER_COUNT] = 1
        if CONF_FILE_PATH not in self.options:
            self.options[CONF_FILE_PATH] = "/config/myhome.yaml"
        if CONF_GENERATE_EVENTS not in self.options:
            self.options[CONF_GENERATE_EVENTS] = False

    async def async_step_init(self, user_input=None):
        return await self.async_step_user()

    async def async_step_user(self, user_input=None, errors=None):
        errors = {} if errors is None else errors

        if user_input is not None:
            # aggiorna dati e options
            self.options.update({CONF_WORKER_COUNT: user_input[CONF_WORKER_COUNT]})
            self.options.update({CONF_FILE_PATH: user_input[CONF_FILE_PATH]})
            self.options.update({CONF_GENERATE_EVENTS: user_input[CONF_GENERATE_EVENTS]})
            self.data.update({CONF_HOST: user_input[CONF_ADDRESS]})
            self.data.update({CONF_OWN_PASSWORD: user_input[CONF_OWN_PASSWORD]})

            try:
                self.data[CONF_HOST] = str(ipaddress.IPv4Address(self.data[CONF_HOST]))
            except ipaddress.AddressValueError:
                errors[CONF_ADDRESS] = "invalid_ip"

            if not errors:
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=self.data
                )
                await self.hass.config_entries.async_reload(
                    self.config_entry.entry_id
                )
                return self.async_create_entry(title="", data=self.options)

        return self.async_show_form(
            step_id="user",
            data_schema=Schema(
                {
                    Required(
                        CONF_ADDRESS,
                        description={"suggested_value": self.data[CONF_HOST]},
                    ): str,
                    Required(
                        CONF_OWN_PASSWORD,
                        description={"suggested_value": self.data[CONF_PASSWORD]},
                    ): str,
                    Required(
                        CONF_FILE_PATH,
                        description={"suggested_value": self.options[CONF_FILE_PATH]},
                    ): str,
                    Required(
                        CONF_WORKER_COUNT,
                        description={"suggested_value": self.options[CONF_WORKER_COUNT]},
                    ): All(Coerce(int), Range(min=1, max=10)),
                    Required(
                        CONF_GENERATE_EVENTS,
                        description={"suggested_value": self.options[CONF_GENERATE_EVENTS]},
                    ): bool,
                }
            ),
            errors=errors,
        )



