import logging
import socket
import threading
import json
import sys
import base64
import zlib
from collections import Counter

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# In-memory storage
peer_data = []  # List to hold peer information
active_connections = {}  # To manage active connections
host_files_online = []  # To track online hosts

# Log event helper
def log_event(message):
    logging.info(message)

# Update peer data in memory
def update_client_info(peers_ip, peers_port, peers_hostname, file_name, file_size, piece_hash, piece_size, num_order_in_file):
    global peer_data  # Declare peer_data as global here
    try:
        for i in range(len(num_order_in_file)):
            peer_entry = {
                'peers_ip': peers_ip,
                'peers_port': peers_port,
                'peers_hostname': peers_hostname,
                'file_name': file_name,
                'file_size': file_size,
                'piece_hash': piece_hash[i],
                'piece_size': piece_size,
                'num_order_in_file': num_order_in_file[i]
            }
            # Add peer data if it doesn't already exist
            if peer_entry not in peer_data:
                peer_data.append(peer_entry)
    except Exception as e:
        print(f"An error occurred while updating client info: {e}")

# Print current peer data for debugging
def print_peer_data():
    print("Current peer data:")
    for peer in peer_data:
        print(peer)

def count_piece_frequency(peer_data, file_name):
    piece_count = Counter()
    for peer in peer_data:
        if peer['file_name'] == file_name:
            piece_count[peer['num_order_in_file']] += 1
    return piece_count

# Handle client connections
def client_handler(conn, addr):
    global peer_data  # Declare peer_data as global here
    try:
        while True:
            data = conn.recv(4096).decode()
            if not data:
                break

            command = json.loads(data)
            peers_ip = addr[0]
            peers_port = command['peers_port']
            peers_hostname = command['peers_hostname']
            file_name = command.get('file_name', "")
            file_size = command.get('file_size', "")
            piece_hash = command.get('piece_hash', "")
            piece_size = command.get('piece_size', "")
            num_order_in_file = command.get('num_order_in_file', "")

            if command.get('action') == 'introduce':
                active_connections[peers_ip] = conn
                host_files_online.append((peers_ip, peers_port))
                log_event(f"Connection established with {peers_hostname}/{peers_ip}:{peers_port}")

            elif command['action'] == 'publish':
                log_event(f"Updating client info in memory for hostname: {peers_hostname}/{peers_ip}:{peers_port}")
                update_client_info(peers_ip, peers_port, peers_hostname, file_name, file_size, piece_hash, piece_size, num_order_in_file)
                log_event(f"In-memory update complete for hostname: {peers_hostname}/{peers_ip}:{peers_port}")
                conn.sendall("File list updated successfully.".encode())

            elif command['action'] == 'download':
                results = [
                    peer for peer in peer_data
                    if peer['file_name'] == file_name and
                    peer['num_order_in_file'] not in num_order_in_file and
                    peer['piece_hash'] not in piece_hash
                ]

                filtered_results = [
                    peer for peer in results
                    if (peer['peers_ip'], peer['peers_port']) in host_files_online
                ]

                for peer in filtered_results:
                    peer['piece_hash'] = base64.b64encode(peer['piece_hash'].encode('utf-8')).decode('utf-8')

                response = {'action': 'download-reply'}

                if filtered_results:
                    # Compress and encode the data
                    compressed_peers_info = zlib.compress(json.dumps(filtered_results).encode('utf-8'))
                    response['peers_info'] = base64.b64encode(compressed_peers_info).decode('utf-8')  # Base64 encode compressed data
                else:
                    response['error'] = 'File not available'

                # Send the response
                conn.sendall(json.dumps(response).encode('utf-8'))

            elif command['action'] == 'exit':
                peer_data = [
                    peer for peer in peer_data
                    if peer['peers_ip'] != peers_ip or peer['peers_port'] != peers_port
                ]
                host_files_online.remove((peers_ip, peers_port))
                break

    except Exception as e:
        logging.exception(f"An error occurred while handling client {addr}: {e}")
    finally:
        if conn.fileno() != -1:  # Check if connection is open using fileno()
            conn.close()
        if (peers_ip, peers_port) in host_files_online:
            host_files_online.remove((peers_ip, peers_port))
        log_event(f"Connection with {addr} has been closed.")

# Command shell for server
def server_command_shell():
    while True:
        cmd_input = input("Server command: ")
        cmd_parts = cmd_input.split()
        if cmd_parts:
            action = cmd_parts[0]
            if action == "show-peers":
                print_peer_data()
            elif action == "exit":
                break
            else:
                print("Unknown command or incorrect usage.")

# Start the server
def start_server(host='0.0.0.0', port=65432):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((host, port))
    server_socket.listen()
    log_event("Server started and is listening for connections.")

    try:
        while True:
            conn, addr = server_socket.accept()
            thread = threading.Thread(target=client_handler, args=(conn, addr))
            thread.start()
            log_event(f"Active connections: {threading.active_count() - 1}")
    except KeyboardInterrupt:
        log_event("Server shutdown requested.")
    finally:
        server_socket.close()

if __name__ == "__main__":
    SERVER_HOST = '192.168.56.100'
    SERVER_PORT = 65432

    # Start server in a separate thread
    server_thread = threading.Thread(target=start_server, args=(SERVER_HOST, SERVER_PORT))
    server_thread.start()

    # Start the server command shell in the main thread
    server_command_shell()

    # Signal the server to shutdown
    print("Server shutdown requested.")
    sys.exit(0)
