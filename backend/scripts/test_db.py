import asyncio
import sys
from pathlib import Path

# Add backend directory to Python path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.database import engine


async def test():
    try:
        async with engine.connect() as conn:
            print("Database connected successfully:", not conn.closed)
    except Exception as e:
        print(f"Database connection failed: {type(e).__name__}: {e}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(test())
    