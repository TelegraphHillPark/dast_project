"""
Worker — точка входа для фонового обработчика сканов.
Sprint 3: здесь будет asyncio-цикл Orchestrator + Crawler.
"""
import asyncio
import logging

logger = logging.getLogger("dast.worker")


async def main() -> None:
    logger.info("Worker started. Waiting for scan tasks...")
    # TODO Sprint 3: подключить Redis-очередь и Orchestrator
    while True:
        await asyncio.sleep(5)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
