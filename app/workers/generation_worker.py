from app.core.logging import setup_logging
from app.services.generation_queue_service import run_worker_loop


def main() -> None:
    setup_logging()
    run_worker_loop()


if __name__ == "__main__":
    main()
