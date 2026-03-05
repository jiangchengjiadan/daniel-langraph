# src/server/image_server.py
"""Lightweight HTTP server for serving images"""

import os
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote

from ..config import config
from ..logging import log


class ImageServer:
    """Simple HTTP server for serving images"""

    def __init__(self, port: int = None, images_dir: str = None):
        """
        Initialize image server

        Args:
            port: Server port (defaults to config value)
            images_dir: Directory for images (defaults to config value)
        """
        self.port = port or config.image_server_port
        self.images_dir = Path(images_dir) if images_dir else config.images_dir
        self.server = None
        self.thread = None
        self.log = log.bind(module="image_server")

    def start(self, blocking: bool = False):
        """Start the image server"""
        if self.server:
            self.log.warning("Server already running")
            return

        # Create custom handler
        handler = self._create_handler()

        # Start server
        self.server = HTTPServer(("0.0.0.0", self.port), handler)

        self.log.info(f"Image server starting on port {self.port}")
        self.log.info(f"Serving images from: {self.images_dir}")

        if blocking:
            self.server.serve_forever()
        else:
            self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
            self.log.info("Image server started in background")

    def stop(self):
        """Stop the image server"""
        if self.server:
            self.server.shutdown()
            self.server = None
            self.log.info("Image server stopped")

    def _create_handler(self):
        """Create a custom HTTP request handler"""
        images_dir = self.images_dir

        class ImageHandler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(images_dir), **kwargs)

            def translate_path(self, path):
                """Override to handle URL-encoded paths with special characters"""
                # Decode URL-encoded path (handles spaces, chinese chars, etc.)
                path = unquote(path)
                return super().translate_path(path)

            def end_headers(self):
                # Add CORS headers
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                super().end_headers()

            def do_OPTIONS(self):
                self.send_response(200)
                self.end_headers()

            def log_message(self, format, *args):
                pass  # Suppress logging

        return ImageHandler

    def is_running(self) -> bool:
        """Check if server is running"""
        return self.server is not None
