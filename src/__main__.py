import asyncio

from src.core import Config, Engine


async def main():
    config = Config()
    engine = Engine(config)

    # Register plugins here as they're built:
    # engine.add("broker", KiteBroker(role=BrokerRole.EXECUTION))
    # engine.add("broker", GrowwBroker(role=BrokerRole.DATA))
    # engine.add("provider", NewsProvider())
    # engine.add("analyzer", SentimentAnalyzer())
    # engine.add("strategy", HybridStrategy())
    # engine.add("executor", PaperExecutor())

    await engine.run()


if __name__ == "__main__":
    asyncio.run(main())
