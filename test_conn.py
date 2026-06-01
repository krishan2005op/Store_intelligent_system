import asyncio, asyncpg, os

async def test():
    dsn = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://store_intel:store_intel@localhost:5432/store_intel",
    )
    # asyncpg expects postgres:// without +asyncpg
    dsn = dsn.replace("postgresql+asyncpg://", "postgresql://")
    try:
        conn = await asyncpg.connect(dsn)
        await conn.close()
        print("Connection succeeded")
    except Exception as e:
        print("Connection failed:", e)

if __name__ == "__main__":
    asyncio.run(test())
