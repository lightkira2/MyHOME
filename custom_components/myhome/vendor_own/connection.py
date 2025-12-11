""" This module handles TCP connections to the OpenWebNet gateway """

from ..const import LOGGER

import asyncio
import hmac
import hashlib
import string
import random
import logging
from typing import Union
from urllib.parse import urlparse

from .discovery import find_gateways, get_gateway, get_port
from .message import OWNMessage, OWNSignaling


class OWNGateway:
    def __init__(self, discovery_info: dict):
        # Attributes potentially provided by user
        self.address = (
            discovery_info["address"] if "address" in discovery_info else None
        )
        self._password = (
            discovery_info["password"] if "password" in discovery_info else None
        )
        # Attributes retrieved from SSDP discovery
        self.ssdp_location = (
            discovery_info["ssdp_location"]
            if "ssdp_location" in discovery_info
            else None
        )
        self.ssdp_st = (
            discovery_info["ssdp_st"] if "ssdp_st" in discovery_info else None
        )
        # Attributes retrieved from UPnP device description
        self.device_type = (
            discovery_info["deviceType"] if "deviceType" in discovery_info else None
        )
        self.friendly_name = (
            discovery_info["friendlyName"] if "friendlyName" in discovery_info else None
        )
        self.manufacturer = (
            discovery_info["manufacturer"]
            if "manufacturer" in discovery_info
            else "BTicino S.p.A."
        )
        self.manufacturer_url = (
            discovery_info["manufacturerURL"]
            if "manufacturerURL" in discovery_info
            else None
        )
        self.model_name = (
            discovery_info["modelName"]
            if "modelName" in discovery_info
            else "Unknown model"
        )
        self.model_number = (
            discovery_info["modelNumber"] if "modelNumber" in discovery_info else None
        )
        # self.presentationURL = (
        #     discovery_info["presentationURL"]
        #     if "presentationURL" in discovery_info
        #     else None
        # )
        self.serial_number = (
            discovery_info["serialNumber"] if "serialNumber" in discovery_info else None
        )
        self.udn = discovery_info["UDN"] if "UDN" in discovery_info else None
        # Attributes retrieved from SOAP service control
        self.port = discovery_info["port"] if "port" in discovery_info else None

        self._log_id = f"[{self.model_name} gateway - {self.host}]"

    @property
    def unique_id(self) -> str:
        return self.serial_number

    @unique_id.setter
    def unique_id(self, unique_id: str) -> None:
        self.serial_number = unique_id

    @property
    def host(self) -> str:
        return self.address

    @host.setter
    def host(self, host: str) -> None:
        self.address = host

    @property
    def firmware(self) -> str:
        return self.model_number

    @firmware.setter
    def firmware(self, firmware: str) -> None:
        self.model_number = firmware

    @property
    def serial(self) -> str:
        return self.serial_number

    @serial.setter
    def serial(self, serial: str) -> None:
        self.serial_number = serial

    @property
    def password(self) -> str:
        return self._password

    @password.setter
    def password(self, password: str) -> None:
        self._password = password

    @property
    def log_id(self) -> str:
        return self._log_id

    @log_id.setter
    def log_id(self, id: str) -> None:
        self._log_id = id

    @classmethod
    async def get_first_available_gateway(cls, password: str = None):
        local_gateways = await find_gateways()
        local_gateways[0]["password"] = password
        return cls(local_gateways[0])

    @classmethod
    async def find_from_address(cls, address: str):
        if address is not None:
            return cls(await get_gateway(address))
        else:
            return await cls.get_first_available_gateway()

    @classmethod
    async def build_from_discovery_info(cls, discovery_info: dict):
        if (
            ("address" not in discovery_info or discovery_info["address"] is None)
            and "ssdp_location" in discovery_info
            and discovery_info["ssdp_location"] is not None
        ):
            discovery_info["address"] = urlparse(
                discovery_info["ssdp_location"]
            ).hostname

        if "port" in discovery_info and discovery_info["port"] is None:
            if (
                "ssdp_location" in discovery_info
                and discovery_info["ssdp_location"] is not None
            ):
                discovery_info["port"] = await get_port(discovery_info["ssdp_location"])
            elif "address" in discovery_info and discovery_info["address"] is not None:
                return await cls.find_from_address(discovery_info["address"])
            else:
                return await cls.get_first_available_gateway(
                    password=discovery_info["password"]
                    if "password" in discovery_info
                    else None
                )

        return cls(discovery_info)


