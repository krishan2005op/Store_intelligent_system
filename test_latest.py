import asyncio
from app.db.session import get_event_repository

async def main():
    async for repo in get_event_repository():
        latest = await repo.latest_event_at()
        print('latest:', latest)

if __name__ == '__main__':
    asyncio.run(main())
