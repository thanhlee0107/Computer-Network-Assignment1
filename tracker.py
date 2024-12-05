import logging
import socket
import threading
import json
import sys
import base64
import zlib
import shutil
import os
from collections import Counter

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# In-memory storage
peer_data = []  # List to hold peer information
active_connections = {}  # To manage active connections
host_files_online = []  # To track online hosts
TORRENT_DIR = "torrents"  # Thư mục lưu file torrent
lock = threading.Lock()


def load_torrent_file(file_name, torrent_dir="torrents"):
    torrent_file_path = os.path.join(torrent_dir, f"{file_name}.torrent")
    if os.path.exists(torrent_file_path):
        with open(torrent_file_path, "r") as f:
            return json.load(f)
    return None

# Log event helper
def log_event(message):
    logging.info(message)

# Update peer data in memory
# def update_client_info(peers_ip, peers_port, peers_hostname, file_name, file_size, piece_hash, piece_size, num_order_in_file):
#     global peer_data  # Declare peer_data as global here
#     try:
#         for i in range(len(num_order_in_file)):
#             peer_entry = {
#                 'peers_ip': peers_ip,
#                 'peers_port': peers_port,
#                 'peers_hostname': peers_hostname,
#                 'file_name': file_name,
#                 'file_size': file_size,
#                 'piece_hash': piece_hash[i],
#                 'piece_size': piece_size,
#                 'num_order_in_file': num_order_in_file[i]
#             }
#             # Add peer data if it doesn't already exist
#             if peer_entry not in peer_data:
#                 peer_data.append(peer_entry)
#     except Exception as e:
#         print(f"An error occurred while updating client info: {e}")
def save_torrent_file(file_name, file_size, piece_hash, piece_size, peer_info, num_order_in_file, torrent_dir="torrents"):
    os.makedirs(torrent_dir, exist_ok=True)  # Tạo thư mục nếu chưa tồn tại
    torrent_file_path = os.path.join(torrent_dir, f"{file_name}.torrent")
    
    # Đọc dữ liệu torrent hiện tại (nếu có)
    if os.path.exists(torrent_file_path):
        with open(torrent_file_path, "r") as f:
            torrent_data = json.load(f)
    else:
        # Tạo dữ liệu torrent mới nếu chưa tồn tại
        torrent_data = {
            "info": {
                "file_name": file_name,
                "file_size": file_size,
                "piece_size": piece_size,
            },
            "peers": []
        }
    
    # Kiểm tra xem peer đã tồn tại trong danh sách chưa
    existing_peer = next((peer for peer in torrent_data["peers"] if peer["ip"] == peer_info["ip"] and peer["port"] == peer_info["port"]), None)
    
    if existing_peer:
        # Cập nhật danh sách pieces và piece_hash của peer
        for i, piece_num in enumerate(num_order_in_file):
            existing_peer["pieces"].append({
                "piece_number": piece_num,
                "piece_hash": piece_hash[i]
            })
    else:
        # Thêm peer mới với thông tin pieces
        peer_info["pieces"] = [{"piece_number": num_order_in_file[i], "piece_hash": piece_hash[i]} for i in range(len(num_order_in_file))]
        torrent_data["peers"].append(peer_info)
    
    # Ghi lại dữ liệu vào file torrent
    with open(torrent_file_path, "w") as f:
        json.dump(torrent_data, f, indent=4)
    print(f"Torrent file saved/updated: {torrent_file_path}")


