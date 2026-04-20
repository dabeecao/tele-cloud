#
# Copyright (C) 2026 @dabeecao
#
# This file is part of TeleCloud project, lead developer: @dabeecao
# For support, please visit the TTJB support group: https://t.me/thuthuatjb_sp
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
#

import os
import asyncio
from hydrogram import Client
from dotenv import load_dotenv

load_dotenv()

api_id = os.getenv("API_ID")
api_hash = os.getenv("API_HASH")

if not api_id or not api_hash:
    print("❌ Thiếu API_ID hoặc API_HASH trong file .env")
    exit(1)

app = Client(
    "telecloud",
    api_id=int(api_id),
    api_hash=api_hash
)

async def main():
    async with app:
        print("\n✅ SESSION_STRING của bạn:\n")
        session_string = await app.export_session_string()
        print(session_string)

if __name__ == "__main__":
    # This runs the async function and manages the loop for you
    asyncio.run(main())
