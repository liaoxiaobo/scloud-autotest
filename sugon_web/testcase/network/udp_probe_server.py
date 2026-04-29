#!/usr/bin/env python3
import argparse
import os
import socket


def write_lines(path, lines, mode):
    with open(path, mode, encoding="utf-8") as file_obj:
        for line in lines:
            file_obj.write(line + "\n")
        file_obj.flush()
        os.fsync(file_obj.fileno())


def main():
    parser = argparse.ArgumentParser(description="Receive one UDP packet and persist it.")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--log", default="/tmp/udp_receive.log")
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--bufsize", type=int, default=4096)
    args = parser.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((args.bind, args.port))
        write_lines(args.log, [f"LISTENING {args.port}"], "w")

        data, addr = sock.recvfrom(args.bufsize)
        write_lines(
            args.log,
            [
                data.decode("utf-8", "replace"),
                f"FROM {addr[0]}:{addr[1]}",
            ],
            "a",
        )
    finally:
        sock.close()


if __name__ == "__main__":
    main()
