"""Docker healthcheck for a running application process."""

from urllib.request import urlopen


def main() -> None:
    with urlopen("http://127.0.0.1:8000/healthz", timeout=3) as response:
        if response.status != 200:
            raise RuntimeError("Application healthcheck failed")


if __name__ == "__main__":
    main()
