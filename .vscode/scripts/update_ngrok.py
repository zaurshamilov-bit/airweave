"""Updates the .env file with the current ngrok public URL."""

import time
from pathlib import Path

import requests


def update_env() -> None:
    """Update the LOCAL_NGROK_SERVER variable in .env with current ngrok URL.

    Waits briefly for Ngrok to initialize, then queries its local API to get
    the public URL. Updates the .env file by replacing the existing
    LOCAL_NGROK_SERVER line with the new URL while preserving all other content.

    Prints success message with new URL or error message if operation fails.
    """
    # Wait for ngrok to start
    time.sleep(2)

    try:
        # Get ngrok url
        response = requests.get("http://localhost:4040/api/tunnels")
        url = response.json()["tunnels"][0]["public_url"]

        # Update .env file
        env_path = Path(__file__).parent.parent.parent / ".env"
        with open(env_path, "r") as file:
            lines = file.readlines()

        with open(env_path, "w") as file:
            for line in lines:
                if line.startswith("LOCAL_NGROK_SERVER="):
                    file.write(f"LOCAL_NGROK_SERVER={url}\n")
                else:
                    file.write(line)
        print(f"Updated LOCAL_NGROK_SERVER to {url}")
    except Exception as e:
        print(f"Failed to update .env: {e}")


if __name__ == "__main__":
    update_env()
