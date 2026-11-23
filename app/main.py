import asyncio
import socket


async def send_ping(loop: asyncio.AbstractEventLoop, client_socket: socket.socket):
    try:
        while True:
            data = await loop.sock_recv(client_socket, 1024)
            if not data:
                break

            await loop.sock_sendall(client_socket, b"+PONG\r\n")

    except ConnectionResetError, BrokenPipeError, asyncio.CancelledError:
        pass


async def main(host="127.0.0.1", port=6379):
    loop = asyncio.get_running_loop()

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((host, port))
    server_socket.listen()
    server_socket.setblocking(False)

    print(f"Server listening on {host}:{port}...")

    try:
        while True:
            client_socket, _ = await loop.sock_accept(server_socket)
            client_socket.setblocking(False)
            asyncio.create_task(send_ping(loop, client_socket))
    finally:
        server_socket.close()

    # connection.sendall(b"+PONG\r\n")

    # while True:
    #     data = connection.recv(1024)
    #     if not data:
    #         break
    #     connection.sendall(b"+PONG\r\n")


if __name__ == "__main__":
    asyncio.run(main())