def update_client_info(peers_ip, peers_port, peers_hostname, file_name, file_size, piece_hash, piece_size, num_order_in_file):
    global peer_data  # Dữ liệu trong bộ nhớ

    peer_info = {
        "ip": peers_ip,
        "port": peers_port,
        "hostname": peers_hostname
    }

    try:
        # Gọi hàm lưu thông tin vào file torrent
        save_torrent_file(file_name, file_size, piece_hash, piece_size, peer_info, num_order_in_file)
        
        # Cập nhật thông tin vào peer_data (in-memory) nếu cần
        for i in range(len(num_order_in_file)):
            peer_entry = {
                'peers_ip': peers_ip,
                'peers_port': peers_port,
                'peers_hostname': peers_hostname,
                'file_name': file_name,
                'file_size': file_size,
                'piece_number': num_order_in_file[i],  # Số thứ tự của piece
                'piece_hash': piece_hash[i],  # Hash của piece
                'piece_size': piece_size
            }
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
                # Load thông tin từ file torrent
                torrent_data = load_torrent_file(file_name)

                if not torrent_data:
                    response = {'action': 'download-reply', 'error': 'File not available in tracker.'}
                    conn.sendall(json.dumps(response).encode('utf-8'))
                    return

                # Lấy danh sách các peer và các piece từ file torrent
                peers_info = torrent_data.get("peers", [])
                piece_size = torrent_data["info"].get("piece_size", None)
                file_size = torrent_data["info"].get("file_size", None)

                if len(peers_info) == 0:
                    logging.error(f"No peers found in torrent file for {file_name}.")
                    response = {'action': 'download-reply', 'error': 'Invalid torrent data.'}
                    conn.sendall(json.dumps(response).encode('utf-8'))
                    return

                # Tìm các piece mà client yêu cầu (chưa có)
                requested_pieces = []
                for peer in peers_info:
                    for piece in peer.get("pieces", []):
                        piece_hash = piece.get("piece_hash")
                        piece_number = piece.get("piece_number")
                        if piece_hash and piece_number:  # Đảm bảo piece có đầy đủ thông tin cần thiết
                            requested_pieces.append({
                                "peers_ip": peer["ip"],
                                "peers_port": peer["port"],
                                "peers_hostname": peer["hostname"],
                                "num_order_in_file": piece_number,
                                "piece_hash": piece_hash,
                                "piece_size": piece_size,
                                "file_size": file_size,
                                "file_name": file_name
                            })

                # print("num order in file:", num_order_in_file)
                # Lọc bỏ những piece không hợp lệ (có piece_hash là None)
                requested_pieces = [piece for piece in requested_pieces if piece["piece_hash"] is not None]
                #Check 
                # print(f"Filtered requested_pieces: {requested_pieces}")
                
                # Lọc danh sách peer đang trực tuyến
                filtered_results = [
                    peer for peer in requested_pieces
                    if (peer['peers_ip'], peer['peers_port']) in host_files_online
                ]
                # In ra filtered results để debug
                # print(f"Filtered results (online peers): {filtered_results}")

                # Mã hóa piece_hash của từng peer
                for peer in filtered_results:
                    peer['piece_hash'] = base64.b64encode(peer['piece_hash'].encode('utf-8')).decode('utf-8')

                # Tạo phản hồi
                response = {'action': 'download-reply'}
                # print("file name requested information:", requested_pieces)
                if filtered_results:
                    # Nén và mã hóa thông tin
                    compressed_peers_info = zlib.compress(json.dumps(filtered_results).encode('utf-8'))
                    response['peers_info'] = base64.b64encode(compressed_peers_info).decode('utf-8')  # Base64 encode compressed data
                else:
                    response['error'] = 'Requested pieces not available.'

                # Gửi phản hồi đến client
                conn.sendall(json.dumps(response).encode('utf-8'))
                print(host_files_online)
            # Xuất file
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
    # TRACKER_HOST = '192.168.56.100'
    # TRACKER_PORT = 65432
    while True:
        try:
            TRACKER_HOST = input("Enter the server IP address (leave blank for 0.0.0.0): ").strip() or "0.0.0.0"
            TRACKER_PORT = int(input("Enter the server port: ").strip())
            if TRACKER_PORT < 1 or TRACKER_PORT > 65535:
                raise ValueError("Port must be between 1 and 65535.")
            break
        except ValueError as e:
            print(f"Invalid input: {e}. Please try again.")

    # Start server in a separate thread
    server_thread = threading.Thread(target=start_server, args=(TRACKER_HOST, TRACKER_PORT))
    server_thread.start()

    # Start the server command shell in the main thread
    server_command_shell()

    # Signal the server to shutdown
    print("Server shutdown requested.")
    sys.exit(0)
