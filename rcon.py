import asyncio
import struct

TIMEOUT = 5.0


async def rcon(host: str, password: str, command: str, port: int = 25575) -> str:
    reader, writer = await asyncio.wait_for(
        asyncio.open_connection(host, port), timeout=TIMEOUT
    )
    try:
        _send(writer, 1, 3, password)
        await asyncio.wait_for(writer.drain(), timeout=TIMEOUT)

        auth_id, _, _ = await asyncio.wait_for(_recv(reader), timeout=TIMEOUT)
        if auth_id == -1:
            raise ConnectionError("Неверный RCON пароль")

        _send(writer, 2, 2, command)
        await asyncio.wait_for(writer.drain(), timeout=TIMEOUT)

        _, _, body = await asyncio.wait_for(_recv(reader), timeout=TIMEOUT)
        return body
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


def _send(writer: asyncio.StreamWriter, req_id: int, req_type: int, payload: str) -> None:
    data = payload.encode("utf-8")
    length = len(data) + 10
    writer.write(struct.pack("<iii", length, req_id, req_type) + data + b"\x00\x00")


async def _recv(reader: asyncio.StreamReader) -> tuple[int, int, str]:
    raw_len = await reader.readexactly(4)
    length = struct.unpack("<i", raw_len)[0]
    raw = await reader.readexactly(length)
    req_id = struct.unpack("<i", raw[:4])[0]
    req_type = struct.unpack("<i", raw[4:8])[0]
    body = raw[8:-2].decode("utf-8", errors="replace")
    return req_id, req_type, body