class OWNSession:
    """Connection to OpenWebNet gateway"""

    SEPARATOR = "##".encode()

    def __init__(
        self,
        gateway: OWNGateway = None,
        connection_type: str = "test",
        logger: logging.Logger = None,
    ):
        """Initialize the class
        Arguments:
        gateway: OpenWebNet gateway instance
        connection_type: used when logging to identify this session
        logger: instance of logging
        """

        self._gateway = gateway
        self._type = connection_type.lower()
        self._logger = logger

        # annotations for stream reader/writer:
        self._stream_reader: asyncio.StreamReader
        self._stream_writer: asyncio.StreamWriter
        # init them to None:
        self._stream_reader = None
        self._stream_writer = None

        # Se il logger non è stato passato, usiamo quello dell'integrazione
        if self._logger is None:
            self._logger = LOGGER

        self._logger.warning(
            "VENDORED OWNSession init: type=%s, gateway=%s",
            self._type,
            self._gateway.address if self._gateway else None,
        )

    @property
    def gateway(self) -> OWNGateway:
        return self._gateway

    @gateway.setter
    def gateway(self, gateway: OWNGateway) -> None:
        self._gateway = gateway

    @property
    def logger(self) -> logging.Logger:
        return self._logger

    @logger.setter
    def logger(self, logger: logging.Logger) -> None:
        self._logger = logger

    @property
    def connection_type(self) -> str:
        return self._type

    @connection_type.setter
    def connection_type(self, connection_type: str) -> None:
        self._type = connection_type.lower()

    @classmethod
    async def test_gateway(cls, gateway: OWNGateway) -> dict:
        connection = cls(gateway)
        return await connection.test_connection()

    async def test_connection(self) -> dict:
        retry_count = 0
        retry_timer = 1

        while True:
            try:
                if retry_count > 2:
                    self._logger.error(
                        "%s Test session connection still refused after 3 attempts.",
                        self._gateway.log_id,
                    )
                    return {"Success": False, "Message": "connection_refused"}
                (
                    self._stream_reader,
                    self._stream_writer,
                ) = await asyncio.open_connection(
                    self._gateway.address, self._gateway.port
                )
                break
            except ConnectionRefusedError:
                self._logger.warning(
                    "%s Test session connection refused, retrying in %ss.",
                    self._gateway.log_id,
                    retry_timer,
                )
                await asyncio.sleep(retry_timer)
                retry_count += 1
                retry_timer *= 2

        try:
            result = await self._negotiate()
            await self.close()
        except ConnectionResetError as exc:
            self._logger.error(
                "%s NEGOTIATE: ConnectionResetError in %s session: %r",
                self._gateway.log_id,
                self._type,
                exc,
            )
            return {"Success": False, "Message": "password_retry"}

        return result

    async def connect(self):
        self._logger.debug("%s Opening %s session.", self._gateway.log_id, self._type)

        retry_count = 0
        retry_timer = 1

        while True:
            try:
                if retry_count > 4:
                    self._logger.error(
                        "%s %s session connection still refused after 5 attempts.",
                        self._gateway.log_id,
                        self._type.capitalize(),
                    )
                    return None
                (
                    self._stream_reader,
                    self._stream_writer,
                ) = await asyncio.open_connection(
                    self._gateway.address, self._gateway.port
                )
                return await self._negotiate()
            except (ConnectionRefusedError, asyncio.IncompleteReadError):
                self._logger.warning(
                    "%s %s session connection refused, retrying in %ss.",
                    self._gateway.log_id,
                    self._type.capitalize(),
                    retry_timer,
                )
                await asyncio.sleep(retry_timer)
                retry_count += 1
                retry_timer = retry_count * 2
            except ConnectionResetError:
                self._logger.warning(
                    "%s %s session connection reset, retrying in 60s.",
                    self._gateway.log_id,
                    self._type.capitalize(),
                )
                await asyncio.sleep(60)
                retry_count += 1

    async def close(self) -> None:
        """Closes the connection to the OpenWebNet gateway"""

        # this method may be invoked on an empty instance of OWNSession, so be robust against Nones:
        if self._stream_writer is not None:
            self._stream_writer.close()
            await self._stream_writer.wait_closed()
        if self._gateway is not None:
            self._logger.debug(
                "%s %s session closed.", self._gateway.log_id, self._type.capitalize()
            )

    async def _negotiate(self) -> dict:
        type_id = 0 if self._type == "command" else 1
        error = False
        error_message = None

        self._logger.debug(
            "%s Negotiating %s session.", self._gateway.log_id, self._type
        )

        self._stream_writer.write(f"*99*{type_id}##".encode())
        await self._stream_writer.drain()

        raw_response = await self._stream_reader.readuntil(OWNSession.SEPARATOR)
        resulting_message = OWNSignaling(raw_response.decode())
        # self._logger.debug("%s Reply: `%s`", self._gateway.log_id, resulting_message)

        if resulting_message.is_nack():
            self._logger.error(
                "%s Error while opening %s session.", self._gateway.log_id, self._type
            )
            error = True
            error_message = "connection_refused"

        raw_response = await self._stream_reader.readuntil(OWNSession.SEPARATOR)
        resulting_message = OWNSignaling(raw_response.decode())
        if resulting_message.is_nack():
            error = True
            error_message = "negotiation_refused"
            self._logger.debug(
                "%s Reply: `%s`", self._gateway.log_id, resulting_message
            )
            self._logger.error(
                "%s Error while opening %s session.", self._gateway.log_id, self._type
            )
        elif resulting_message.is_sha():
            self._logger.debug(
                "%s Received SHA challenge: `%s`",
                self._gateway.log_id,
                resulting_message,
            )
            if self._gateway.password is None:
                error = True
                error_message = "password_required"
                self._logger.warning(
                    "%s Connection requires a password but none was provided.",
                    self._gateway.log_id,
                )
                self._stream_writer.write("*#*0##".encode())
                await self._stream_writer.drain()
            else:
                method = "sha"
                if resulting_message.is_sha_1():
                    # self._logger.debug("%s Detected SHA-1 method.", self._gateway.log_id)
                    method = "sha1"
                elif resulting_message.is_sha_256():
                    # self._logger.debug("%s Detected SHA-256 method.", self._gateway.log_id)
                    method = "sha256"
                self._logger.debug(
                    "%s Accepting %s challenge, initiating handshake.",
                    self._gateway.log_id,
                    method,
                )
                self._stream_writer.write("*#*1##".encode())
                await self._stream_writer.drain()
                raw_response = await self._stream_reader.readuntil(OWNSession.SEPARATOR)
                resulting_message = OWNSignaling(raw_response.decode())
                if resulting_message.is_nonce():
                    server_random_string_ra = resulting_message.nonce
                    # self._logger.debug("%s Received Ra.", self._gateway.log_id)
                    key = "".join(random.choices(string.digits, k=56))
                    client_random_string_rb = self._hex_string_to_int_string(
                        hmac.new(key=key.encode(), digestmod=method).hexdigest()
                    )
                    # self._logger.debug("%s Generated Rb.", self._gateway.log_id)
                    hashed_password = f"*#{client_random_string_rb}*{self._encode_hmac_password(method=method, password=self._gateway.password, nonce_a=server_random_string_ra, nonce_b=client_random_string_rb)}##"
                    self._logger.debug(
                        "%s Sending %s session password.",
                        self._gateway.log_id,
                        self._type,
                    )
                    self._stream_writer.write(hashed_password.encode())
                    await self._stream_writer.drain()
                    try:
                        raw_response = await asyncio.wait_for(
                            self._stream_reader.readuntil(OWNSession.SEPARATOR),
                            timeout=5,
                        )
                        resulting_message = OWNSignaling(raw_response.decode())
                        if resulting_message.is_nack():
                            error = True
                            error_message = "password_error"
                            self._logger.error(
                                "%s Password error while opening %s session.",
                                self._gateway.log_id,
                                self._type,
                            )
                        elif resulting_message.is_nonce():
                            # self._logger.debug(
                            #     "%s Received HMAC response.", self._gateway.log_id
                            # )
                            hmac_response = resulting_message.nonce
                            if hmac_response == self._decode_hmac_response(
                                method=method,
                                password=self._gateway.password,
                                nonce_a=server_random_string_ra,
                                nonce_b=client_random_string_rb,
                            ):
                                # self._logger.debug(
                                #     "%s Server identity confirmed.", self._gateway.log_id
                                # )
                                self._stream_writer.write("*#*1##".encode())
                                await self._stream_writer.drain()
                                self._logger.debug(
                                    "%s Session established successfully.",
                                    self._gateway.log_id,
                                )
                            else:
                                self._logger.error(
                                    "%s Server identity could not be confirmed.",
                                    self._gateway.log_id,
                                )
                                self._stream_writer.write("*#*0##".encode())
                                await self._stream_writer.drain()
                                error = True
                                error_message = "negociation_error"
                                self._logger.error(
                                    "%s Error while opening %s session: HMAC authentication failed.",
                                    self._gateway.log_id,
                                    self._type,
                                )
                    except asyncio.IncompleteReadError:
                        error = True
                        error_message = "password_error"
                        self._logger.error(
                            "%s Password error while opening %s session.",
                            self._gateway.log_id,
                            self._type,
                        )
                    except asyncio.TimeoutError:
                        error = True
                        error_message = "password_error"
                        self._logger.error(
                            "%s Password timeout error while opening %s session.",
                            self._gateway.log_id,
                            self._type,
                        )
        elif resulting_message.is_nonce():
            self._logger.debug(
                "%s Received nonce: `%s`", self._gateway.log_id, resulting_message
            )
            if self._gateway.password is not None:
                hashed_password = f"*#{self._get_own_password(self._gateway.password, resulting_message.nonce)}##"
                self._logger.debug(
                    "%s Sending %s session password.", self._gateway.log_id, self._type
                )
                self._stream_writer.write(hashed_password.encode())
                await self._stream_writer.drain()
                raw_response = await self._stream_reader.readuntil(OWNSession.SEPARATOR)
                resulting_message = OWNSignaling(raw_response.decode())
                # self._logger.debug("%s Reply: `%s`", self._gateway.log_id, resulting_message)
                if resulting_message.is_nack():
                    error = True
                    error_message = "password_error"
                    self._logger.error(
                        "%s Password error while opening %s session.",
                        self._gateway.log_id,
