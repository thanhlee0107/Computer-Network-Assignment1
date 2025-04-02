Assignment 1: Computer Networks – Torrent-Like Application
This assignment involves simulating a peer-to-peer (P2P) network application similar to a torrent system. The application supports:

Downloading multiple pieces of a file from multiple peers simultaneously.

Managing multiple file downloads concurrently.

Executing commands such as:

download – Downloads a file from available peers.

publish – Publishes a file to the network.

Important Notes:
The tracker must be started before running any peers.

The basic implementation has some limitations:

It cannot handle connection losses or redownload missing pieces if a peer disconnects.

If the tracker goes offline and then comes back online, it cannot retrieve torrent files from peers. However, since the tracker stores torrent files locally, they remain available after a restart.

Application Branch:
The "application" branch contains an improved version:

No hardcoded configurations.

Supports exporting the application as a standalone executable (.exe).

This project aims to help others understand and experiment with basic P2P file-sharing concepts.
